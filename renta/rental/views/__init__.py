"""
ПРЕДСТАВЛЕНИЯ (VIEWS) - модульная структура
Импорт всех views из отдельных модулей
"""

from .home import home
from .spaces import spaces_list, space_detail
from .auth import CustomLoginView, register_view, logout_view
from .account import dashboard, profile, my_bookings, my_favorites, view_user_profile
from .favorites import toggle_favorite
from .bookings import create_booking, booking_detail, cancel_booking
from .reviews import create_review, edit_review, admin_delete_review, approve_review, manage_reviews
from .users import manage_users, user_detail, block_user, unblock_user, verify_user_email

__all__ = [
    # Главная
    'home',
    # Помещения
    'spaces_list',
    'space_detail',
    # Аутентификация
    'CustomLoginView',
    'register_view',
    'logout_view',
    # Личный кабинет
    'dashboard',
    'profile',
    'my_bookings',
    'my_favorites',
    'view_user_profile',
    # Избранное
    'toggle_favorite',
    # Бронирования
    'create_booking',
    'booking_detail',
    'cancel_booking',
    # Отзывы
    'create_review',
    'edit_review',
    'admin_delete_review',
    'approve_review',
    'manage_reviews',
    'manage_users',
    'user_detail',
    'block_user',
    'unblock_user',
    'verify_user_email',
]
