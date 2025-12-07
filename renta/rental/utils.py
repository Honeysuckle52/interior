"""
ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
Утилиты для приложения аренды
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Type

from django.db import models
from django.utils.text import slugify
from unidecode import unidecode


def generate_unique_slug(
    model_class: Type[models.Model],
    title: str,
    exclude_pk: Optional[int] = None
) -> str:
    """
    Генерация уникального slug из заголовка

    Args:
        model_class: Класс модели со slug полем
        title: Исходная строка
        exclude_pk: PK для исключения (при обновлении)
    """
    base_slug = slugify(unidecode(title)) or 'item'
    slug = base_slug
    counter = 1

    while True:
        qs = model_class.objects.filter(slug=slug)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            break
        slug = f'{base_slug}-{counter}'
        counter += 1

    return slug


def format_price(price: Optional[Decimal | float | int]) -> str:
    """Форматирование цены: 1500 -> '1 500 ₽'"""
    if price is None:
        return '—'
    try:
        formatted = '{:,.0f}'.format(Decimal(str(price))).replace(',', ' ')
        return f'{formatted} ₽'
    except Exception:
        return str(price)


def format_area(area: Optional[Decimal | float | int]) -> str:
    """Форматирование площади: 150 -> '150 м²'"""
    if area is None:
        return '—'
    try:
        area_dec = Decimal(str(area))
        if area_dec == int(area_dec):
            return f'{int(area_dec)} м²'
        return f'{area_dec:.1f} м²'
    except Exception:
        return str(area)


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Обрезка текста с сохранением целых слов"""
    if not text or len(text) <= max_length:
        return text or ''

    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def calculate_duration_text(hours: int) -> str:
    """Преобразование часов в читаемый текст: 26 -> '1 день 2 часа'"""
    if hours < 1:
        return 'менее часа'

    days = hours // 24
    remaining = hours % 24
    parts = []

    if days > 0:
        if days == 1:
            parts.append('1 день')
        elif 2 <= days <= 4:
            parts.append(f'{days} дня')
        else:
            parts.append(f'{days} дней')

    if remaining > 0:
        if remaining == 1:
            parts.append('1 час')
        elif 2 <= remaining <= 4:
            parts.append(f'{remaining} часа')
        else:
            parts.append(f'{remaining} часов')

    return ' '.join(parts)


def get_rating_stars(rating: float) -> str:
    """Звёзды рейтинга: 3.5 -> '★★★⯪☆'"""
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = 5 - full - half
    return '★' * full + '⯪' * half + '☆' * empty
