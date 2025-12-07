"""
КОМАНДА ДЛЯ ЗАПОЛНЕНИЯ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ
ООО "ИНТЕРЬЕР" - Аренда помещений

Запуск: python manage.py populate_db
Опции:
    --clear     Очистить существующие данные перед заполнением
    --spaces N  Количество помещений для генерации (по умолчанию 40)
"""

from __future__ import annotations

import io
import random
from decimal import Decimal
from typing import Any, Optional
from urllib.request import urlopen
from urllib.error import URLError

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from unidecode import unidecode

from ...models import (
    Region, City, SpaceCategory, PricingPeriod, Space, SpaceImage,
    SpacePrice, BookingStatus, TransactionStatus, UserProfile
)

User = get_user_model()

# Константы
DEFAULT_SPACES_COUNT: int = 40
PAGINATION_STEP: int = 10
MIN_AREA_SMALL: int = 20
MAX_AREA_SMALL: int = 300
MIN_AREA_LARGE: int = 50
MAX_AREA_LARGE: int = 1000
MIN_AREA_MEDIUM: int = 30
MAX_AREA_MEDIUM: int = 150
MIN_CAPACITY_DIVISOR: int = 5
MIN_CAPACITY: int = 2
MIN_BASE_HOUR_PRICE: int = 300
MAX_BASE_HOUR_PRICE: int = 3000
MIN_PRICE: int = 100
PRICE_ROUND_BASE: int = 100
PRICE_VARIANCE_MIN: float = 0.9
PRICE_VARIANCE_MAX: float = 1.1
FEATURED_PROBABILITY: float = 0.2
MAX_VIEWS_COUNT: int = 500
MIN_STREET_NUMBER: int = 1
MAX_STREET_NUMBER: int = 200
IMAGE_WIDTH: int = 800
IMAGE_HEIGHT: int = 600
IMAGES_PER_SPACE_MIN: int = 1
IMAGES_PER_SPACE_MAX: int = 4


