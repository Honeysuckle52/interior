"""
ФОРМЫ - модульная структура
"""

from .auth import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    AdminUserCreationForm,  # добавлен экспорт
    AdminUserChangeForm,    # добавлен экспорт
)
from .profile import UserProfileForm, UserProfileExtendedForm, ChangePasswordForm
from .spaces import SpaceFilterForm, SpaceForm, SpaceImageForm
from .bookings import BookingForm, BookingFilterForm
from .reviews import ReviewForm

__all__ = [
    # Аутентификация
    'CustomUserCreationForm',
    'CustomAuthenticationForm',
    'AdminUserCreationForm',   # добавлен в экспорт
    'AdminUserChangeForm',     # добавлен в экспорт
    # Профиль
    'UserProfileForm',
    'UserProfileExtendedForm',
    'ChangePasswordForm',
    # Помещения
    'SpaceFilterForm',
    'SpaceForm',
    'SpaceImageForm',
    # Бронирования
    'BookingForm',
    'BookingFilterForm',
    # Отзывы
    'ReviewForm',
]
