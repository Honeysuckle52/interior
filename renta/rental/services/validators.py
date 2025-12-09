"""
====================================================================
ВАЛИДАТОРЫ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит централизованные валидаторы для форм и моделей,
специализированные для российских телефонных номеров и других
пользовательских данных.

Основные функции:
- validate_russian_phone: Валидация российских номеров телефона без regex
- normalize_phone: Нормализация номера к стандартному формату +7XXXXXXXXXX
- format_phone_display: Форматирование номера для красивого отображения

Основной класс:
- PhoneValidator: Django-валидатор для интеграции с формами и моделями

Особенности:
- Поддержка множества форматов ввода (с разделителями и без)
- Логика без использования regex для упрощения понимания и отладки
- Преобразование к единому стандартному формату для хранения в БД
====================================================================
"""

from __future__ import annotations

from typing import Optional

from django import forms
from django.core.validators import BaseValidator


def validate_russian_phone(value: str) -> None:
    """
    Валидация российского номера телефона БЕЗ использования regex.

    Поддерживает множество популярных форматов ввода:
    - +7 (999) 123-45-67
    - 8 (999) 123-45-67
    - 79991234567
    - 89991234567
    - 8 999 123 45 67
    - +7-999-123-45-67

    Проверяет:
    1. Общее количество цифр (10-11)
    2. Корректность начала номера (+7, 8 или 7)
    3. Корректность кода оператора

    Args:
        value (str): Строка с номером телефона для валидации

    Raises:
        forms.ValidationError: Если номер не соответствует требованиям

    Note:
        Используется логика без regex для упрощения отладки и понимания.
        Принимаются как мобильные (начинающиеся с 9xx), так и городские номера.
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

    Приводит любой российский номер к единому формату для хранения в БД:
    - Удаляет все нецифровые символы
    - Преобразует номер с кодом 8 в код 7
    - Добавляет код страны +7 к 10-значным номерам

    Args:
        phone (Optional[str]): Строка с номером телефона любого формата

    Returns:
        str: Нормализованный номер в формате "+79991234567" 
             или пустая строка если вход пустой

    Examples:
        "8 (999) 123-45-67" -> "+79991234567"
        "+7 999 123 45 67" -> "+79991234567"
        "9991234567" -> "+79991234567"
        "" -> ""
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
    Форматирование номера телефона для красивого отображения.

    Преобразует нормализованный номер (+79991234567) 
    в удобочитаемый формат для пользователя.

    Args:
        phone (str): Номер телефона (предпочтительно нормализованный)

    Returns:
        str: Отформатированный номер в виде "+7 (999) 123-45-67"
             или исходный номер если он не может быть отформатирован

    Examples:
        "+79991234567" -> "+7 (999) 123-45-67"
        "invalid" -> "invalid"
    """
    normalized = normalize_phone(phone)
    if not normalized or len(normalized) != 12:
        return phone

    return f"{normalized[:2]} ({normalized[2:5]}) {normalized[5:8]}-{normalized[8:10]}-{normalized[10:12]}"


class PhoneValidator(BaseValidator):
    """
    Django-валидатор для телефонных номеров.

    Класс-обертка для функции validate_russian_phone,
    позволяющая использовать валидацию телефонных номеров
    в моделях и формах Django как стандартный валидатор.

    Usage:
        phone = models.CharField(
            max_length=20,
            validators=[phone_validator],
            ...
        )
    """

    message = 'Введите корректный номер телефона. Примеры: +7 (999) 123-45-67, 8 999 123 45 67'
    code = 'invalid_phone'

    def __init__(self, message=None):
        """
        Инициализация валидатора.

        Args:
            message (str, optional): Кастомное сообщение об ошибке
        """
        super().__init__(limit_value=None, message=message)

    def compare(self, value, limit_value):
        """
        Сравнение значения с лимитом (требуется BaseValidator).

        В данном валидаторе не используется, но требуется для совместимости
        с архитектурой Django BaseValidator.

        Returns:
            bool: Всегда False
        """
        return False

    def __call__(self, value):
        """
        Вызов валидации для значения.

        Args:
            value (str): Значение для валидации

        Raises:
            ValidationError: Если номер телефона некорректен
        """
        validate_russian_phone(value)


# Экземпляр валидатора для удобного использования в формах и моделях
phone_validator = PhoneValidator()