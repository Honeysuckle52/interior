# =============================================================================
# ФАЙЛ: rental/services/__init__.py
# =============================================================================
# НАЗНАЧЕНИЕ:
#   Инициализационный файл для пакета сервисов бизнес-логики.
#   Экспортирует основные сервисы для использования в представлениях.
#
# АРХИТЕКТУРА:
#   Сервисы содержат бизнес-логику, вынесенную из представлений.
#   Это упрощает тестирование и повторное использование кода.
#
# ДОСТУПНЫЕ СЕРВИСЫ:
#   BookingService - Создание, подтверждение, отмена бронирований
#   SpaceService   - Фильтрация, поиск, избранное
#   UserService    - Профиль, статистика пользователя
#   StatusService  - Управление статусами бронирований
#   ProfanityFilter - Фильтрация матерных слов
#
# ДОПОЛНИТЕЛЬНЫЕ МОДУЛИ:
#   email_service   - Отправка email уведомлений
#   logging_service - Логирование действий пользователей
#   validators      - Валидаторы (телефон и др.) [DEPRECATED: use core.validators]
#
# ПРОЕКТ: ООО "ИНТЕРЬЕР" - Сайт аренды помещений
# =============================================================================

"""
СЕРВИСЫ - бизнес-логика приложения
"""

from .booking_service import BookingService
from .space_service import SpaceService
from .user_service import UserService
from .status_service import StatusService, StatusCodes, StatusDefaults
from .profanity_filter import (
    contains_profanity,
    validate_comment,
    censor_text,
    normalize_text,
)

__all__ = [
    'BookingService',
    'SpaceService',
    'UserService',
    'StatusService',
    'StatusCodes',
    'StatusDefaults',
    # Функции фильтрации мата
    'contains_profanity',
    'validate_comment',
    'censor_text',
    'normalize_text',
]
