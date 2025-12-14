"""
====================================================================
ПАНЕЛЬ УПРАВЛЕНИЯ ДЛЯ АДМИНИСТРАТОРОВ И МОДЕРАТОРОВ
САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления для административной панели сайта,
предоставляя единую точку входа для всех административных функций
и централизованное управление контентом.

Основные представления:
- admin_panel: Главная страница панели управления со статистикой

Вспомогательные функции:
- is_moderator_or_admin: Проверка прав доступа пользователя

Функционал панели управления:
- Общая статистика по всем разделам сайта
- Быстрый доступ к основным разделам управления
- Визуальные индикаторы и бейджи для элементов, требующих внимания
- Адаптивная проверка прав доступа для разных типов пользователей

Контекстные секции управления:
1. Помещения - Управление объявлениями о помещениях
2. Категории - Управление категориями помещений
3. Бронирования - Управление заявками на бронирование
4. Отзывы - Модерация отзывов пользователей
5. Пользователи - Управление учетными записями
6. Отчёты и аналитика - Статистика и отчёты по системе (только для staff и модераторов)
7. Django Admin - Расширенная панель администратора (только для staff)
====================================================================
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.db.models import Count, Q, Avg

from ..models import Space, SpaceCategory, Booking, Review, CustomUser, City


def is_moderator_or_admin(user) -> bool:
    """
    Проверка, имеет ли пользователь права модератора или администратора.

    Проверяет различные флаги и типы пользователей для определения
    наличия прав доступа к административной панели.

    Args:
        user: Объект пользователя для проверки

    Returns:
        bool: True если пользователь имеет права модератора или администратора,
             False в противном случае
    """
    return user.is_authenticated and (user.is_staff or user.is_moderator or user.is_admin_user)


@login_required
def admin_panel(request: HttpRequest) -> HttpResponse:
    """
    Главная страница панели управления для администраторов и модераторов.

    Отображает сводную статистику по всем разделам сайта и предоставляет
    быстрый доступ к основным функциям управления через визуальные карточки.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрендеренный шаблон панели управления или страница 403
                     при отсутствии прав доступа

    Template:
        admin_panel/index.html

    Context:
        - spaces_stats: Статистика по помещениям
        - categories_stats: Статистика по категориям
        - bookings_stats: Статистика по бронированиям
        - reviews_stats: Статистика по отзывам
        - users_stats: Статистика по пользователям
        - cities_stats: Статистика по городам
        - management_sections: Список секций управления с метаданными
    """
    if not is_moderator_or_admin(request.user):
        from django.contrib import messages
        messages.error(request, 'У вас нет доступа к панели управления.')
        return render(request, 'errors/403.html', status=403)

    # Статистика помещений
    spaces_stats = {
        'total': Space.objects.count(),
        'active': Space.objects.filter(is_active=True).count(),
        'inactive': Space.objects.filter(is_active=False).count(),
        'featured': Space.objects.filter(is_featured=True).count(),
    }

    # Статистика категорий
    categories_stats = {
        'total': SpaceCategory.objects.count(),
        'active': SpaceCategory.objects.filter(is_active=True).count(),
        'inactive': SpaceCategory.objects.filter(is_active=False).count(),
    }

    # Статистика бронирований
    bookings_stats = {
        'total': Booking.objects.count(),
        'pending': Booking.objects.filter(status__code='pending').count(),
        'confirmed': Booking.objects.filter(status__code='confirmed').count(),
        'completed': Booking.objects.filter(status__code='completed').count(),
        'cancelled': Booking.objects.filter(status__code='cancelled').count(),
    }

    # Статистика отзывов
    reviews_stats = {
        'total': Review.objects.count(),
        'pending': Review.objects.filter(is_approved=False).count(),
        'approved': Review.objects.filter(is_approved=True).count(),
        'avg_rating': Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg'] or 0,
    }

    # Статистика пользователей
    users_stats = {
        'total': CustomUser.objects.count(),
        'active': CustomUser.objects.filter(is_active=True).count(),
        'blocked': CustomUser.objects.filter(is_blocked=True).count(),
        'verified': CustomUser.objects.filter(email_verified=True).count(),
        'admins': CustomUser.objects.filter(Q(is_staff=True) | Q(user_type='admin')).count(),
        'moderators': CustomUser.objects.filter(user_type='moderator').count(),
    }

    # Статистика городов
    cities_stats = {
        'total': City.objects.count(),
        'active': City.objects.filter(is_active=True).count(),
    }

    # Секции управления с иконками и описаниями
    management_sections = [
        {
            'title': 'Помещения',
            'description': 'Управление объявлениями о помещениях',
            'icon': 'fa-building',
            'url': 'manage_spaces',
            'color': 'gold',
            'stats': [
                {'label': 'Всего', 'value': spaces_stats['total']},
                {'label': 'Активных', 'value': spaces_stats['active']},
                {'label': 'Рекомендуемых', 'value': spaces_stats['featured']},
            ],
            'actions': [
                {'label': 'Добавить помещение', 'url': 'add_space', 'icon': 'fa-plus'},
            ]
        },
        {
            'title': 'Категории',
            'description': 'Управление категориями помещений',
            'icon': 'fa-folder',
            'url': 'manage_categories',
            'color': 'info',
            'stats': [
                {'label': 'Всего', 'value': categories_stats['total']},
                {'label': 'Активных', 'value': categories_stats['active']},
                {'label': 'Отключено', 'value': categories_stats['inactive']},
            ],
            'actions': [
                {'label': 'Добавить категорию', 'url': 'add_category', 'icon': 'fa-plus'},
            ]
        },
        {
            'title': 'Бронирования',
            'description': 'Управление заявками на бронирование',
            'icon': 'fa-calendar-check',
            'url': 'manage_bookings',
            'color': 'success',
            'stats': [
                {'label': 'Всего', 'value': bookings_stats['total']},
                {'label': 'Ожидают', 'value': bookings_stats['pending']},
                {'label': 'Подтверждено', 'value': bookings_stats['confirmed']},
            ],
            'badge': bookings_stats['pending'] if bookings_stats['pending'] > 0 else None,
            'actions': []
        },
        {
            'title': 'Отзывы',
            'description': 'Модерация отзывов пользователей',
            'icon': 'fa-comments',
            'url': 'manage_reviews',
            'color': 'warning',
            'stats': [
                {'label': 'Всего', 'value': reviews_stats['total']},
                {'label': 'На модерации', 'value': reviews_stats['pending']},
                {'label': 'Средний рейтинг', 'value': f"{reviews_stats['avg_rating']:.1f}"},
            ],
            'badge': reviews_stats['pending'] if reviews_stats['pending'] > 0 else None,
            'actions': []
        },
        {
            'title': 'Пользователи',
            'description': 'Управление учётными записями',
            'icon': 'fa-users',
            'url': 'manage_users',
            'color': 'primary',
            'stats': [
                {'label': 'Всего', 'value': users_stats['total']},
                {'label': 'Активных', 'value': users_stats['active']},
                {'label': 'Заблокировано', 'value': users_stats['blocked']},
            ],
            'actions': []
        },
    ]

    if request.user.is_staff or request.user.is_moderator:
        management_sections.append({
            'title': 'Отчёты и аналитика',
            'description': 'Статистика и отчёты по системе',
            'icon': 'fa-chart-bar',
            'url': None,
            'external_url': '/admin/reports/',
            'color': 'info',
            'stats': [],
            'actions': []
        })

    # Добавляем ссылку на Django Admin только для staff пользователей
    if request.user.is_staff:
        management_sections.append({
            'title': 'Django Admin',
            'description': 'Расширенная панель администратора',
            'icon': 'fa-cog',
            'url': None,
            'external_url': '/admin/',
            'color': 'danger',
            'stats': [],
            'actions': []
        })

    context = {
        'spaces_stats': spaces_stats,
        'categories_stats': categories_stats,
        'bookings_stats': bookings_stats,
        'reviews_stats': reviews_stats,
        'users_stats': users_stats,
        'cities_stats': cities_stats,
        'management_sections': management_sections,
    }

    return render(request, 'admin_panel/index.html', context)
