"""
СЕРВИС СТАТУСОВ БРОНИРОВАНИЯ
Единая точка для работы со статусами
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
    """Сервис для работы со статусами бронирований"""

    @staticmethod
    def get_or_create(code: str) -> 'BookingStatus':
        """
        Получить или создать статус по коду

        Args:
            code: Код статуса (pending, confirmed, completed, cancelled)

        Returns:
            Объект BookingStatus

        Raises:
            ValueError: Неизвестный код статуса
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
        """Получить статус 'Ожидание'"""
        return StatusService.get_or_create('pending')

    @staticmethod
    def get_confirmed() -> 'BookingStatus':
        """Получить статус 'Подтверждено'"""
        return StatusService.get_or_create('confirmed')

    @staticmethod
    def get_completed() -> 'BookingStatus':
        """Получить статус 'Завершено'"""
        return StatusService.get_or_create('completed')

    @staticmethod
    def get_cancelled() -> 'BookingStatus':
        """Получить статус 'Отменено'"""
        return StatusService.get_or_create('cancelled')
