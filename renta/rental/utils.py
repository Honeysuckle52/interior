"""
ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

Utility functions for the rental application.
"""

from __future__ import annotations

import re
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
    Generate a unique slug from title.

    Args:
        model_class: Django model class with slug field
        title: Source string for slug
        exclude_pk: Primary key to exclude (for updates)

    Returns:
        Unique slug string
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


def format_price(price: Optional[Decimal | float | int]) -> str:
    """
    Format price for display.

    Args:
        price: Numeric price value

    Returns:
        Formatted price string (e.g., "1 500 ₽")
    """
    if price is None:
        return '—'

    price_decimal = Decimal(str(price))
    formatted = '{:,.0f}'.format(price_decimal).replace(',', ' ')
    return f"{formatted} ₽"


def format_area(area: Optional[Decimal | float | int]) -> str:
    """
    Format area for display.

    Args:
        area: Numeric area value

    Returns:
        Formatted area string (e.g., "150 м²")
    """
    if area is None:
        return '—'

    area_decimal = Decimal(str(area))
    if area_decimal == int(area_decimal):
        return f"{int(area_decimal)} м²"
    return f"{area_decimal:.1f} м²"


def normalize_phone(phone: Optional[str]) -> str:
    """
    Normalize phone number to standard format.

    Args:
        phone: Phone number string

    Returns:
        Normalized phone number (e.g., "+71234567890")
    """
    if not phone:
        return ''

    # Keep only digits
    digits = re.sub(r'\D', '', phone)

    # Convert to +7XXXXXXXXXX format
    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        return f"+{digits}"
    elif len(digits) == 10:
        return f"+7{digits}"

    return phone


def format_phone(phone: str) -> str:
    """
    Format phone number for display.

    Args:
        phone: Phone number (preferably normalized)

    Returns:
        Formatted phone (e.g., "+7 (999) 123-45-67")
    """
    phone = normalize_phone(phone)
    if not phone or len(phone) != 12:
        return phone

    return f"{phone[:2]} ({phone[2:5]}) {phone[5:8]}-{phone[8:10]}-{phone[10:12]}"


def truncate_text(
    text: str,
    max_length: int = 100,
    suffix: str = '...'
) -> str:
    """
    Truncate text to specified length.

    Args:
        text: Source text
        max_length: Maximum length
        suffix: Suffix for truncated text

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    truncated = text[:max_length - len(suffix)]
    # Try to break at word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def calculate_duration_text(hours: int) -> str:
    """
    Convert hours to readable text.

    Args:
        hours: Number of hours

    Returns:
        Readable duration (e.g., "2 дня 5 часов")
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
    Get star representation of rating.

    Args:
        rating: Rating from 0 to 5

    Returns:
        String with star characters
    """
    full_stars = int(rating)
    half_star = 1 if rating - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    return '★' * full_stars + '⯪' * half_star + '☆' * empty_stars
