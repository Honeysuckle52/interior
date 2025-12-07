"""
MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ДЕЙСТВИЙ
"""

import logging

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out

from .models import ActionLog
from .services.logging_service import LoggingService

logger = logging.getLogger('rental')


class ActionLoggingMiddleware(MiddlewareMixin):
    """Middleware для автоматического логирования POST/PUT/DELETE запросов"""

    EXCLUDED_PATHS = (
        '/admin/jsi18n/',
        '/static/',
        '/media/',
        '/favicon.ico',
    )

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Логирование успешных изменяющих запросов"""
        if any(request.path.startswith(p) for p in self.EXCLUDED_PATHS):
            return response

        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if 200 <= response.status_code < 400:
                self._log_request(request)

        return response

    def _log_request(self, request: HttpRequest) -> None:
        """Внутренний метод логирования"""
        user = request.user if request.user.is_authenticated else None

        action_map = {
            'POST': ActionLog.ActionType.CREATE,
            'PUT': ActionLog.ActionType.UPDATE,
            'PATCH': ActionLog.ActionType.UPDATE,
            'DELETE': ActionLog.ActionType.DELETE,
        }
        action_type = action_map.get(request.method, ActionLog.ActionType.OTHER)

        path_parts = request.path.strip('/').split('/')
        model_name = path_parts[0] if path_parts else 'unknown'

        try:
            LoggingService.log_action(
                user=user,
                action_type=action_type,
                model_name=model_name,
                object_repr=request.path,
                request=request
            )
        except Exception as e:
            logger.error(f"Ошибка логирования: {e}")


# Обработчики сигналов входа/выхода
def log_user_login(sender, request, user, **kwargs):
    """Логирование входа"""
    LoggingService.log_login(user, request)


def log_user_logout(sender, request, user, **kwargs):
    """Логирование выхода"""
    if user:
        LoggingService.log_logout(user, request)


user_logged_in.connect(log_user_login)
user_logged_out.connect(log_user_logout)
