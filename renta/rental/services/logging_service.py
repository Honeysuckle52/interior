"""
СЕРВИС ЛОГИРОВАНИЯ
Единая точка для логирования действий пользователей
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from django.http import HttpRequest
    from ..models import CustomUser, ActionLog

logger = logging.getLogger('rental')


class LoggingService:
    """Сервис логирования действий пользователей"""

    @staticmethod
    def get_client_ip(request: 'HttpRequest') -> Optional[str]:
        """Получить IP клиента из запроса"""
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def log_action(
            user: Optional['CustomUser'],
            action_type: str,
            model_name: str,
            object_id: Optional[int] = None,
            object_repr: str = '',
            changes: Optional[dict] = None,
            request: Optional['HttpRequest'] = None
    ) -> 'ActionLog':
        """
        Создать запись в журнале действий

        Args:
            user: Пользователь (None для анонимов)
            action_type: Тип действия (ActionLog.ActionType)
            model_name: Название модели
            object_id: ID объекта
            object_repr: Строковое представление
            changes: Словарь изменений
            request: HTTP запрос для IP и User-Agent
        """
        from ..models import ActionLog

        ip_address = None
        user_agent = ''

        if request:
            ip_address = LoggingService.get_client_ip(request)
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

    @staticmethod
    def log_login(user: 'CustomUser', request: 'HttpRequest') -> None:
        """Логирование входа"""
        from ..models import ActionLog
        try:
            LoggingService.log_action(
                user=user,
                action_type=ActionLog.ActionType.LOGIN,
                model_name='auth',
                object_repr=f'Вход: {user.username}',
                request=request
            )
        except Exception as e:
            logger.error(f"Ошибка логирования входа: {e}")

    @staticmethod
    def log_logout(user: 'CustomUser', request: 'HttpRequest') -> None:
        """Логирование выхода"""
        from ..models import ActionLog
        try:
            LoggingService.log_action(
                user=user,
                action_type=ActionLog.ActionType.LOGOUT,
                model_name='auth',
                object_repr=f'Выход: {user.username}',
                request=request
            )
        except Exception as e:
            logger.error(f"Ошибка логирования выхода: {e}")
