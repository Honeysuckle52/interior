"""
ФОРМЫ - модульная структура
"""

from .auth import CustomUserCreationForm, CustomAuthenticationForm
from .profile import UserProfileForm, UserProfileExtendedForm, ChangePasswordForm  # добавлен ChangePasswordForm
from .spaces import SpaceFilterForm, SpaceForm, SpaceImageForm
from .bookings import BookingForm, BookingFilterForm  # добавлен BookingFilterForm
from .reviews import ReviewForm

__all__ = [
    # Аутентификация
    'CustomUserCreationForm',
    'CustomAuthenticationForm',
    # Профиль
    'UserProfileForm',
    'UserProfileExtendedForm',
    'ChangePasswordForm',  # добавлен в экспорт
    # Помещения
    'SpaceFilterForm',
    'SpaceForm',
    'SpaceImageForm',
    # Бронирования
    'BookingForm',
    'BookingFilterForm',  # добавлен в экспорт
    # Отзывы
    'ReviewForm',
]
