"""
ФОРМЫ - модульная структура
"""

from .auth import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    AdminUserCreationForm,
    AdminUserChangeForm,
    PasswordResetRequestForm,
    PasswordResetConfirmForm,
    EmailVerificationCodeForm,  # Добавлен экспорт
)
from .profile import UserProfileForm, UserProfileExtendedForm, ChangePasswordForm
from .spaces import SpaceFilterForm, SpaceForm, SpaceImageForm
from .bookings import BookingForm, BookingFilterForm
from .reviews import ReviewForm

__all__ = [
    # Аутентификация
    'CustomUserCreationForm',
    'CustomAuthenticationForm',
    'AdminUserCreationForm',
    'AdminUserChangeForm',
    'PasswordResetRequestForm',
    'PasswordResetConfirmForm',
    'EmailVerificationCodeForm',  # Добавлен экспорт
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
