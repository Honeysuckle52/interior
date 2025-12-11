# =============================================================================
# ФАЙЛ: rental/views/__init__.py
# =============================================================================
# НАЗНАЧЕНИЕ:
#   Инициализационный файл для пакета представлений (views).
#   Экспортирует все view-функции для использования в urls.py
#
# СТРУКТУРА ПРЕДСТАВЛЕНИЙ:
#   home.py       - Главная страница
#   spaces.py     - Каталог помещений, детальная страница
#   auth.py       - Вход, регистрация, подтверждение email
#   account.py    - Личный кабинет, профиль
#   bookings.py   - Создание и управление бронированиями
#   reviews.py    - Отзывы пользователей
#   favorites.py  - Избранное (AJAX)
#   users.py      - Управление пользователями (модератор)
#   categories.py - Управление категориями (модератор)
#   admin_panel.py - Панель управления для модераторов
#
# ПРОЕКТ: ООО "ИНТЕРЬЕР" - Сайт аренды помещений
# =============================================================================

"""
ПРЕДСТАВЛЕНИЯ (VIEWS) - модульная структура
Импорт всех views из отдельных модулей
"""

from .home import home
from .spaces import spaces_list, space_detail
from .auth import CustomLoginView, register_view, logout_view
from .account import dashboard, profile, my_bookings, my_favorites, view_user_profile, public_user_profile
from .favorites import toggle_favorite
from .bookings import (
    create_booking, booking_detail, cancel_booking,
    confirm_booking, reject_booking, manage_bookings, get_price_for_period
)
from .reviews import create_review, edit_review, admin_delete_review, approve_review, manage_reviews
from .users import manage_users, user_detail, block_user, unblock_user, verify_user_email
from .admin_panel import admin_panel

__all__ = [
    # -------------------------------------------------------------------------
    # ГЛАВНАЯ СТРАНИЦА
    # -------------------------------------------------------------------------
    'home',

    # -------------------------------------------------------------------------
    # ПОМЕЩЕНИЯ
    # -------------------------------------------------------------------------
    'spaces_list',
    'space_detail',

    # -------------------------------------------------------------------------
    # АУТЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    'CustomLoginView',
    'register_view',
    'logout_view',

    # -------------------------------------------------------------------------
    # ЛИЧНЫЙ КАБИНЕТ
    # -------------------------------------------------------------------------
    'dashboard',
    'profile',
    'my_bookings',
    'my_favorites',
    'view_user_profile',
    'public_user_profile',  # Добавлен экспорт public_user_profile

    # -------------------------------------------------------------------------
    # ИЗБРАННОЕ (AJAX)
    # -------------------------------------------------------------------------
    'toggle_favorite',

    # -------------------------------------------------------------------------
    # БРОНИРОВАНИЯ
    # -------------------------------------------------------------------------
    'create_booking',
    'booking_detail',
    'cancel_booking',
    'confirm_booking',
    'reject_booking',
    'manage_bookings',
    'get_price_for_period',

    # -------------------------------------------------------------------------
    # ОТЗЫВЫ
    # -------------------------------------------------------------------------
    'create_review',
    'edit_review',
    'admin_delete_review',
    'approve_review',
    'manage_reviews',

    # -------------------------------------------------------------------------
    # УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (МОДЕРАТОР)
    # -------------------------------------------------------------------------
    'manage_users',
    'user_detail',
    'block_user',
    'unblock_user',
    'verify_user_email',

    # -------------------------------------------------------------------------
    # ПАНЕЛЬ УПРАВЛЕНИЯ
    # -------------------------------------------------------------------------
    'admin_panel',
]
