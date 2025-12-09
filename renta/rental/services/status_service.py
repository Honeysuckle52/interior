"""
====================================================================
СЕРВИС СТАТУСОВ БРОНИРОВАНИЯ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит сервис для работы со статусами бронирований.
Обеспечивает единую точку доступа к стандартным статусам
бронирований и их созданию при необходимости.

Основные функции:
- get_or_create: Получение или создание статуса по коду
- get_pending_status: Получение статуса "Ожидание"
- get_confirmed_status: Получение статуса "Подтверждено"
- get_completed_status: Получение статуса "Завершено"
- get_cancelled_status: Получение статуса "Отменено"

Константы:
- StatusCodes: Коды статусов для использования в коде
- StatusDefaults: Значения по умолчанию для статусов

Особенности:
- Конфигурация статусов по умолчанию в словаре DEFAULT_STATUSES
- Автоматическое создание отсутствующих статусов
- Проверка корректности кодов статусов
- Единообразное использование во всем приложении
====================================================================
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import BookingStatus

logger = logging.getLogger(__name__)


# =============================================================================
# КОНСТАНТЫ СТАТУСОВ
# =============================================================================

class StatusCodes:
    """Коды статусов бронирования для использования в коде."""
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    # Список активных статусов (для фильтрации)
    ACTIVE = [PENDING, CONFIRMED]
    # Список финальных статусов
    FINAL = [COMPLETED, CANCELLED]


class StatusDefaults:
    """Значения по умолчанию для статусов."""
    PENDING = {'name': 'Ожидание', 'color': 'warning', 'sort_order': 1}
    CONFIRMED = {'name': 'Подтверждено', 'color': 'success', 'sort_order': 2}
    COMPLETED = {'name': 'Завершено', 'color': 'info', 'sort_order': 3}
    CANCELLED = {'name': 'Отменено', 'color': 'danger', 'sort_order': 4}


# Конфигурация статусов по умолчанию (для обратной совместимости)
DEFAULT_STATUSES: dict[str, dict[str, Any]] = {
    StatusCodes.PENDING: StatusDefaults.PENDING,
    StatusCodes.CONFIRMED: StatusDefaults.CONFIRMED,
    StatusCodes.COMPLETED: StatusDefaults.COMPLETED,
    StatusCodes.CANCELLED: StatusDefaults.CANCELLED,
}


class StatusService:
    """
    Сервис для работы со статусами бронирований.

    Предоставляет удобный интерфейс для получения стандартных статусов
    бронирований с гарантией их существования в базе данных.
    """

    # Кэш статусов для оптимизации
    _cache: dict[str, 'BookingStatus'] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Очистить кэш статусов."""
        cls._cache.clear()

    @classmethod
    def get_or_create(cls, code: str) -> 'BookingStatus':
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
        # Проверяем кэш
        if code in cls._cache:
            return cls._cache[code]

        from ..models import BookingStatus

        defaults = DEFAULT_STATUSES.get(code)
        if not defaults:
            raise ValueError(f'Неизвестный код статуса: {code}')

        try:
            status, _ = BookingStatus.objects.get_or_create(code=code, defaults=defaults)
            cls._cache[code] = status
            return status
        except Exception as e:
            logger.error(f"Ошибка получения статуса '{code}': {e}")
            raise

    @classmethod
    def get_pending(cls) -> 'BookingStatus':
        """
        Получить статус 'Ожидание'.

        Returns:
            BookingStatus: Статус с кодом 'pending'
        """
        return cls.get_or_create(StatusCodes.PENDING)

    @classmethod
    def get_confirmed(cls) -> 'BookingStatus':
        """
        Получить статус 'Подтверждено'.

        Returns:
            BookingStatus: Статус с кодом 'confirmed'
        """
        return cls.get_or_create(StatusCodes.CONFIRMED)

    @classmethod
    def get_completed(cls) -> 'BookingStatus':
        """
        Получить статус 'Завершено'.

        Returns:
            BookingStatus: Статус с кодом 'completed'
        """
        return cls.get_or_create(StatusCodes.COMPLETED)

    @classmethod
    def get_cancelled(cls) -> 'BookingStatus':
        """
        Получить статус 'Отменено'.

        Returns:
            BookingStatus: Статус с кодом 'cancelled'
        """
        return cls.get_or_create(StatusCodes.CANCELLED)

    # Алиасы для совместимости с использованием в views
    @classmethod
    def get_pending_status(cls) -> 'BookingStatus':
        """Алиас для get_pending()."""
        return cls.get_pending()

    @classmethod
    def get_confirmed_status(cls) -> 'BookingStatus':
        """Алиас для get_confirmed()."""
        return cls.get_confirmed()

    @classmethod
    def get_completed_status(cls) -> 'BookingStatus':
        """Алиас для get_completed()."""
        return cls.get_completed()

    @classmethod
    def get_cancelled_status(cls) -> 'BookingStatus':
        """Алиас для get_cancelled()."""
        return cls.get_cancelled()
