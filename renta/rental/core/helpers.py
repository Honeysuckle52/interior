"""
====================================================================
ЦЕНТРАЛИЗОВАННЫЕ ХЕЛПЕРЫ
====================================================================
Вспомогательные функции для форматирования, парсинга и утилиты.
====================================================================
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional, Type

from django.db import models
from django.utils.text import slugify
from unidecode import unidecode


# =============================================================================
# ПАРСИНГ ПАРАМЕТРОВ
# =============================================================================

def parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Безопасный парсинг целого числа.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Целое число или default
    """
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Безопасный парсинг числа с плавающей точкой.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Число или default
    """
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_bool(value: Any, default: bool = False) -> bool:
    """
    Безопасный парсинг булева значения.

    Args:
        value: Значение для парсинга
        default: Значение по умолчанию

    Returns:
        Булево значение
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)


# =============================================================================
# ФОРМАТИРОВАНИЕ
# =============================================================================

def format_price(price: Optional[Decimal | float | int]) -> str:
    """
    Форматирование цены для отображения.

    Args:
        price: Числовое значение цены

    Returns:
        Отформатированная строка: "1 500 ₽"
    """
    if price is None:
        return '—'

    price_decimal = Decimal(str(price))
    formatted = '{:,.0f}'.format(price_decimal).replace(',', ' ')
    return f"{formatted} ₽"


def format_area(area: Optional[Decimal | float | int]) -> str:
    """
    Форматирование площади для отображения.

    Args:
        area: Числовое значение площади

    Returns:
        Отформатированная строка: "150 м²"
    """
    if area is None:
        return '—'

    area_decimal = Decimal(str(area))
    if area_decimal == int(area_decimal):
        return f"{int(area_decimal)} м²"
    return f"{area_decimal:.1f} м²"


def truncate_text(
    text: str,
    max_length: int = 100,
    suffix: str = '...'
) -> str:
    """
    Обрезка текста до указанной длины.

    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста

    Returns:
        Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text

    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def calculate_duration_text(hours: int) -> str:
    """
    Преобразование часов в читаемый текст.

    Args:
        hours: Количество часов

    Returns:
        Читаемая строка: "2 дня 5 часов"
    """
    if hours < 1:
        return 'менее часа'

    days = hours // 24
    remaining_hours = hours % 24

    parts: list[str] = []

    if days > 0:
        if days == 1:
            parts.append('1 день')
        elif 2 <= days <= 4:
            parts.append(f'{days} дня')
        else:
            parts.append(f'{days} дней')

    if remaining_hours > 0:
        if remaining_hours == 1:
            parts.append('1 час')
        elif 2 <= remaining_hours <= 4:
            parts.append(f'{remaining_hours} часа')
        else:
            parts.append(f'{remaining_hours} часов')

    return ' '.join(parts)


def get_rating_stars(rating: float) -> str:
    """
    Получить звёзды для рейтинга.

    Args:
        rating: Рейтинг от 0 до 5

    Returns:
        Строка со звёздами
    """
    full_stars = int(rating)
    half_star = 1 if rating - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    return '★' * full_stars + '⯪' * half_star + '☆' * empty_stars


def generate_unique_slug(
    model_class: Type[models.Model],
    title: str,
    exclude_pk: Optional[int] = None
) -> str:
    """
    Генерация уникального slug из заголовка.

    Args:
        model_class: Класс модели Django
        title: Исходная строка для slug
        exclude_pk: ID для исключения (при обновлении)

    Returns:
        Уникальный slug
    """
    base_slug = slugify(unidecode(title))
    if not base_slug:
        base_slug = 'item'

    slug = base_slug
    counter = 1

    while True:
        qs = model_class.objects.filter(slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        if not qs.exists():
            break

        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug
