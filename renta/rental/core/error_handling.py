"""
====================================================================
ЦЕНТРАЛИЗОВАННАЯ ОБРАБОТКА ОШИБОК
====================================================================
Унифицированные паттерны обработки ошибок для всего приложения.
====================================================================
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional, Type, TypeVar

from django.contrib import messages
from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.shortcuts import redirect

from .exceptions import AppError, ServiceError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)

T = TypeVar('T')
ViewFunc = TypeVar('ViewFunc', bound=Callable[..., HttpResponse])


# =============================================================================
# КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ
# =============================================================================

@contextmanager
def handle_service_errors(
    operation_name: str = 'operation',
    reraise: bool = True
) -> Generator[None, None, None]:
    """
    Контекстный менеджер для обработки ошибок в сервисах.

    Args:
        operation_name: Название операции для логирования
        reraise: Перебрасывать ли исключение после логирования

    Usage:
        with handle_service_errors('create booking'):
            booking = BookingService.create_booking(...)
    """
    try:
        yield
    except AppError:
        # Наши исключения просто пробрасываем
        raise
    except DatabaseError as e:
        logger.error(f"Database error during {operation_name}: {e}", exc_info=True)
        if reraise:
            raise ServiceError(f'Ошибка базы данных при {operation_name}')
    except Exception as e:
        logger.error(f"Unexpected error during {operation_name}: {e}", exc_info=True)
        if reraise:
            raise ServiceError(f'Неожиданная ошибка при {operation_name}')


@contextmanager
def safe_operation(
    default: T = None,
    log_errors: bool = True,
    operation_name: str = 'operation'
) -> Generator[None, None, T]:
    """
    Контекстный менеджер для безопасного выполнения операций.

    Возвращает default при любой ошибке вместо выброса исключения.

    Args:
        default: Значение по умолчанию при ошибке
        log_errors: Логировать ли ошибки
        operation_name: Название операции для логирования

    Usage:
        with safe_operation(default=[]):
            items = get_items()
    """
    try:
        yield
    except Exception as e:
        if log_errors:
            logger.error(f"Error during {operation_name}: {e}", exc_info=True)
        return default


# =============================================================================
# ДЕКОРАТОРЫ ДЛЯ VIEWS
# =============================================================================

def handle_view_exceptions(
    redirect_url: str = 'home',
    error_message: str = 'Произошла ошибка',
    allowed_exceptions: tuple[Type[Exception], ...] = (Http404,)
) -> Callable[[ViewFunc], ViewFunc]:
    """
    Декоратор для унифицированной обработки исключений в views.

    Args:
        redirect_url: URL для редиректа при ошибке
        error_message: Сообщение об ошибке для пользователя
        allowed_exceptions: Исключения, которые пробрасываются дальше

    Returns:
        Декоратор
    """
    def decorator(view_func: ViewFunc) -> ViewFunc:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            try:
                return view_func(request, *args, **kwargs)
            except allowed_exceptions:
                raise
            except AppError as e:
                # Наши исключения с понятными сообщениями
                messages.error(request, e.message)
                return redirect(redirect_url)
            except Exception as e:
                logger.error(
                    f"Error in {view_func.__name__}: {e}",
                    exc_info=True,
                    extra={
                        'view': view_func.__name__,
                        'user': getattr(request.user, 'username', 'anonymous'),
                        'path': request.path,
                    }
                )
                messages.error(request, error_message)
                return redirect(redirect_url)
        return wrapper  # type: ignore
    return decorator


def handle_ajax_exceptions(view_func: ViewFunc) -> ViewFunc:
    """
    Декоратор для обработки исключений в AJAX views.

    Args:
        view_func: Функция представления

    Returns:
        Обёрнутая функция
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return view_func(request, *args, **kwargs)
        except AppError as e:
            return JsonResponse({
                'success': False,
                'error': e.message,
                'code': e.code
            }, status=400)
        except Exception as e:
            logger.error(
                f"AJAX error in {view_func.__name__}: {e}",
                exc_info=True
            )
            return JsonResponse({
                'success': False,
                'error': 'Произошла ошибка при обработке запроса'
            }, status=500)
    return wrapper  # type: ignore


# =============================================================================
# ХЕЛПЕРЫ ДЛЯ VIEWS
# =============================================================================

def add_error_message(
    request: HttpRequest,
    error: Exception,
    default_message: str = 'Произошла ошибка'
) -> None:
    """
    Добавить сообщение об ошибке в messages framework.

    Args:
        request: HTTP запрос
        error: Исключение
        default_message: Сообщение по умолчанию
    """
    if isinstance(error, AppError):
        messages.error(request, error.message)
    else:
        messages.error(request, default_message)


def log_view_error(
    view_name: str,
    error: Exception,
    request: Optional[HttpRequest] = None,
    extra: Optional[dict[str, Any]] = None
) -> None:
    """
    Логировать ошибку в view с контекстом.

    Args:
        view_name: Название view
        error: Исключение
        request: HTTP запрос (опционально)
        extra: Дополнительные данные для лога
    """
    log_extra = extra or {}

    if request:
        log_extra.update({
            'view': view_name,
            'user': getattr(request.user, 'username', 'anonymous'),
            'path': request.path,
            'method': request.method,
        })

    logger.error(
        f"Error in {view_name}: {error}",
        exc_info=True,
        extra=log_extra
    )
