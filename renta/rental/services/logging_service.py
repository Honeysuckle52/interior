"""
====================================================================
СЕРВИС ЛОГИРОВАНИЯ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит сервис для централизованного логирования
действий пользователей на сайте. Логирование включает в себя
авторизацию, изменения данных, бронирования и другие действия.

Основные функции:
- log_action: Основная функция создания записей в журнале действий
- log_login: Специализированная функция логирования входа пользователя
- log_logout: Специализированная функция логирования выхода пользователя
- get_client_ip: Вспомогательная функция получения IP-адреса клиента

Особенности:
- Поддержка логирования как авторизованных, так и анонимных пользователей
- Запись IP-адреса, User-Agent и других метаданных запроса
- Фиксация изменений объектов в формате JSON
- Обработка ошибок логирования без прерывания основного потока
====================================================================
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from django.http import HttpRequest
    from ..models import CustomUser, ActionLog

logger = logging.getLogger('rental')


class LoggingService:
    """
    Сервис логирования действий пользователей.

    Предоставляет статические методы для записи различных типов
    пользовательских действий в системный журнал для последующего
    аудита и анализа.
    """

    @staticmethod
    def get_client_ip(request: 'HttpRequest') -> Optional[str]:
        """
        Получить реальный IP-адрес клиента из HTTP запроса.

        Корректно обрабатывает случаи использования прокси-серверов
        через заголовок HTTP_X_FORWARDED_FOR.

        Args:
            request (HttpRequest): Объект HTTP запроса Django

        Returns:
            Optional[str]: IP-адрес клиента или None если не удалось определить
        """
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
        Создать запись в журнале действий.

        Основная функция для логирования любых действий пользователей.
        Автоматически извлекает дополнительную информацию из запроса
        (IP-адрес, User-Agent) при его наличии.

        Args:
            user (Optional[CustomUser]): Пользователь, совершивший действие
                (None для анонимных действий)
            action_type (str): Тип действия из ActionLog.ActionType
                (например: 'create', 'update', 'delete', 'login', 'logout')
            model_name (str): Название модели, с которой связано действие
                (например: 'Booking', 'Space', 'UserProfile')
            object_id (Optional[int]): ID объекта, с которым связано действие
            object_repr (str): Строковое представление объекта
                (например: "Помещение 'Конференц-зал'")
            changes (Optional[dict]): Словарь изменений объекта
                (используется для действий update)
            request (Optional[HttpRequest]): HTTP запрос для получения
                IP-адреса и User-Agent

        Returns:
            ActionLog: Созданная запись в журнале действий

        Raises:
            Exception: Возможны любые исключения при создании записи в БД
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
        """
        Логирование успешного входа пользователя.

        Args:
            user (CustomUser): Пользователь, который вошел в систему
            request (HttpRequest): HTTP запрос, связанный с входом

        Note:
            В случае ошибки логирования, ошибка записывается в лог,
            но не прерывает основной поток выполнения
        """
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
        """
        Логирование выхода пользователя из системы.

        Args:
            user (CustomUser): Пользователь, который вышел из системы
            request (HttpRequest): HTTP запрос, связанный с выходом

        Note:
            В случае ошибки логирования, ошибка записывается в лог,
            но не прерывает основной поток выполнения
        """
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