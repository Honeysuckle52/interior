"""
ФОРМЫ - модульная структура
"""

from .auth import CustomUserCreationForm, CustomAuthenticationForm
from .profile import UserProfileForm, UserProfileExtendedForm
from .spaces import SpaceFilterForm, SpaceForm, SpaceImageForm
from .bookings import BookingForm
from .reviews import ReviewForm

__all__ = [
    # Аутентификация
    'CustomUserCreationForm',
    'CustomAuthenticationForm',
    # Профиль
    'UserProfileForm',
    'UserProfileExtendedForm',
    # Помещения
    'SpaceFilterForm',
    'SpaceForm',
    'SpaceImageForm',
    # Бронирования
    'BookingForm',
    # Отзывы
    'ReviewForm',
]
