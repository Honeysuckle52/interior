"""
ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
"""

from django.utils.text import slugify
from unidecode import unidecode
from decimal import Decimal
import re


def generate_unique_slug(model_class, title: str, exclude_pk=None) -> str:
    """
    Генерация уникального slug из названия

    Args:
        model_class: класс модели Django
        title: исходная строка для slug
        exclude_pk: ID записи для исключения (при редактировании)

    Returns:
        str: уникальный slug
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


def format_price(price) -> str:
    """
    Форматирование цены для отображения

    Args:
        price: число или Decimal

    Returns:
        str: отформатированная цена, например "1 500 ₽"
    """
    if price is None:
        return '—'

    price = Decimal(str(price))
    formatted = '{:,.0f}'.format(price).replace(',', ' ')
    return f"{formatted} ₽"


def format_area(area) -> str:
    """
    Форматирование площади

    Args:
        area: число или Decimal

    Returns:
        str: отформатированная площадь, например "150 м²"
    """
    if area is None:
        return '—'

    area = Decimal(str(area))
    if area == int(area):
        return f"{int(area)} м²"
    return f"{area:.1f} м²"


def normalize_phone(phone: str) -> str:
    """
    Нормализация номера телефона

    Args:
        phone: строка с номером телефона

    Returns:
        str: нормализованный номер
    """
    if not phone:
        return ''

    # Оставляем только цифры
    digits = re.sub(r'\D', '', phone)

    # Приводим к формату +7XXXXXXXXXX
    if len(digits) == 11:
        if digits.startswith('8'):
            digits = '7' + digits[1:]
        elif digits.startswith('7'):
            pass
        return f"+{digits}"
    elif len(digits) == 10:
        return f"+7{digits}"

    return phone


def format_phone(phone: str) -> str:
    """
    Форматирование номера телефона для отображения

    Args:
        phone: нормализованный номер

    Returns:
        str: красиво отформатированный номер
    """
    phone = normalize_phone(phone)
    if not phone or len(phone) != 12:
        return phone

    # +7 (999) 123-45-67
    return f"{phone[:2]} ({phone[2:5]}) {phone[5:8]}-{phone[8:10]}-{phone[10:12]}"


def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    Обрезка текста до указанной длины

    Args:
        text: исходный текст
        max_length: максимальная длина
        suffix: суффикс для обрезанного текста

    Returns:
        str: обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)].rsplit(' ', 1)[0] + suffix


def calculate_duration_text(hours: int) -> str:
    """
    Преобразование часов в читаемый текст

    Args:
        hours: количество часов

    Returns:
        str: текстовое представление, например "2 дня 5 часов"
    """
    if hours < 1:
        return 'менее часа'

    days = hours // 24
    remaining_hours = hours % 24

    parts = []

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
    Получить звёзды рейтинга

    Args:
        rating: рейтинг от 0 до 5

    Returns:
        str: строка со звёздами
    """
    full_stars = int(rating)
    half_star = 1 if rating - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    return '★' * full_stars + '⯪' * half_star + '☆' * empty_stars
