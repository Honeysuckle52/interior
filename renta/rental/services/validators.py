"""
ВАЛИДАТОРЫ
Централизованные валидаторы для форм и моделей
"""
from __future__ import annotations

import re
from typing import Optional

from django import forms
from django.core.validators import RegexValidator


# Поддерживаемые форматы:
# - Международный: +7 (999) 123-45-67
# - Российский: 8 (999) 123-45-67
# - Без форматирования: 79991234567, 89991234567
# - С пробелами и дефисами: 8 999 123 45 67
# Исправлен regex: заменены $$? на $$? и $$? для корректного экранирования скобок
RUSSIAN_PHONE_REGEX = r'^(\+7|8)[\s\-]?$$?\d{3}$$?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$'

# Валидатор для использования в формах Django
phone_regex_validator = RegexValidator(
    regex=RUSSIAN_PHONE_REGEX,
    message='Введите корректный номер телефона. Примеры: +7 (999) 123-45-67, 8 999 123 45 67'
)


def validate_russian_phone(value: str) -> None:
    """
    Валидация российского номера телефона.

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

    # Проверяем базовую длину
    if len(cleaned) < 11 or len(cleaned) > 12:
        raise forms.ValidationError(
            'Номер телефона должен содержать 11 цифр (с кодом страны)'
        )

    # Проверяем формат с помощью regex
    if not re.match(RUSSIAN_PHONE_REGEX, value):
        raise forms.ValidationError(
            'Введите корректный номер телефона. Примеры: +7 (999) 123-45-67, 8 999 123 45 67'
        )


def normalize_phone(phone: Optional[str]) -> str:
    """
    Нормализация номера телефона к стандартному формату +7XXXXXXXXXX.

    Args:
        phone: Строка с номером телефона

    Returns:
        Нормализованный номер (например, "+79991234567") или пустая ��трока
    """
    if not phone:
        return ''

    # Оставляем только цифры
    digits = re.sub(r'\D', '', phone)

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
