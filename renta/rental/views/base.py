"""
====================================================================
БАЗОВЫЕ КЛАССЫ И МИКСИНЫ ДЛЯ ПРЕДСТАВЛЕНИЙ
====================================================================
Этот файл содержит базовые классы и миксины для унификации
функциональности представлений: обработка ошибок, пагинация,
оптимизация запросов и проверка прав доступа.

Основные классы:
- BaseViewMixin: Базовый миксин с обработкой ошибок и логированием
- PaginationMixin: Миксин для унифицированной пагинации
- OptimizedQueryMixin: Миксин для оптимизации запросов к БД
- ModeratorRequiredMixin: Миксин проверки прав модератора

====================================================================
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from django.contrib import messages
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

# Type alias для функций view
ViewFunc = TypeVar('ViewFunc', bound=Callable[..., HttpResponse])


# =============================================================================
# КОНСТАНТЫ ПАГИНАЦИИ
# =============================================================================

DEFAULT_PAGE_SIZE: int = 12
MAX_PAGE_SIZE: int = 100
MIN_PAGE_SIZE: int = 5


# =============================================================================
# ДЕКОРАТОРЫ
# =============================================================================

def moderator_required(view_func: ViewFunc) -> ViewFunc:
    """
    Декоратор для проверки прав модератора или администратора.

    Args:
        view_func: Функция представления для обертывания

    Returns:
        Функция-обертка, проверяющая права доступа
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            messages.error(request, 'Необходимо войти в систему')
            return redirect('login')
        if not request.user.can_moderate:
            messages.error(request, 'У вас нет прав для доступа к этой странице')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper  # type: ignore


def handle_view_errors(
    redirect_to: str = 'home',
    error_message: str = 'Произошла ошибка',
    log_prefix: str = 'View error'
) -> Callable[[ViewFunc], ViewFunc]:
    """
    Декоратор для унифицированной обработки ошибок в представлениях.

    Args:
        redirect_to: URL для редиректа при ошибке
        error_message: Сообщение об ошибке для пользователя
        log_prefix: Префикс для логирования

    Returns:
        Декоратор
    """
    def decorator(view_func: ViewFunc) -> ViewFunc:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            try:
                return view_func(request, *args, **kwargs)
            except Exception as e:
                logger.error(f"{log_prefix}: {e}", exc_info=True)
                messages.error(request, error_message)
                return redirect(redirect_to)
        return wrapper  # type: ignore
    return decorator


def handle_ajax_errors(view_func: ViewFunc) -> ViewFunc:
    """
    Декоратор для обработки ошибок в AJAX представлениях.

    Args:
        view_func: Функция представления

    Returns:
        Функция-обертка с обработкой ошибок
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"AJAX error in {view_func.__name__}: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Произошла ошибка при обработке запроса'
            }, status=500)
    return wrapper  # type: ignore


# =============================================================================
# МИКСИНЫ
# =============================================================================

class PaginationMixin:
    """
    Миксин для унифицированной пагинации.

    Предоставляет метод для пагинации queryset с обработкой
    некорректных номеров страниц и настраиваемым размером страницы.
    """

    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE
    page_param: str = 'page'
    per_page_param: str = 'per_page'

    @classmethod
    def paginate_queryset(
        cls,
        queryset: QuerySet,
        request: HttpRequest,
        page_size: Optional[int] = None
    ) -> tuple[Page, Paginator]:
        """
        Пагинация queryset с обработкой ошибок.

        Args:
            queryset: QuerySet для пагинации
            request: HTTP запрос
            page_size: Размер страницы (опционально)

        Returns:
            Кортеж (Page объект, Paginator объект)
        """
        # Определяем размер страницы
        if page_size is None:
            try:
                page_size = int(request.GET.get(cls.per_page_param, cls.default_page_size))
                page_size = max(MIN_PAGE_SIZE, min(page_size, cls.max_page_size))
            except (ValueError, TypeError):
                page_size = cls.default_page_size

        paginator = Paginator(queryset, page_size)
        page_number = request.GET.get(cls.page_param, 1)

        try:
            page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            page = paginator.get_page(1)

        return page, paginator


def paginate(
    queryset: QuerySet,
    request: HttpRequest,
    page_size: int = DEFAULT_PAGE_SIZE
) -> tuple[Page, Paginator]:
    """
    Функциональный хелпер для пагинации.

    Args:
        queryset: QuerySet для пагинации
        request: HTTP запрос
        page_size: Размер страницы

    Returns:
        Кортеж (Page объект, Paginator объект)
    """
    # Получаем размер из параметров запроса или используем переданный
    try:
        per_page = int(request.GET.get('per_page', page_size))
        per_page = max(MIN_PAGE_SIZE, min(per_page, MAX_PAGE_SIZE))
    except (ValueError, TypeError):
        per_page = page_size

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page', 1)

    try:
        page = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.get_page(1)

    return page, paginator


# =============================================================================
# ХЕЛПЕРЫ ДЛЯ ПАРСИНГА ПАРАМЕТРОВ
# =============================================================================

def parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Безопасный парсинг целого числа.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Целое число или значение по умолчанию
    """
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Безопасный парсинг числа с плавающей точкой.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Число или значение по умолчанию
    """
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_bool(value: Any, default: bool = False) -> bool:
    """
    Безопасный парсинг булева значения.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Булево значение
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)
