"""
КОМАНДА ДЛЯ ЗАПОЛНЕНИЯ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ
ООО "ИНТЕРЬЕР" - Аренда помещений

Запуск: python manage.py populate_db
Опции:
    --clear     Очистить существующие данные перед заполнением
    --spaces N  Количество помещений для генерации (по умолчанию 40)
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from unidecode import unidecode

from ...models import (
    Region, City, SpaceCategory, PricingPeriod, Space, SpaceImage,
    SpacePrice, BookingStatus, TransactionStatus, UserProfile
)
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Заполняет базу данных начальными данными для сайта аренды помещений'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед заполнением'
        )
        parser.add_argument(
            '--spaces',
            type=int,
            default=40,
            help='Количество помещений для генерации (по умолчанию 40)'
        )

    def handle(self, *args, **options):
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
                self.create_test_owners()
                self.create_spaces(options['spaces'])

            self.stdout.write(self.style.SUCCESS(
                '\n✓ База данных успешно заполнена!\n'
            ))
            self.print_summary()

        except Exception as e:
            raise CommandError(f'Ошибка при заполнении БД: {e}')

    def clear_data(self):
        """Очистка существующих данных"""
        self.stdout.write('Очистка существующих данных...')
        Space.objects.all().delete()
        SpaceCategory.objects.all().delete()
        City.objects.all().delete()
        Region.objects.all().delete()
        PricingPeriod.objects.all().delete()
        BookingStatus.objects.all().delete()
        TransactionStatus.objects.all().delete()
        self.stdout.write('  → Данные очищены')

    def create_regions_and_cities(self):
        """Создание 20 городов в разных регионах России"""
        self.stdout.write('\n📍 Создание регионов и городов...')

        # Данные: регион -> (код, [список городов])
        regions_data = {
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
        }

        regions_created = 0
        cities_created = 0

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

    def create_categories(self):
        """Создание категорий помещений"""
        self.stdout.write('\n📂 Создание категорий помещений...')

        categories = [
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

        created_count = 0
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

    def create_pricing_periods(self):
        """Создание периодов аренды"""
        self.stdout.write('\n⏱️  Создание периодов аренды...')

        periods = [
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

    def create_statuses(self):
        """Создание статусов бронирования и транзакций"""
        self.stdout.write('\n📊 Создание статусов...')

        booking_statuses = [
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

        transaction_statuses = [
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

    def create_admin_user(self):
        """Создание администратора"""
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

    def create_test_owners(self):
        """Создание тестовых владельцев помещений"""
        self.stdout.write('\n👥 Создание тестовых владельцев...')

        owners_data = [
            ('owner1', 'Иван', 'Петров', 'ООО "Бизнес Центр"'),
            ('owner2', 'Анна', 'Сидорова', 'ИП Сидорова А.В.'),
            ('owner3', 'Сергей', 'Козлов', 'Арендодатель'),
        ]

        for username, first_name, last_name, company in owners_data:
            owner, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@interior.ru',
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_type': 'owner',
                    'company': company,
                    'phone': f'+7 (9{random.randint(10,99)}) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}'
                }
            )
            if created:
                owner.set_password('owner123')
                owner.save()
                UserProfile.objects.get_or_create(user=owner)

        self.stdout.write(f'  → Владельцев создано: {User.objects.filter(user_type="owner").count()}')

    def create_spaces(self, count):
        """Создание тестовых помещений"""
        self.stdout.write(f'\n🏢 Создание {count} помещений...')

        owners = list(User.objects.filter(user_type__in=['owner', 'admin']))
        cities = list(City.objects.filter(is_active=True))
        categories = list(SpaceCategory.objects.filter(is_active=True))
        periods = list(PricingPeriod.objects.all())

        if not owners or not cities or not categories:
            self.stdout.write(self.style.ERROR('  → Недостаточно данных для создания помещений'))
            return

        # Шаблоны названий и описаний
        name_templates = {
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

        streets = [
            'ул. Ленина', 'пр. Мира', 'ул. Пушкина', 'ул. Гагарина',
            'ул. Советская', 'пр. Победы', 'ул. Центральная',
            'бульвар Строителей', 'ул. Кирова', 'пр. Революции',
            'ул. Садовая', 'ул. Молодёжная', 'пр. Космонавтов'
        ]

        descriptions = {
            'office': 'Светлое офисное помещение с современным ремонтом. Высокие потолки, панорамные окна, кондиционирование. Есть кухня и санузел. Подходит для IT-компаний, юридических фирм, консалтинга.',
            'loft': 'Стильное лофт-пространство в бывшем промышленном здании. Высокие потолки, кирпичные стены, открытые коммуникации. Идеально для творческих меропр��ятий, съёмок, выставок.',
            'coworking': 'Современное рабочее пространство с высокоскоростным интернетом. Есть переговорные, лаунж-зона, кухня. Включены все коммунальны�� услуги. Подходит для фрилансеров и небольших команд.',
            'conference': 'Оборудованный зал для проведения конференций, семинаров и тренингов. Проектор, экран, флипчарт, маркерная доска. Возможность организации кофе-брейков.',
            'photo-studio': 'Профессиональная фотостудия с полным комплектом оборудования. Циклорама, импульсный и постоянный свет, набор фонов. Гримёрка, зона отдыха для моделей.',
            'showroom': 'Элегантное выставочное пространство на первой линии. Панорамные витрины, качественное освещение. Идеально для презентаций, выставок, pop-up магазинов.',
            'warehouse': 'Сухое отапливаемое складское помещение. Удобный подъезд для транспорта, погрузочно-разгрузочная зона. Охрана, видеонаблюдение 24/7.',
            'retail': 'Торговое помещение в месте с высокой проходимостью. Первая линия домов, отдельный вход, витринные окна. Все коммуникации подведены.',
        }

        created_count = 0
        for i in range(count):
            city = random.choice(cities)
            category = random.choice(categories)
            owner = random.choice(owners)
            street = random.choice(streets)

            # Генерируем название
            templates = name_templates.get(category.slug, ['Помещение "{city}"'])
            title = random.choice(templates).format(city=city.name, street=street)

            # Генерируем slug
            base_slug = slugify(unidecode(f"{city.name} {category.slug} {i}"))
            slug = base_slug

            # Параметры помещения зависят от категории
            if category.slug in ['warehouse', 'retail']:
                area = random.randint(50, 1000)
            elif category.slug in ['conference', 'photo-studio']:
                area = random.randint(30, 150)
            else:
                area = random.randint(20, 300)

            capacity = max(2, area // 5)

            space, created = Space.objects.get_or_create(
                slug=slug,
                defaults={
                    'title': title,
                    'address': f'{street}, {random.randint(1, 200)}',
                    'city': city,
                    'category': category,
                    'area_sqm': Decimal(str(area)),
                    'max_capacity': capacity,
                    'description': descriptions.get(category.slug, 'Помещение для аренды'),
                    'owner': owner,
                    'is_active': True,
                    'is_featured': random.random() < 0.2,  # 20% рекомендуемых
                    'views_count': random.randint(0, 500),
                }
            )

            if created:
                # Генерируем цены для каждого периода
                base_hour_price = random.randint(300, 3000)

                price_multipliers = {
                    'hour': 1,
                    'day': 6,  # ~6 часов по выгодной цене
                    'week': 30,  # ~5 дней
                    'month': 100,  # ~3.3 недели
                }

                for period in periods:
                    multiplier = price_multipliers.get(period.name, 1)
                    price = base_hour_price * multiplier
                    # Добавляем небольшую вариацию
                    price = int(price * random.uniform(0.9, 1.1))
                    # Округляем до красивого числа
                    price = round(price / 100) * 100

                    SpacePrice.objects.create(
                        space=space,
                        period=period,
                        price=Decimal(str(max(price, 100))),
                        is_active=True
                    )

                created_count += 1

            if (i + 1) % 10 == 0:
                self.stdout.write(f'  → Создано {i + 1} помещений...')

        self.stdout.write(f'  → Всего создано помещений: {created_count}')

    def print_summary(self):
        """Вывод итоговой статистики"""
        self.stdout.write(self.style.MIGRATE_HEADING('\n📈 ИТОГОВАЯ СТАТИСТИКА:'))
        self.stdout.write(f'   • Регионов: {Region.objects.count()}')
        self.stdout.write(f'   • Городов: {City.objects.count()}')
        self.stdout.write(f'   • Категорий: {SpaceCategory.objects.count()}')
        self.stdout.write(f'   • Периодов аренды: {PricingPeriod.objects.count()}')
        self.stdout.write(f'   • Пользователей: {User.objects.count()}')
        self.stdout.write(f'   • Помещений: {Space.objects.count()}')
        self.stdout.write(f'   • Цен: {SpacePrice.objects.count()}')
        self.stdout.write('')
