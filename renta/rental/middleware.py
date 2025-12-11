"""
====================================================================
MIDDLEWARE ДЛЯ ЛОГИРОВАНИЯ ДЕЙСТВИЙ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит middleware и вспомогательные функции для
автоматического логирования действий пользователей на сайте,
включая HTTP запросы и события аутентификации.

Основные компоненты:
- ActionLoggingMiddleware: Middleware для логирования HTTP запросов
- BlockedUserMiddleware: Middleware для проверки заблокированных пользователей
- log_action: Утилитарная функция для создания записей в журнале действий
- get_client_ip: Вспомогательная функция для получения IP-адреса клиента
- log_user_login, log_user_logout: Обработчики сигналов для логирования входа/выхода

Функционал:
- Автоматическое логирование всех POST, PUT, PATCH, DELETE запросов
- Логирование событий входа и выхода пользователей через сигналы Django
- Получение и сохранение метаданных (IP-адрес, User-Agent)
- Исключение несущественных путей из логирования для оптимизации
- Проверка и разблокировка заблокированных пользователей

Особенности:
- Использование сигналов Django для отслеживания событий аутентификации
- Пропуск статических файлов и служебных путей для снижения нагрузки
- Безопасная обработка ошибок логирования без прерывания основного потока
- Интеграция с моделью ActionLog для сохранения записей в БД
====================================================================
"""

import json
import logging
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages

from .models import ActionLog, CustomUser

logger = logging.getLogger('rental')


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Получить реальный IP-адрес клиента из HTTP запроса.

    Корректно обрабатывает случаи использования прокси-серверов
    через заголовок HTTP_X_FORWARDED_FOR.

    Args:
        request (HttpRequest): Объект HTTP запроса Django

    Returns:
        Optional[str]: IP-адрес клиента или None если не удалось определить
    """
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

    Утилитарная функция для создания стандартизированных записей
    в журнале действий с автоматическим извлечением метаданных из запроса.

    Args:
        user (Optional[CustomUser]): Пользователь, совершивший действие
            (None для анонимных действий)
        action_type (str): Тип действия из ActionLog.ActionType
            (например: 'create', 'update', 'delete', 'login', 'logout')
        model_name (str): Название модели, с которой связано действие
        object_id (Optional[int]): ID объекта, с которым связано действие
        object_repr (str): Строковое представление объекта
        changes (Optional[dict]): Словарь с изменениями объекта
        request (Optional[HttpRequest]): HTTP запрос для получения
            IP-адреса и User-Agent

    Returns:
        ActionLog: Созданная запись в журнале действий

    Raises:
        Exception: Возможны любые исключения при создании записи в БД
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


class BlockedUserMiddleware(MiddlewareMixin):
    """
    Middleware для проверки заблокированных пользователей.

    Если пользователь заблокирован (is_blocked=True), он автоматически
    выбрасывается из сессии и перенаправляется на страницу входа.
    """

    # Пути, которые доступны даже для заблокированных
    ALLOWED_PATHS = (
        '/static/',
        '/media/',
        '/favicon.ico',
        '/logout/',
        '/login/',
    )

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Проверка на блокировку при каждом запросе."""
        # Пропускаем разрешённые пути
        if any(request.path.startswith(path) for path in self.ALLOWED_PATHS):
            return None

        # Проверяем наличие атрибута user (добавляется AuthenticationMiddleware)
        if not hasattr(request, 'user'):
            return None

        # Проверяем только аутентифицированных пользователей
        if request.user.is_authenticated:
            try:
                # Перезагружаем пользователя из БД для актуальных данных
                user = CustomUser.objects.get(pk=request.user.pk)

                # Проверяем флаг is_blocked
                if hasattr(user, 'is_blocked') and user.is_blocked:
                    # Разлогиниваем заблокированного пользователя
                    logout(request)
                    messages.error(
                        request,
                        'Ваш аккаунт заблокирован. Обратитесь к администратору.'
                    )
                    return redirect('login')

            except CustomUser.DoesNotExist:
                logout(request)
                return redirect('login')
            except Exception as e:
                # Логируем ошибку но не блокируем запрос
                logger.error(f"BlockedUserMiddleware error: {e}")

        return None


class ActionLoggingMiddleware(MiddlewareMixin):
    """
    Middleware для автоматического логирования действий пользователей.

    Логирует все POST, PUT, PATCH, DELETE запросы и сохраняет информацию
    о действиях пользователей в журнал действий (ActionLog).

    Особенности:
    - Логирует только успешные изменяющие запросы
    - Исключает служебные пути (статика, медиа, админка и т.д.)
    - Автоматически определяет тип действия по HTTP методу
    - Извлекает метаданные (IP, User-Agent) из запроса
    """

    # Пути, которые не нужно логировать (для оптимизации)
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
        """
        Обработка HTTP ответа для логирования действий.

        Args:
            request (HttpRequest): Объект HTTP запроса
            response (HttpResponse): Объект HTTP ответа

        Returns:
            HttpResponse: Исходный ответ (middleware не изменяет ответ)
        """
        # Пропускаем исключенные пути для оптимизации
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return response

        # Логируем только успешные изменяющие запросы
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if 200 <= response.status_code < 400:
                self._log_request(request, response)

        return response

    def _log_request(self, request: HttpRequest, response: HttpResponse) -> None:
        """
        Внутренний метод для логирования HTTP запроса.

        Создает запись в журнале действий на основе информации о запросе.

        Args:
            request (HttpRequest): Объект HTTP запроса
            response (HttpResponse): Объект HTTP ответа
        """
        user = request.user if request.user.is_authenticated else None

        # Определяем тип действия по HTTP методу
        action_map = {
            'POST': ActionLog.ActionType.CREATE,
            'PUT': ActionLog.ActionType.UPDATE,
            'PATCH': ActionLog.ActionType.UPDATE,
            'DELETE': ActionLog.ActionType.DELETE,
        }
        action_type = action_map.get(request.method, ActionLog.ActionType.OTHER)

        # Получаем название модели из пути URL
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
            # Логируем ошибку, но не прерываем выполнение
            logger.error(f"Error logging action: {e}")


# Обработчики сигналов Django для логирования событий аутентификации
def log_user_login(sender, request, user, **kwargs):
    """
    Логирование успешного входа пользователя в систему.

    Args:
        sender: Отправитель сигнала
        request (HttpRequest): Объект HTTP запроса
        user (CustomUser): Аутентифицированный пользователь
        **kwargs: Дополнительные аргументы сигнала
    """
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
    """
    Логирование выхода пользователя из системы.

    Args:
        sender: Отправитель сигнала
        request (HttpRequest): Объект HTTP запроса
        user (CustomUser): Пользователь, выходящий из системы
        **kwargs: Дополнительные аргументы сигнала
    """
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


# Подключаем сигналы Django для автоматического логирования входа/выхода
user_logged_in.connect(log_user_login)
user_logged_out.connect(log_user_logout)
