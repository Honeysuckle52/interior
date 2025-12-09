"""
====================================================================
ЦЕНТРАЛИЗОВАННЫЕ ИСКЛЮЧЕНИЯ
====================================================================
Иерархия кастомных исключений для унификации обработки ошибок.
====================================================================
"""

from __future__ import annotations


class AppError(Exception):
    """
    Базовое исключение приложения.

    Все кастомные исключения наследуются от него для
    унифицированной обработки ошибок.
    """

    default_message: str = 'Произошла ошибка'

    def __init__(self, message: str = None, code: str = None):
        self.message = message or self.default_message
        self.code = code
        super().__init__(self.message)


class ValidationError(AppError):
    """Ошибка валидации данных."""
    default_message = 'Ошибка валидации данных'


class ServiceError(AppError):
    """Ошибка в сервисном слое."""
    default_message = 'Ошибка сервиса'


class NotFoundError(AppError):
    """Объект не найден."""
    default_message = 'Объект не найден'


class PermissionError(AppError):
    """Ошибка доступа."""
    default_message = 'Недостаточно прав для выполнения операции'


class BookingError(ServiceError):
    """Ошибка бронирования."""
    default_message = 'Ошибка при бронировании'


class PaymentError(ServiceError):
    """Ошибка оплаты."""
    default_message = 'Ошибка при обработке оплаты'
