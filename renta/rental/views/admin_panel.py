"""
ПАНЕЛЬ УПРАВЛЕНИЯ ДЛЯ АДМИНИСТРАТОРОВ И МОДЕРАТОРОВ
Единая точка входа для всех административных функций
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.db.models import Count, Q, Avg

from ..models import Space, SpaceCategory, Booking, Review, CustomUser, City


def is_moderator_or_admin(user) -> bool:
    """Проверка, является ли пользователь модератором или администратором"""
    return user.is_authenticated and (user.is_staff or user.is_moderator or user.is_admin_user)


@login_required
def admin_panel(request: HttpRequest) -> HttpResponse:
    """
    Главная страница панели управления для администраторов и модераторов.
    Отображает статистику и ссылки на все разделы управления.
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

    # Добавляем ссылку на Django Admin только для staff
    if request.user.is_staff:
        management_sections.append({
            'title': 'Django Admin',
            'description': 'Расширенная панель администратора',
            'icon': 'fa-cog',
            'url': None,  # Внешняя ссылка
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
