"""
====================================================================
CORE МОДУЛЬ - БАЗОВЫЕ УТИЛИТЫ И ХЕЛПЕРЫ
====================================================================
Централизованные утилиты, валидаторы и хелперы для всего приложения.
====================================================================
"""

from .validators import (
    validate_russian_phone,
    normalize_phone,
    format_phone_display,
    PhoneValidator,
    phone_validator,
)
from .helpers import (
    parse_int,
    parse_float,
    parse_bool,
    format_price,
    format_area,
    truncate_text,
    calculate_duration_text,
    get_rating_stars,
    generate_unique_slug,
)
from .pagination import (
    paginate,
    PaginationMixin,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)
from .decorators import (
    moderator_required,
    handle_view_errors,
    handle_ajax_errors,
    log_action,
)
from .exceptions import (
    AppError,
    ValidationError,
    ServiceError,
    NotFoundError,
    PermissionError,
)

__all__ = [
    # Валидаторы
    'validate_russian_phone',
    'normalize_phone',
    'format_phone_display',
    'PhoneValidator',
    'phone_validator',
    # Хелперы
    'parse_int',
    'parse_float',
    'parse_bool',
    'format_price',
    'format_area',
    'truncate_text',
    'calculate_duration_text',
    'get_rating_stars',
    'generate_unique_slug',
    # Пагинация
    'paginate',
    'PaginationMixin',
    'DEFAULT_PAGE_SIZE',
    'MAX_PAGE_SIZE',
    # Декораторы
    'moderator_required',
    'handle_view_errors',
    'handle_ajax_errors',
    'log_action',
    # Исключения
    'AppError',
    'ValidationError',
    'ServiceError',
    'NotFoundError',
    'PermissionError',
]
