"""
MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ДЕЙСТВИЙ
"""

import json
import logging
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out

from .models import ActionLog, CustomUser

logger = logging.getLogger('rental')


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """Получить IP адрес клиента."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_action(
    user: Optional[CustomUser],
    action_type: str,
    model_name: str,
    object_id: Optional[int] = None,
    object_repr: str = '',
    changes: Optional[dict] = None,
    request: Optional[HttpRequest] = None
) -> ActionLog:
    """
    Создать запись в журнале действий.

    Args:
        user: Пользователь (может быть None для анонимов)
        action_type: Тип действия из ActionLog.ActionType
        model_name: Название модели
        object_id: ID объекта
        object_repr: Строковое представление объекта
        changes: Словарь с изменениями
        request: HTTP запрос для получения IP и User-Agent

    Returns:
        Созданная запись ActionLog
    """
    ip_address = None
    user_agent = ''

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    return ActionLog.objects.create(
        user=user,
        action_type=action_type,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr[:255],
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent
    )


class ActionLoggingMiddleware(MiddlewareMixin):
    """
    Middleware для автоматического логирования действий.
    Логирует POST/PUT/DELETE запросы.
    """

    # Пути, которые не нужно логировать
    EXCLUDED_PATHS = (
        '/admin/jsi18n/',
        '/static/',
        '/media/',
        '/favicon.ico',
    )

    def process_response(
        self,
        request: HttpRequest,
        response: HttpResponse
    ) -> HttpResponse:
        """Обработка ответа для логирования."""
        # Пропускаем исключенные пути
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return response

        # Логируем только успешные изменяющие запросы
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if 200 <= response.status_code < 400:
                self._log_request(request, response)

        return response

    def _log_request(self, request: HttpRequest, response: HttpResponse) -> None:
        """Внутренний метод для логирования запроса."""
        user = request.user if request.user.is_authenticated else None

        # Определяем тип действия по методу
        action_map = {
            'POST': ActionLog.ActionType.CREATE,
            'PUT': ActionLog.ActionType.UPDATE,
            'PATCH': ActionLog.ActionType.UPDATE,
            'DELETE': ActionLog.ActionType.DELETE,
        }
        action_type = action_map.get(request.method, ActionLog.ActionType.OTHER)

        # Получаем название модели из пути
        path_parts = request.path.strip('/').split('/')
        model_name = path_parts[0] if path_parts else 'unknown'

        try:
            log_action(
                user=user,
                action_type=action_type,
                model_name=model_name,
                object_repr=request.path,
                request=request
            )
        except Exception as e:
            logger.error(f"Error logging action: {e}")


# Обработчики сигналов для логирования входа/выхода
def log_user_login(sender, request, user, **kwargs):
    """Логирование входа пользователя."""
    try:
        log_action(
            user=user,
            action_type=ActionLog.ActionType.LOGIN,
            model_name='auth',
            object_repr=f'Вход пользователя {user.username}',
            request=request
        )
    except Exception as e:
        logger.error(f"Error logging login: {e}")


def log_user_logout(sender, request, user, **kwargs):
    """Логирование выхода пользователя."""
    try:
        log_action(
            user=user,
            action_type=ActionLog.ActionType.LOGOUT,
            model_name='auth',
            object_repr=f'Выход пользователя {user.username}',
            request=request
        )
    except Exception as e:
        logger.error(f"Error logging logout: {e}")


# Подключаем сигналы
user_logged_in.connect(log_user_login)
user_logged_out.connect(log_user_logout)
