"""
====================================================================
СЕРВИС СТАТУСОВ БРОНИРОВАНИЯ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит сервис для работы со статусами бронирований.
Обеспечивает единую точку доступа к стандартным статусам
бронирований и их созданию при необходимости.

Основные функции:
- get_or_create: Получение или создание статуса по коду
- get_pending: Получение статуса "Ожидание"
- get_confirmed: Получение статуса "Подтверждено"
- get_completed: Получение статуса "Завершено"
- get_cancelled: Получение статуса "Отменено"

Особенности:
- Конфигурация статусов по умолчанию в словаре DEFAULT_STATUSES
- Автоматическое создание отсутствующих статусов
- Проверка корректности кодов статусов
- Единообразное использование во всем приложении
====================================================================
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import BookingStatus

logger = logging.getLogger(__name__)

# Конфигурация статусов по умолчанию
DEFAULT_STATUSES = {
    'pending': {'name': 'Ожидание', 'color': 'warning', 'sort_order': 1},
    'confirmed': {'name': 'Подтверждено', 'color': 'success', 'sort_order': 2},
    'completed': {'name': 'Завершено', 'color': 'info', 'sort_order': 3},
    'cancelled': {'name': 'Отменено', 'color': 'danger', 'sort_order': 4},
}


class StatusService:
    """
    Сервис для работы со статусами бронирований.

    Предоставляет удобный интерфейс для получения стандартных статусов
    бронирований с гарантией их существования в базе данных.
    """

    @staticmethod
    def get_or_create(code: str) -> 'BookingStatus':
        """
        Получить или создать статус по коду.

        Получает статус бронирования из базы данных по его коду.
        Если статус с таким кодом не существует, создает его
        используя конфигурацию из DEFAULT_STATUSES.

        Args:
            code (str): Код статуса. Допустимые значения:
                - 'pending': Ожидание подтверждения
                - 'confirmed': Подтверждено
                - 'completed': Завершено
                - 'cancelled': Отменено

        Returns:
            BookingStatus: Объект статуса бронирования

        Raises:
            ValueError: Если передан неизвестный код статуса
            Exception: При любых других ошибках работы с базой данных
        """
        from ..models import BookingStatus

        defaults = DEFAULT_STATUSES.get(code)
        if not defaults:
            raise ValueError(f'Неизвестный код статуса: {code}')

        try:
            status, _ = BookingStatus.objects.get_or_create(code=code, defaults=defaults)
            return status
        except Exception as e:
            logger.error(f"Ошибка получения статуса '{code}': {e}")
            raise

    @staticmethod
    def get_pending() -> 'BookingStatus':
        """
        Получить статус 'Ожидание'.

        Returns:
            BookingStatus: Статус с кодом 'pending'
        """
        return StatusService.get_or_create('pending')

    @staticmethod
    def get_confirmed() -> 'BookingStatus':
        """
        Получить статус 'Подтверждено'.

        Returns:
            BookingStatus: Статус с кодом 'confirmed'
        """
        return StatusService.get_or_create('confirmed')

    @staticmethod
    def get_completed() -> 'BookingStatus':
        """
        Получить статус 'Завершено'.

        Returns:
            BookingStatus: Статус с кодом 'completed'
        """
        return StatusService.get_or_create('completed')

    @staticmethod
    def get_cancelled() -> 'BookingStatus':
        """
        Получить статус 'Отменено'.

        Returns:
            BookingStatus: Статус с кодом 'cancelled'
        """
        return StatusService.get_or_create('cancelled')