"""
ВАЛИДАТОРЫ
Единые валидаторы для форм и моделей
"""

from __future__ import annotations

import re
from typing import Optional

from django import forms


# Паттерн для российских номеров телефона
PHONE_PATTERN = re.compile(r'^\+?[78]?[\s\-]?$$?\d{3}$$?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$')


def validate_phone(value: str) -> None:
    """
    Валидация номера телефона (российский формат)

    Допустимые форматы:
    - +7 (999) 123-45-67
    - 8 999 123 45 67
    - +79991234567
    """
    if not value:
        return

    # Очистка от пробелов для проверки длины
    digits = re.sub(r'\D', '', value)

    if len(digits) < 10 or len(digits) > 11:
        raise forms.ValidationError('Номер должен содержать 10-11 цифр')

    if not PHONE_PATTERN.match(value):
        raise forms.ValidationError('Введите корректный номер телефона')


def normalize_phone(phone: Optional[str]) -> str:
    """
    Нормализация телефона в формат +7XXXXXXXXXX

    Args:
        phone: Исходный номер

    Returns:
        Нормализованный номер или пустая строка
    """
    if not phone:
        return ''

    digits = re.sub(r'\D', '', phone)

    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        return f'+{digits}'
    elif len(digits) == 10:
        return f'+7{digits}'

    return phone


def format_phone_display(phone: str) -> str:
    """
    Форматирование телефона для отображения

    Args:
        phone: Телефон (желательно нормализованный)

    Returns:
        Отформатированный номер (+7 (999) 123-45-67)
    """
    phone = normalize_phone(phone)
    if not phone or len(phone) != 12:
        return phone

    return f'{phone[:2]} ({phone[2:5]}) {phone[5:8]}-{phone[8:10]}-{phone[10:12]}'


def validate_username(value: str) -> None:
    """Валидация имени пользователя"""
    if not value:
        raise forms.ValidationError('Имя пользователя обязательно')
    if len(value) < 3:
        raise forms.ValidationError('Минимум 3 символа')
    if len(value) > 150:
        raise forms.ValidationError('Максимум 150 символов')

    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
    if not all(c in allowed for c in value):
        raise forms.ValidationError('Только буквы, цифры и подчеркивание')
