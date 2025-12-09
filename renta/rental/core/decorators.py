"""
====================================================================
ЦЕНТРАЛИЗОВАННЫЕ ДЕКОРАТОРЫ
====================================================================
Унифицированные декораторы для обработки ошибок, прав доступа
и логирования действий.
====================================================================
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

ViewFunc = TypeVar('ViewFunc', bound=Callable[..., HttpResponse])


def moderator_required(view_func: ViewFunc) -> ViewFunc:
    """
    Декоратор для проверки прав модератора или администратора.

    Args:
        view_func: Функция представления

    Returns:
        Обернутая функция
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
    Декоратор для унифицированной обработки ошибок.

    Args:
        redirect_to: URL для редиректа при ошибке
        error_message: Сообщение пользователю
        log_prefix: Префикс для логов

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
        Обернутая функция
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


def log_action(
    action_type: str,
    model_name: str,
    get_object_repr: Optional[Callable[[Any], str]] = None
) -> Callable[[ViewFunc], ViewFunc]:
    """
    Декоратор для логирования действий пользователя.

    Args:
        action_type: Тип действия (create, update, delete и т.д.)
        model_name: Название модели
        get_object_repr: Функция для получения строкового представления объекта

    Returns:
        Декоратор
    """
    def decorator(view_func: ViewFunc) -> ViewFunc:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            from ..services.logging_service import LoggingService

            result = view_func(request, *args, **kwargs)

            # Логируем только успешные действия
            if hasattr(result, 'status_code') and 200 <= result.status_code < 400:
                try:
                    object_repr = ''
                    object_id = kwargs.get('pk')

                    if get_object_repr and object_id:
                        object_repr = get_object_repr(object_id)

                    LoggingService.log_action(
                        user=request.user if request.user.is_authenticated else None,
                        action_type=action_type,
                        model_name=model_name,
                        object_id=object_id,
                        object_repr=object_repr,
                        request=request
                    )
                except Exception as e:
                    logger.warning(f"Failed to log action: {e}")

            return result
        return wrapper  # type: ignore
    return decorator