class Command(BaseCommand):
    """Команда для заполнения базы данных тестовыми данными."""

    help = 'Заполняет базу данных начальными данными для сайта аренды помещений'

    def add_arguments(self, parser) -> None:
        """Добавление аргументов командной строки."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед заполнением'
        )
        parser.add_argument(
            '--spaces',
            type=int,
            default=DEFAULT_SPACES_COUNT,
            help=f'Количество помещений для генерации (по умолчанию {DEFAULT_SPACES_COUNT})'
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основной метод выполнения команды."""
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n╔════════════════════════════════════════════════╗\n'
            '║   ЗАПОЛНЕНИЕ БАЗЫ ДАННЫХ ООО "ИНТЕРЬЕР"        ║\n'
            '╚════════════════════════════════════════════════╝\n'
        ))

        if options['clear']:
            self.clear_data()

        try:
            with transaction.atomic():
                self.create_regions_and_cities()
                self.create_categories()
                self.create_pricing_periods()
                self.create_statuses()
                self.create_admin_user()
                self.create_moderators()
                self.create_test_users()
                self.create_spaces(options['spaces'])

            self.stdout.write(self.style.SUCCESS(
                '\n✓ База данных успешно заполнена!\n'
            ))
            self.print_summary()

        except Exception as e:
            raise CommandError(f'Ошибка при заполнении БД: {e}')

    def clear_data(self) -> None:
        """Очистка существующих данных."""
        self.stdout.write('Очистка существующих данных...')
        SpaceImage.objects.all().delete()
        Space.objects.all().delete()
        SpaceCategory.objects.all().delete()
        City.objects.all().delete()
        Region.objects.all().delete()
        PricingPeriod.objects.all().delete()
        BookingStatus.objects.all().delete()
        TransactionStatus.objects.all().delete()
        self.stdout.write('  → Данные очищены')

    def create_regions_and_cities(self) -> None:
        """Создание 21 города в разных регионах России (включая Иркутск)."""
        self.stdout.write('\n📍 Создание регионов и городов...')

        regions_data: dict[str, tuple[str, list[str]]] = {
            'Москва и Московская область': ('77', ['Москва', 'Подольск', 'Химки']),
            'Санкт-Петербург и Ленинградская область': ('78', ['Санкт-Петербург']),
            'Новосибирская область': ('54', ['Новосибирск']),
            'Свердловская область': ('66', ['Екатеринбург']),
            'Республика Татарстан': ('16', ['Казань']),
            'Нижегородская область': ('52', ['Нижний Новгород']),
            'Челябинская область': ('74', ['Челябинск']),
            'Самарская область': ('63', ['Самара']),
            'Омская область': ('55', ['Омск']),
            'Ростовская область': ('61', ['Ростов-на-Дону']),
            'Республика Башкортостан': ('02', ['Уфа']),
            'Красноярский край': ('24', ['Красноярск']),
            'Пермский край': ('59', ['Пермь']),
            'Воронежская область': ('36', ['Воронеж']),
            'Волгоградская область': ('34', ['Волгоград']),
            'Краснодарский край': ('23', ['Краснодар', 'Сочи']),
            'Саратовская область': ('64', ['Саратов']),
            'Тюменская область': ('72', ['Тюмень']),
            'Иркутская область': ('38', ['Иркутск']),  # Added Irkutsk
        }

        regions_created: int = 0
        cities_created: int = 0

        for region_name, (code, cities) in regions_data.items():
            region, created = Region.objects.get_or_create(
                name=region_name,
                defaults={'code': code}
            )
            if created:
                regions_created += 1

            for city_name in cities:
                _, created = City.objects.get_or_create(
                    name=city_name,
                    region=region,
                    defaults={'is_active': True}
                )
                if created:
                    cities_created += 1

        self.stdout.write(f'  → Создано регионов: {regions_created}')
        self.stdout.write(f'  → Создано городов: {cities_created}')

    def create_categories(self) -> None:
        """Создание категорий помещений."""
        self.stdout.write('\n📂 Создание категорий помещений...')

        categories: list[tuple[str, str, str, str]] = [
            ('Офис', 'office', 'fa-building',
             'Современные офисные помещения для бизнеса любого масштаба'),
            ('Лофт', 'loft', 'fa-warehouse',
             'Стильные лофт-пространства с индустриальным дизайном'),
            ('Коворкинг', 'coworking', 'fa-users',
             'Открытые рабочие пространства для фрилансеров и стартапов'),
            ('Конференц-зал', 'conference', 'fa-chalkboard-teacher',
             'Оборудованные залы для переговоров, семинаров и презентаций'),
            ('Фотостудия', 'photo-studio', 'fa-camera',
             'Профессиональные студии с осветительным оборудованием'),
            ('Шоу-рум', 'showroom', 'fa-store',
             'Выставочные пространства для демонстрации товаров'),
            ('Склад', 'warehouse', 'fa-boxes',
             'Складские помещения различной площади'),
            ('Торговое помещение', 'retail', 'fa-shopping-cart',
             'Помещения для розничной торговли с хорошей проходимостью'),
        ]

        created_count: int = 0
        for name, slug, icon, description in categories:
            _, created = SpaceCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'icon': icon,
                    'description': description,
                    'is_active': True
                }
            )
            if created:
                created_count += 1

        self.stdout.write(f'  → Создано категорий: {created_count}')

    def create_pricing_periods(self) -> None:
        """Создание периодов аренды."""
        self.stdout.write('\n⏱️  Создание периодов аренды...')

        periods: list[tuple[str, str, int, int]] = [
            ('hour', 'Почасовая аренда', 1, 1),
            ('day', 'Посуточная аренда', 24, 2),
            ('week', 'Понедельная аренда', 168, 3),
            ('month', 'Помесячная аренда', 720, 4),
        ]

        for name, description, hours, order in periods:
            PricingPeriod.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'hours_count': hours,
                    'sort_order': order
                }
            )

        self.stdout.write(f'  → Создано периодов: {PricingPeriod.objects.count()}')

    def create_statuses(self) -> None:
        """Создание статусов бронирования и транзакций."""
        self.stdout.write('\n📊 Создание статусов...')

        booking_statuses: list[tuple[str, str, str, int]] = [
            ('pending', 'Ожидание подтверждения', 'warning', 1),
            ('confirmed', 'Подтверждено', 'success', 2),
            ('completed', 'Завершено', 'info', 3),
            ('cancelled', 'Отменено', 'danger', 4),
        ]

        for code, name, color, order in booking_statuses:
            BookingStatus.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'color': color,
                    'sort_order': order
                }
            )

        transaction_statuses: list[tuple[str, str]] = [
            ('pending', 'В обработке'),
            ('success', 'Успешно'),
            ('failed', 'Ошибка'),
            ('refunded', 'Возврат'),
        ]

        for code, name in transaction_statuses:
            TransactionStatus.objects.get_or_create(
                code=code,
                defaults={'name': name}
            )

        self.stdout.write('  → Статусы созданы')

    def create_admin_user(self) -> None:
        """Создание администратора."""
        self.stdout.write('\n👤 Создание администратора...')

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@interior.ru',
                'first_name': 'Администратор',
                'last_name': 'Системы',
                'is_staff': True,
                'is_superuser': True,
                'user_type': 'admin',
                'phone': '+7 (999) 123-45-67'
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            UserProfile.objects.get_or_create(user=admin)
            self.stdout.write(self.style.WARNING(
                '  → Создан администратор: admin / admin123'
            ))
        else:
            self.stdout.write('  → Администратор уже существует')

    def create_moderators(self) -> None:
        """Создание тестовых модераторов."""
        self.stdout.write('\n👥 Создание модераторов...')

        moderators_data: list[tuple[str, str, str, str]] = [
            ('moderator1', 'Елена', 'Смирнова', 'elena.smirnova@interior.ru'),
            ('moderator2', 'Дмитрий', 'Волков', 'dmitry.volkov@interior.ru'),
            ('moderator3', 'Ольга', 'Новикова', 'olga.novikova@interior.ru'),
        ]

        created_count: int = 0
        for username, first_name, last_name, email in moderators_data:
            moderator, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_type': 'moderator',
                    'is_staff': True,
                    'is_superuser': False,
                    'phone': f'+7 (9{random.randint(10, 99)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}'
                }
            )
            if created:
                moderator.set_password('Moderator123!')
                moderator.save()
                UserProfile.objects.get_or_create(user=moderator)
                created_count += 1

        self.stdout.write(f'  → Создано модераторов: {created_count}')
        if created_count > 0:
            self.stdout.write(self.style.WARNING(
                '  → Логин: moderator1, moderator2, moderator3 / Пароль: Moderator123!'
            ))

    def create_test_users(self) -> None:
        """Создание тестовых пользователей."""
        self.stdout.write('\n👤 Создание тестовых пользователей...')

        users_data: list[tuple[str, str, str, str]] = [
            ('user1', 'Иван', 'Петров', 'ivan.petrov@mail.ru'),
            ('user2', 'Анна', 'Сидорова', 'anna.sidorova@mail.ru'),
            ('user3', 'Сергей', 'Козлов', 'sergey.kozlov@mail.ru'),
            ('user4', 'Мария', 'Иванова', 'maria.ivanova@mail.ru'),
            ('user5', 'Алексей', 'Николаев', 'alexey.nikolaev@mail.ru'),
        ]

        created_count: int = 0
        for username, first_name, last_name, email in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_type': 'user',
                    'is_staff': False,
                    'is_superuser': False,
                    'phone': f'+7 (9{random.randint(10, 99)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}'
                }
            )
            if created:
                user.set_password('User123!')
                user.save()
                UserProfile.objects.get_or_create(user=user)
                created_count += 1

        self.stdout.write(f'  → Создано пользователей: {created_count}')
        if created_count > 0:
            self.stdout.write(self.style.WARNING(
                '  → Логин: user1-user5 / Пароль: User123!'
            ))

    def _download_placeholder_image(self, category_slug: str, index: int) -> Optional[ContentFile]:
        """
        Скачивает placeholder изображение для помещения.

        Args:
            category_slug: Slug категории помещения
            index: Индекс изображения

        Returns:
            ContentFile с изображением или None при ошибке
        """
        # Используем picsum.photos для генерации случайных изображений
        # Добавляем параметры категории для разнообразия
        seed = f"{category_slug}-{index}-{random.randint(1, 1000)}"
        url = f"https://picsum.photos/seed/{seed}/{IMAGE_WIDTH}/{IMAGE_HEIGHT}"

        try:
            response = urlopen(url, timeout=10)
            image_data = response.read()
            return ContentFile(image_data)
        except (URLError, Exception) as e:
            self.stdout.write(self.style.WARNING(f'    Не удалось загрузить изображение: {e}'))
            return None

    def _create_space_images(self, space: Space, category_slug: str) -> int:
        """
        Создает изображения для помещения.

        Args:
            space: Помещение
            category_slug: Slug категории

        Returns:
            Количество созданных изображений
        """
        images_count = random.randint(IMAGES_PER_SPACE_MIN, IMAGES_PER_SPACE_MAX)
        created_images: int = 0

        for i in range(images_count):
            image_content = self._download_placeholder_image(category_slug, i)

            if image_content:
                image = SpaceImage(
                    space=space,
                    alt_text=f'{space.title} - фото {i + 1}',
                    is_primary=(i == 0),
                    sort_order=i
                )
                image.image.save(
                    f'space_{space.id}_{i}.jpg',
                    image_content,
                    save=True
                )
                created_images += 1

        return created_images

    def create_spaces(self, count: int) -> None:
        """Создание тестовых помещений."""
        self.stdout.write(f'\n🏢 Создание {count} помещений...')

        admin = User.objects.filter(user_type='admin').first()
        if not admin:
            admin = User.objects.filter(is_superuser=True).first()

        cities = list(City.objects.filter(is_active=True))
        categories = list(SpaceCategory.objects.filter(is_active=True))
        periods = list(PricingPeriod.objects.all())

        if not admin or not cities or not categories:
            self.stdout.write(self.style.ERROR('  → Недостаточно данных для создания помещений'))
            return

        name_templates: dict[str, list[str]] = {
            'office': [
                'Современный офис "{city}"',
                'Бизнес-центр "{city}"',
                'Офис класса А в центре',
                'Офисное помещение на {street}',
            ],
            'loft': [
                'Лофт-пространство "Арт"',
                'Индустриальный лофт "{city}"',
                'Творческий лофт "Фабрика"',
                'Лофт с панорамными окнами',
            ],
            'coworking': [
                'Коворкинг "Бизнес Хаб"',
                'Рабочее пространство "Старт"',
                'Коворкинг центр "{city}"',
                'OpenSpace коворкинг',
            ],
            'conference': [
                'Конференц-зал "Успех"',
                'Переговорная комната "Диалог"',
                'Зал для семинаров "{city}"',
                'Конференц-центр "Прогресс"',
            ],
            'photo-studio': [
                'Фотостудия "Свет"',
                'Профессиональная студия "Кадр"',
                'Фотолофт "{city}"',
                'Студия для съёмок "Объектив"',
            ],
            'showroom': [
                'Шоу-рум "Галерея"',
                'Выставочное пространство',
                'Шоу-рум в центре "{city}"',
                'Презентационный зал',
            ],
            'warehouse': [
                'Склад "{city}"',
                'Складское помещение',
                'Тёплый склад на {street}',
                'Мини-склад для бизнеса',
            ],
            'retail': [
                'Торговое помещение "{city}"',
                'Магазин на первой линии',
                'Торговая площадь на {street}',
                'Помещение в ТЦ',
            ],
        }

        streets: list[str] = [
            'ул. Ленина', 'пр. Мира', 'ул. Пушкина', 'ул. Гагарина',
            'ул. Советская', 'пр. Победы', 'ул. Центральная',
            'бульвар Строителей', 'ул. Кирова', 'пр. Революции',
            'ул. Садовая', 'ул. Молодёжная', 'пр. Космонавтов'
        ]

        descriptions: dict[str, str] = {
            'office': 'Светлое офисное помещение с современным ремонтом. Высокие потолки, панорамные окна, кондиционирование. Есть кухня и санузел. Подходит для IT-компаний, юридических фирм, консалтинга.',
            'loft': 'Стильное лофт-пространство в бывшем промышленном здании. Высокие потолки, кирпичные стены, открытые коммуникации. Идеально для творческих мероприятий, съёмок, выставок.',
            'coworking': 'Современное рабочее пространство с высокоскоростным интернетом. Есть переговорные, лаунж-зона, кухня. Включены все коммунальные услуги. Подходит для фрилансеров и небольших команд.',
            'conference': 'Оборудованный зал для проведения конференций, семинаров и тренингов. Проектор, экран, флипчарт, маркерная доска. Возможность организации кофе-брейков.',
            'photo-studio': 'Профессиональная фотостудия с полным комплектом оборудования. Циклорама, импульсный и постоянный свет, набор фонов. Гримёрка, зона отдыха для моделей.',
            'showroom': 'Элегантное выставочное пространство на первой линии. Панорамные витрины, качественное освещение. Идеально для презентаций, выставок, pop-up магазинов.',
            'warehouse': 'Сухое отапливаемое складское помещение. Удобный подъезд для транспорта, погрузочно-разгрузочная зона. Охрана, видеонаблюдение 24/7.',
            'retail': 'Торговое помещение в месте с высокой проходимостью. Первая линия домов, отдельный вход, витринные окна. Все коммуникации подведены.',
        }

        price_multipliers: dict[str, int] = {
            'hour': 1,
            'day': 6,
            'week': 30,
            'month': 100,
        }

        created_count: int = 0
        total_images: int = 0

        for i in range(count):
            city = random.choice(cities)
            category = random.choice(categories)
            street = random.choice(streets)

            templates = name_templates.get(category.slug, ['Помещение "{city}"'])
            title = random.choice(templates).format(city=city.name, street=street)

            base_slug = slugify(unidecode(f"{city.name} {category.slug} {i}"))
            slug = base_slug

            if category.slug in ['warehouse', 'retail']:
                area = random.randint(MIN_AREA_LARGE, MAX_AREA_LARGE)
            elif category.slug in ['conference', 'photo-studio']:
                area = random.randint(MIN_AREA_MEDIUM, MAX_AREA_MEDIUM)
            else:
                area = random.randint(MIN_AREA_SMALL, MAX_AREA_SMALL)

            capacity = max(MIN_CAPACITY, area // MIN_CAPACITY_DIVISOR)

            space, created = Space.objects.get_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'address': f'{street}, {random.randint(MIN_STREET_NUMBER, MAX_STREET_NUMBER)}',
                    'city': city,
                    'category': category,
                    'area_sqm': Decimal(str(area)),
                    'max_capacity': capacity,
                    'description': descriptions.get(category.slug, 'Помещение для аренды'),
                    'owner': admin,
                    'is_active': True,
                    'is_featured': random.random() < FEATURED_PROBABILITY,
                    'views_count': random.randint(0, MAX_VIEWS_COUNT),
                }
            )

            if created:
                base_hour_price = random.randint(MIN_BASE_HOUR_PRICE, MAX_BASE_HOUR_PRICE)

                for period in periods:
                    multiplier = price_multipliers.get(period.name, 1)
                    price = base_hour_price * multiplier
                    price = int(price * random.uniform(PRICE_VARIANCE_MIN, PRICE_VARIANCE_MAX))
                    price = round(price / PRICE_ROUND_BASE) * PRICE_ROUND_BASE

                    SpacePrice.objects.create(
                        space=space,
                        period=period,
                        price=Decimal(str(max(price, MIN_PRICE))),
                        is_active=True
                    )

                # Создаем изображения для помещения
                images_created = self._create_space_images(space, category.slug)
                total_images += images_created

                created_count += 1

            if (i + 1) % PAGINATION_STEP == 0:
                self.stdout.write(f'  → Создано {i + 1} помещений...')

        self.stdout.write(f'  → Всего создано помещений: {created_count}')
        self.stdout.write(f'  → Всего создано изображений: {total_images}')

    def print_summary(self) -> None:
        """Вывод итоговой статистики."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n📈 ИТОГОВАЯ СТАТИСТИКА:'))
        self.stdout.write(f'   • Регионов: {Region.objects.count()}')
        self.stdout.write(f'   • Городов: {City.objects.count()}')
        self.stdout.write(f'   • Категорий: {SpaceCategory.objects.count()}')
        self.stdout.write(f'   • Периодов аренды: {PricingPeriod.objects.count()}')
        self.stdout.write(f'   • Администраторов: {User.objects.filter(user_type="admin").count()}')
        self.stdout.write(f'   • Модераторов: {User.objects.filter(user_type="moderator").count()}')
        self.stdout.write(f'   • Пользователей: {User.objects.filter(user_type="user").count()}')
        self.stdout.write(f'   • Помещений: {Space.objects.count()}')
        self.stdout.write(f'   • Изображений: {SpaceImage.objects.count()}')
        self.stdout.write(f'   • Цен: {SpacePrice.objects.count()}')
        self.stdout.write('')
