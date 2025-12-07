"""
ВАЛИДАТОРЫ
Централизованные валидаторы для форм и моделей
"""
from __future__ import annotations

from typing import Optional

from django import forms
from django.core.validators import BaseValidator


def validate_russian_phone(value: str) -> None:
    """
    Валидация российского номера телефона БЕЗ regex.

    Поддерживаемые форматы:
    - +7 (999) 123-45-67
    - 8 (999) 123-45-67
    - 79991234567
    - 89991234567
    - 8 999 123 45 67
    - +7-999-123-45-67

    Args:
        value: Строка с номером телефона

    Raises:
        forms.ValidationError: Если номер некорректен
    """
    if not value:
        return

    # Удаляем все кроме цифр и +
    cleaned = ''.join(c for c in value if c.isdigit() or c == '+')

    # Удаляем + для подсчёта цифр
    digits_only = cleaned.replace('+', '')

    # Проверяем количество цифр (должно быть 10 или 11)
    if len(digits_only) < 10 or len(digits_only) > 11:
        raise forms.ValidationError(
            'Номер телефона должен содержать 10-11 цифр'
        )

    # Проверяем начало номера
    if cleaned.startswith('+'):
        # Международный формат: +7...
        if not cleaned.startswith('+7'):
            raise forms.ValidationError(
                'Номер должен начинаться с +7 или 8'
            )
        if len(digits_only) != 11:
            raise forms.ValidationError(
                'Номер в формате +7 должен содержать 11 цифр'
            )
    elif digits_only.startswith('8') or digits_only.startswith('7'):
        # Российский формат: 8... или 7...
        if len(digits_only) != 11:
            raise forms.ValidationError(
                'Номер должен содержать 11 цифр с кодом страны'
            )
    else:
        # Номер без кода страны (10 цифр)
        if len(digits_only) != 10:
            raise forms.ValidationError(
                'Номер без кода страны должен содержать 10 цифр'
            )

    # Проверяем что код оператора валидный (9xx для мобильных)
    if len(digits_only) == 11:
        operator_code = digits_only[1:4]
    else:
        operator_code = digits_only[0:3]

    # Мобильные коды начинаются с 9, городские могут быть другими
    # Разрешаем любые коды для гибкости
    if not operator_code.isdigit():
        raise forms.ValidationError(
            'Некорректный код оператора'
        )


def normalize_phone(phone: Optional[str]) -> str:
    """
    Нормализация номера телефона к стандартному формату +7XXXXXXXXXX.

    Args:
        phone: Строка с номером телефона

    Returns:
        Нормализованный номер (например, "+79991234567") или пустая строка
    """
    if not phone:
        return ''

    # Оставляем только цифры
    digits = ''.join(c for c in phone if c.isdigit())

    # Преобразуем к формату +7XXXXXXXXXX
    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        return f"+{digits}"
    elif len(digits) == 10:
        return f"+7{digits}"

    return phone


def format_phone_display(phone: str) -> str:
    """
    Форматирование номера телефона для отображения.

    Args:
        phone: Номер телефона (желательно нормализованный)

    Returns:
        Отформатированный номер (например, "+7 (999) 123-45-67")
    """
    normalized = normalize_phone(phone)
    if not normalized or len(normalized) != 12:
        return phone

    return f"{normalized[:2]} ({normalized[2:5]}) {normalized[5:8]}-{normalized[8:10]}-{normalized[10:12]}"


class PhoneValidator(BaseValidator):
    """Django-валидатор для телефонных номеров"""
    message = 'Введите корректный номер телефона. Примеры: +7 (999) 123-45-67, 8 999 123 45 67'
    code = 'invalid_phone'

    def __init__(self, message=None):
        super().__init__(limit_value=None, message=message)

    def compare(self, value, limit_value):
        # Не используется, но требуется для BaseValidator
        return False

    def __call__(self, value):
        validate_russian_phone(value)


# Экземпляр валидатора для использования в формах
phone_validator = PhoneValidator()
