"""
КОМАНДА ДЛЯ ЗАПОЛНЕНИЯ БАЗЫ ДАННЫХ ТЕСТОВЫМИ ДАННЫМИ
ООО "ИНТЕРЬЕР" - Аренда помещений

Запуск: python manage.py populate_db
Опции:
    --clear     Очистить существующие данные перед заполнением
"""

from __future__ import annotations

import os
import random
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from unidecode import unidecode
# Импортируем shutil для копирования файлов
import shutil

from ...models import (
    Region, City, SpaceCategory, PricingPeriod, Space, SpaceImage,
    SpacePrice, BookingStatus, TransactionStatus, Review
)

User = get_user_model()

# Константы
MIN_PRICE: int = 100
PRICE_ROUND_BASE: int = 100

# Директория для хранения тестовых изображений (относительно корня проекта)
# Убедитесь, что эта папка существует и содержит ваши файлы
TEST_IMAGES_DIR: str = os.path.join(settings.BASE_DIR, 'media', 'spaces', '2025', '12')


class Command(BaseCommand):
    """Команда для заполнения базы данных тестовыми данными."""

    help = 'Заполняет базу данных начальными данными для сайта аренды помещений'

    # 1. Словарь для указания имен файлов изображений
    IMAGE_FILENAMES: dict[str, list[str]] = {
        'bc-moscow-city-tower': ['office_1_1.jpg', 'office_1_2.jpg', 'office_1_3.jpg'],
        'loft-krasny-oktyabr': ['loft_1_1.jpg', 'loft_1_2.jpg', 'loft_1_3.jpg'],
        'coworking-nevsky': ['coworking_1_1.jpg', 'coworking_1_2.jpg', 'coworking_1_3.jpg'],
        'conference-akademichesky': ['conference_1_1.jpg'],
        'photo-studio-irkutsk': ['photo_1_1.jpg', 'photo_1_2.jpg', 'photo_1_3.jpg'],
        'showroom-kazan': ['showroom_1_1.jpg', 'showroom_1_2.jpg'],
        'office-baikal-business': ['office_2_1.jpg', 'office_2_2.jpg', 'office_2_3.jpg'],
        'warehouse-nizny': ['warehouse_1_1.jpg'],
        'retail-irkutsk-center': ['retail_1_1.jpg'],
        'creative-loft-novosib': ['loft_2_1.jpg'],
    }


    def add_arguments(self, parser) -> None:
        """Добавление аргументов командной строки."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед заполнением'
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
                self.create_admin()
                self.create_moderators()
                self.create_test_users()
                self.create_spaces()
                self.create_test_reviews()

            self.stdout.write(self.style.SUCCESS(
                '\n✓ База данных успешно заполнена!\n'
            ))
            self.print_summary()

        except Exception as e:
            # Убедимся, что при ошибке отображается полный путь к файлу
            raise CommandError(f'Ошибка при заполнении БД: {e}')

    def clear_data(self) -> None:
        """Очистка существующих данных."""
        self.stdout.write('Очистка существующих данных...')
        Review.objects.all().delete()
        SpaceImage.objects.all().delete()
        SpacePrice.objects.all().delete()
        Space.objects.all().delete()
        SpaceCategory.objects.all().delete()
        City.objects.all().delete()
        Region.objects.all().delete()
        PricingPeriod.objects.all().delete()
        BookingStatus.objects.all().delete()
        TransactionStatus.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write('  → Данные очищены')

    def create_regions_and_cities(self) -> None:
        """Создание только городов-миллионников и Иркутска (9 городов)."""
        self.stdout.write('\n📍 Создание регионов и городов-миллионников (9 городов)...')

        # Города для создания: Москва, Санкт-Петербург, Новосибирск, Казань, Нижний Новгород,
        # Омск, Красноярск, Пермь, Иркутск (всего 9)
        regions_data: dict[str, tuple[str, list[str]]] = {
            'Москва': ('77', ['Москва']),
            'Санкт-Петербург': ('78', ['Санкт-Петербург']),
            'Новосибирская область': ('54', ['Новосибирск']),
            'Республика Татарстан': ('16', ['Казань']),
            'Нижегородская область': ('52', ['Нижний Новгород']),
            'Омская область': ('55', ['Омск']),
            'Красноярский край': ('24', ['Красноярск']),
            'Пермский край': ('59', ['Пермь']),
            'Иркутская область': ('38', ['Иркутск']),
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

    # ... (Остальные методы: create_categories, create_pricing_periods, create_statuses,
    # create_admin, create_moderators, create_test_users остаются без изменений)
    
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

    def create_admin(self) -> None:
        """Создание администратора."""
        self.stdout.write('\n👤 Создание администратора...')

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@interior.ru',
                'first_name': 'Администратор',
                'last_name': 'Системы',
                'user_type': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'phone': '+7 (999) 123-45-67',
                'email_verified': True
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
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
                    'phone': f'+7 (9{random.randint(10, 99)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}',
                    'email_verified': True
                }
            )
            if created:
                moderator.set_password('Moderator123!')
                moderator.save()
                created_count += 1

        self.stdout.write(f'  → Создано модераторов: {created_count}')

    def create_test_users(self) -> None:
        """Создание 50 уникальных тестовых пользователей."""
        self.stdout.write('\n👤 Создание 50 тестовых пользователей...')

        # Русские имена и фамилии для генерации уникальных пользователей
        first_names_male = [
            'Александр', 'Михаил', 'Максим', 'Артём', 'Даниил', 'Иван', 'Кирилл',
            'Дмитрий', 'Андрей', 'Егор', 'Никита', 'Илья', 'Алексей', 'Матвей',
            'Тимофей', 'Роман', 'Владимир', 'Ярослав', 'Фёдор', 'Георгий', 'Константин',
            'Лев', 'Николай', 'Степан', 'Марк'
        ]
        first_names_female = [
            'Анастасия', 'Мария', 'Анна', 'Виктория', 'Полина', 'Елизавета', 'Екатерина',
            'Ксения', 'Валерия', 'Александра', 'Вероника', 'Алиса', 'Варвара', 'Дарья',
            'София', 'Арина', 'Диана', 'Ульяна', 'Милана', 'Ева', 'Таисия', 'Кира',
            'Маргарита', 'Алина', 'Юлия'
        ]
        last_names = [
            'Иванов', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев', 'Петров', 'Соколов',
            'Михайлов', 'Новиков', 'Фёдоров', 'Морозов', 'Волков', 'Алексеев', 'Лебедев',
            'Семёнов', 'Егоров', 'Павлов', 'Козлов', 'Степанов', 'Николаев', 'Орлов',
            'Андреев', 'Макаров', 'Никитин', 'Захаров', 'Зайцев', 'Соловьёв', 'Борисов',
            'Яковлев', 'Григорьев', 'Романов', 'Воробьёв', 'Сергеев', 'Кузьмин', 'Фролов',
            'Александров', 'Дмитриев', 'Королёв', 'Гусев', 'Киселёв', 'Ильин', 'Максимов',
            'Поляков', 'Сорокин', 'Виноградов', 'Ковалёв', 'Белов', 'Медведев', 'Антонов', 'Тарасов'
        ]

        companies = [
            'ООО "Альфа Групп"', 'ИП Технологии', 'ЗАО "Бизнес Решения"', 'ООО "Старт"',
            'Фриланс', 'ООО "Инновации"', 'ИП Консалтинг', 'ООО "Медиа Плюс"',
            'Студия дизайна', 'ООО "Финанс Групп"', 'IT-компания', 'Маркетинговое агентство',
            'ООО "Строй Сервис"', 'Рекламное агентство', 'ООО "Логистика"', ''
        ]

        domains = ['mail.ru', 'yandex.ru', 'gmail.com', 'bk.ru', 'inbox.ru', 'list.ru']

        created_count: int = 0
        used_combinations = set()

        for i in range(50):
            # Генерируем уникальную комбинацию имя-фамилия
            while True:
                is_female = random.random() > 0.5
                first_name = random.choice(first_names_female if is_female else first_names_male)
                last_name = random.choice(last_names)

                # Для женщин добавляем окончание "а" к фамилии
                if is_female and not last_name.endswith('о'):
                    last_name = last_name + 'а'

                combination = (first_name, last_name)
                if combination not in used_combinations:
                    used_combinations.add(combination)
                    break

            # Генерируем username на основе имени
            username = f"user_{slugify(unidecode(first_name.lower()))}_{i+1}"

            # Генерируем email
            email_name = slugify(unidecode(f"{first_name}.{last_name}")).replace('-', '.')
            domain = random.choice(domains)
            email = f"{email_name}@{domain}"

            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_type': 'user',
                    'is_staff': False,
                    'is_superuser': False,
                    'company': random.choice(companies),
                    'phone': f'+7 (9{random.randint(10, 99)}) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}',
                    'email_verified': random.random() > 0.3  # 70% с подтверждённым email
                }
            )
            if created:
                user.set_password('User123!')
                user.save()
                created_count += 1

        self.stdout.write(f'  → Создано пользователей: {created_count}')
        if created_count > 0:
            self.stdout.write(self.style.WARNING(
                '  → Логин: user_<имя>_<номер> / Пароль: User123!'
            ))

    def create_spaces(self) -> None:
        """
        Создание 10 реальных помещений с точными координатами.
        Обновлено для использования только созданных городов.
        """
        self.stdout.write('\n🏢 Создание 10 реальных помещений...')

        admin = User.objects.filter(user_type='admin').first()
        if not admin:
            admin = User.objects.filter(is_superuser=True).first()

        periods = list(PricingPeriod.objects.all())

        if not admin:
            self.stdout.write(self.style.ERROR('  → Администратор не найден'))
            return
            
        # Список доступных городов для распределения помещений
        city_names = ['Москва', 'Санкт-Петербург', 'Новосибирск', 'Казань', 
                      'Нижний Новгород', 'Омск', 'Красноярск', 'Пермь', 'Иркутск']
        
        # 10 реальных помещений с точными адресами и координатами, привязанные к доступным городам
        spaces_data = [
            # 1. Москва - Офис
            {
                'title': 'Бизнес-центр "Москва-Сити" Tower',
                'slug': 'bc-moscow-city-tower',
                'city': 'Москва',
                'address': 'Пресненская наб., 12, Башня Федерация',
                'category': 'office',
                'area': 150,
                'capacity': 30,
                'latitude': 55.749558,
                'longitude': 37.537168,
                'description': 'Престижный офис в самом сердце делового центра Москва-Сити. Панорамные окна с видом на город, современная отделка класса А+. Высокоскоростной интернет, система климат-контроля, круглосуточная охрана. Идеально для представительств крупных компаний.',
                'is_featured': True,
                'prices': {'hour': 5000, 'day': 35000, 'week': 180000, 'month': 650000}
            },
            # 2. Москва - Лофт
            {
                'title': 'Лофт "Красный Октябрь"',
                'slug': 'loft-krasny-oktyabr',
                'city': 'Москва',
                'address': 'Берсеневская наб., 6, стр. 3',
                'category': 'loft',
                'area': 200,
                'capacity': 80,
                'latitude': 55.742793,
                'longitude': 37.610401,
                'description': 'Атмосферный лофт на территории бывшей шоколадной фабрики. Кирпичные стены, высокие потолки 6 метров, панорамные окна с видом на Кремль. Подходит для мероприятий, съёмок, выставок и корпоративов.',
                'is_featured': True,
                'prices': {'hour': 8000, 'day': 50000, 'week': 280000, 'month': 900000}
            },
            # 3. Санкт-Петербург - Коворкинг
            {
                'title': 'Коворкинг "Невский Проспект"',
                'slug': 'coworking-nevsky',
                'city': 'Санкт-Петербург',
                'address': 'Невский пр., 100',
                'category': 'coworking',
                'area': 80,
                'capacity': 25,
                'latitude': 59.932485,
                'longitude': 30.352536,
                'description': 'Современный коворкинг в историческом центре Петербурга. Эргономичные рабочие места, переговорные комнаты, зона отдыха с кофе-машиной. Wi-Fi 1 Гбит/с, круглосуточный доступ. Идеально для IT-специалистов и стартапов.',
                'is_featured': True,
                'prices': {'hour': 400, 'day': 2500, 'week': 12000, 'month': 35000}
            },
            # 4. Новосибирск - Конференц-зал
            {
                'title': 'Конференц-зал "Академический"',
                'slug': 'conference-akademichesky',
                'city': 'Новосибирск',
                'address': 'Красный пр., 65',
                'category': 'conference',
                'area': 120,
                'capacity': 60,
                'latitude': 55.030204,
                'longitude': 82.920430,
                'description': 'Профессиональный конференц-зал для проведения семинаров, тренингов и деловых встреч. Проектор 4K, звуковая система, видеоконференцсвязь. Возможность организации кофе-брейков и банкетов.',
                'is_featured': False,
                'prices': {'hour': 2500, 'day': 15000, 'week': 70000, 'month': 200000}
            },
            # 5. Иркутск (был Екатеринбург) - Фотостудия
            {
                'title': 'Фотостудия "Байкал-Свет"',
                'slug': 'photo-studio-irkutsk',
                'city': 'Иркутск',
                'address': 'ул. Ленина, 7',
                'category': 'photo-studio',
                'area': 90,
                'capacity': 15,
                'latitude': 52.285856,
                'longitude': 104.288599,
                'description': 'Профессиональная фотостудия с полным комплектом оборудования. Циклорама, зона для предметной съёмки, гримёрная комната. Набор фонов и реквизита включён в стоимость.',
                'is_featured': True,
                'prices': {'hour': 2000, 'day': 12000, 'week': 55000, 'month': 180000}
            },
            # 6. Казань - Шоу-рум
            {
                'title': 'Шоу-рум "Галерея Искусств"',
                'slug': 'showroom-kazan',
                'city': 'Казань',
                'address': 'ул. Баумана, 48',
                'category': 'showroom',
                'area': 180,
                'capacity': 50,
                'latitude': 55.789425,
                'longitude': 49.114242,
                'description': 'Элегантное выставочное пространство на главной пешеходной улице Казани. Панорамные витрины, профессиональное освещение, климат-контроль. Идеально для презентаций, выставок, pop-up магазинов.',
                'is_featured': False,
                'prices': {'hour': 3000, 'day': 18000, 'week': 90000, 'month': 300000}
            },
            # 7. Иркутск - Офис
            {
                'title': 'Офис "Байкал Бизнес"',
                'slug': 'office-baikal-business',
                'city': 'Иркутск',
                'address': 'ул. Карла Маркса, 40',
                'category': 'office',
                'area': 75,
                'capacity': 15,
                'latitude': 52.283468,
                'longitude': 104.280586,
                'description': 'Уютный офис в историческом центре Иркутска. Свежий ремонт, кондиционирование, оптоволоконный интернет. Отдельный вход, парковка. Подходит для небольших команд и представительств.',
                'is_featured': True,
                'prices': {'hour': 800, 'day': 5000, 'week': 25000, 'month': 80000}
            },
            # 8. Нижний Новгород - Склад
            {
                'title': 'Склад "Логистик-Центр"',
                'slug': 'warehouse-nizny',
                'city': 'Нижний Новгород',
                'address': 'ул. Ларина, 15',
                'category': 'warehouse',
                'area': 500,
                'capacity': 10,
                'latitude': 56.298660,
                'longitude': 43.936350,
                'description': 'Современный отапливаемый склад класса B+. Высота потолков 8 метров, пол с антипылевым покрытием. Погрузочно-разгрузочная зона, охрана 24/7, видеонаблюдение.',
                'is_featured': False,
                'prices': {'hour': 500, 'day': 3500, 'week': 20000, 'month': 70000}
            },
            # 9. Иркутск (был Ростов-на-Дону) - Торговое помещение
            {
                'title': 'Торговое помещение "Иркутск-Центр"',
                'slug': 'retail-irkutsk-center',
                'city': 'Иркутск',
                'address': 'ул. Литвинова, 17',
                'category': 'retail',
                'area': 100,
                'capacity': 30,
                'latitude': 52.285579,
                'longitude': 104.288283,
                'description': 'Торговое помещение на первой линии в центре Иркутска. Большие витринные окна, отдельный вход, высокая проходимость. Все коммуникации, кондиционирование.',
                'is_featured': False,
                'prices': {'hour': 1500, 'day': 10000, 'week': 50000, 'month': 180000}
            },
            # 10. Новосибирск (был Самара) - Лофт
            {
                'title': 'Креативный лофт "Фабрика"',
                'slug': 'creative-loft-novosib',
                'city': 'Новосибирск',
                'address': 'ул. Ленина, 12',
                'category': 'loft',
                'area': 250,
                'capacity': 100,
                'latitude': 55.030571,
                'longitude': 82.915077,
                'description': 'Просторный индустриальный лофт в бывшем заводском здании. Открытые балки, кирпичные стены, панорамное остекление. Идеально для мероприятий, концертов, выставок и корпоративных праздников.',
                'is_featured': True,
                'prices': {'hour': 4000, 'day': 25000, 'week': 130000, 'month': 450000}
            },
        ]

        created_count: int = 0
        total_images: int = 0

        for space_data in spaces_data:
            # Находим город и категорию
            try:
                city = City.objects.get(name=space_data['city'])
                category = SpaceCategory.objects.get(slug=space_data['category'])
            except (City.DoesNotExist, SpaceCategory.DoesNotExist) as e:
                # Этот блок не должен срабатывать после исправления, но оставим для отладки
                self.stdout.write(self.style.ERROR(f"  → ОШИБКА: {space_data['title']} - {e}"))
                continue

            space, created = Space.objects.get_or_create(
                slug=space_data['slug'],
                defaults={
                    'title': space_data['title'],
                    'address': space_data['address'],
                    'city': city,
                    'category': category,
                    'area_sqm': Decimal(str(space_data['area'])),
                    'max_capacity': space_data['capacity'],
                    'description': space_data['description'],
                    'owner': admin,
                    'is_active': True,
                    'is_featured': space_data['is_featured'],
                    'views_count': random.randint(50, 500),
                    'latitude': Decimal(str(space_data['latitude'])),
                    'longitude': Decimal(str(space_data['longitude'])),
                }
            )

            if created:
                # Создаём цены
                for period in periods:
                    price = space_data['prices'].get(period.name, 1000)
                    SpacePrice.objects.create(
                        space=space,
                        period=period,
                        price=Decimal(str(price)),
                        is_active=True
                    )

                # Создаём изображения по имени файла
                images_count = self._create_space_images(space, space_data['slug'])
                total_images += images_count
                self.stdout.write(f'  → Создано: {space_data["title"]}')
            else:
                self.stdout.write(f'  → Пропущено (уже существует): {space_data["title"]}')


        self.stdout.write(f'  → Всего создано помещений: {created_count}')
        self.stdout.write(f'  → Всего создано изображений: {total_images}')

    def _create_space_images(self, space: Space, space_slug: str) -> int:
        """
        Создаёт записи об изображениях, привязывая их к существующим файлам
        в папке media/spaces/2025/12. Не создает дубликатов файлов.
        """
        filenames = self.IMAGE_FILENAMES.get(space_slug, [])

        if not filenames:
            self.stdout.write(self.style.WARNING(f'    Нет файлов изображений для: {space.title} ({space_slug})'))
            return 0

        created_images = 0

        # Относительная папка внутри MEDIA_ROOT, где лежат фото
        # Мы берем её жестко, так как она определена в TEST_IMAGES_DIR как константа
        relative_folder = 'spaces/2025/12'

        for i, filename in enumerate(filenames):
            # Полный путь только для проверки существования файла
            full_path = os.path.join(TEST_IMAGES_DIR, filename)

            if not os.path.exists(full_path):
                self.stdout.write(self.style.ERROR(f'    Ошибка: Файл не найден по пути: {full_path}'))
                continue

            try:
                # Создаём объект, но пока не сохраняем в БД
                image = SpaceImage(
                    space=space,
                    alt_text=f'{space.title} - фото {i + 1}',
                    is_primary=(i == 0),
                    sort_order=i
                )

                # ГЛАВНОЕ ИЗМЕНЕНИЕ:
                # Мы вручную формируем путь относительно MEDIA_ROOT.
                # Django хранит в БД именно строку пути.
                # Используем forward slash '/', так как это стандарт для путей в БД Django даже на Windows.
                image_relative_path = f'{relative_folder}/{filename}'

                # Присваиваем атрибуту name поля ImageField этот путь
                image.image.name = image_relative_path

                # Сохраняем только запись в БД (метод save модели, а не поля файла)
                image.save()

                created_images += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    Не удалось привязать файл {filename}: {e}'))

        return created_images

    # 3. Удаляем или комментируем ненужный метод _generate_placeholder_image
    # (Оригинальный метод закомментирован на случай, если он понадобится)
    def _generate_placeholder_image(self, query: str) -> Optional[ContentFile]:
        """Генерирует placeholder изображение. (Теперь не используется)"""
        # try:
        #     from urllib.request import urlopen
        #     from urllib.error import URLError

        #     # Используем placeholder.com для генерации изображений
        #     seed = hash(query) % 10000
        #     url = f"https://picsum.photos/seed/{seed}/800/600"

        #     response = urlopen(url, timeout=15)
        #     image_data = response.read()
        #     return ContentFile(image_data)
        # except Exception as e:
        #     self.stdout.write(self.style.WARNING(f'    Не удалось создать изображение: {e}'))
        return None

    def create_test_reviews(self) -> None:
        """Создание тестовых отзывов от пользователей к помещениям."""
        self.stdout.write('\n⭐ Создание тестовых отзывов...')

        # Получаем всех обычных пользователей и все помещения
        users = list(User.objects.filter(user_type='user'))
        spaces = list(Space.objects.all())

        if not users or not spaces:
            self.stdout.write(self.style.WARNING('  → Нет пользователей или помещений для создания отзывов'))
            return

        # Варианты комментариев для разных оценок
        comments_5_stars = [
            'Отличное помещение! Всё на высшем уровне, рекомендую всем. Очень удобное расположение и приятный персонал.',
            'Превосходное место для работы. Современный ремонт, быстрый интернет, отличная инфраструктура вокруг.',
            'Идеальное помещение для нашей компании. Всё чисто, аккуратно, хорошее освещение. Будем арендовать снова!',
            'Прекрасный офис с панорамными окнами. Отличная вентиляция, удобная парковка. Очень довольны выбором.',
            'Замечательное пространство! Провели мероприятие на 50 человек, всё прошло идеально. Спасибо!',
            'Лучший коворкинг в городе! Уютная атмосфера, вкусный кофе, отзывчивый персонал.',
            'Снимали для фотосессии - результат превзошёл ожидания. Естественное освещение просто великолепное.',
            'Отличная студия с профессиональным оборудованием. Всё работает как часы!',
        ]

        comments_4_stars = [
            'Хорошее помещение, почти всё понравилось. Единственное - хотелось бы лучше кондиционирование.',
            'В целом отлично, удобное расположение. Немного шумно от соседей, но в целом комфортно.',
            'Достойный вариант за свои деньги. Ремонт свежий, всё чисто. Минус - парковка маловата.',
            'Неплохое место для работы. WiFi стабильный, мебель удобная. Хотелось бы больше розеток.',
            'Хороший офис, рекомендую. Мелкие недочёты есть, но в целом всё устраивает.',
            'Приятное помещение с хорошим видом. Немного далеко от метро, но это компенсируется качеством.',
        ]

        comments_3_stars = [
            'Средний вариант. Есть свои плюсы и минусы. За эту цену ожидал большего.',
            'Нормальное помещение, но ничего особенного. Базовые условия соблюдены.',
            'Для разовых встреч подойдёт, но для постоянной работы искал бы что-то получше.',
            'Обычный офис без изысков. Всё работает, но атмосферы не хватает.',
        ]

        comments_2_stars = [
            'Не очень понравилось. Ремонт устаревший, интернет периодически пропадал.',
            'Ожидал большего за такую цену. Кондиционер шумит, мебель потёртая.',
            'Расположение хорошее, но состояние помещения оставляет желать лучшего.',
        ]

        comments_1_star = [
            'Разочарован полностью. Фото не соответствуют реальности, много проблем.',
            'Не рекомендую. Грязно, шумно, проблемы с электричеством.',
        ]

        comments_by_rating = {
            5: comments_5_stars,
            4: comments_4_stars,
            3: comments_3_stars,
            2: comments_2_stars,
            1: comments_1_star,
        }

        created_count = 0

        # Для каждого помещения создаём от 3 до 8 отзывов
        for space in spaces:
            num_reviews = random.randint(3, 8)
            # Выбираем случайных пользователей для этого помещения
            reviewers = random.sample(users, min(num_reviews, len(users)))

            for user in reviewers:
                # Проверяем, не оставлял ли уже этот пользователь отзыв
                if Review.objects.filter(space=space, author=user).exists():
                    continue

                # Распределение оценок: больше положительных
                rating_weights = [5, 5, 5, 5, 4, 4, 4, 3, 3, 2, 1]
                rating = random.choice(rating_weights)

                comments = comments_by_rating.get(rating, comments_3_stars)
                comment = random.choice(comments)

                Review.objects.create(
                    space=space,
                    author=user,
                    rating=rating,
                    comment=comment,
                    is_approved=True  # Автоматически одобряем тестовые отзывы
                )
                created_count += 1

        self.stdout.write(f'  → Создано отзывов: {created_count}')

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
        self.stdout.write(f'   • Отзывов: {Review.objects.count()}')
        self.stdout.write('')