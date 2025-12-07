"""
КАСТОМНЫЕ TEMPLATE TAGS
"""

from django import template
from django.utils.safestring import mark_safe

from ..utils import format_price as _format_price, format_area as _format_area

register = template.Library()


@register.filter
def format_price(value):
    """Форматирование цены: {{ price|format_price }}"""
    return _format_price(value)


@register.filter
def format_area(value):
    """Форматирование площади: {{ area|format_area }}"""
    return _format_area(value)


@register.filter
def rating_stars(value):
    """Звёзды рейтинга с иконками: {{ rating|rating_stars }}"""
    try:
        rating = float(value)
        full = int(rating)
        half = 1 if rating - full >= 0.5 else 0
        empty = 5 - full - half

        html = '<span class="text-warning">'
        html += '<i class="fas fa-star"></i>' * full
        if half:
            html += '<i class="fas fa-star-half-alt"></i>'
        html += '<i class="far fa-star"></i>' * empty
        html += '</span>'
        return mark_safe(html)
    except Exception:
        return ''


@register.filter
def rating_stars_simple(value):
    """Простые звёзды: {{ rating|rating_stars_simple }}"""
    try:
        rating = int(float(value))
        return '★' * rating + '☆' * (5 - rating)
    except Exception:
        return '☆☆☆☆☆'


@register.filter
def truncate_chars(value, max_length=100):
    """Обрезка текста: {{ text|truncate_chars:50 }}"""
    if not value:
        return ''
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[:max_length - 3].rsplit(' ', 1)[0] + '...'


@register.filter
def phone_format(value):
    """Форматирование телефона: {{ phone|phone_format }}"""
    from ..services.validators import format_phone_display
    return format_phone_display(value) if value else ''


@register.filter
def pluralize_ru(value, forms):
    """Русское склонение: {{ count|pluralize_ru:"помещение,помещения,помещений" }}"""
    try:
        count = int(value)
        forms_list = forms.split(',')
        if len(forms_list) != 3:
            return forms_list[0] if forms_list else ''

        n = abs(count) % 100
        n1 = n % 10

        if 10 < n < 20:
            return forms_list[2]
        elif 1 < n1 < 5:
            return forms_list[1]
        elif n1 == 1:
            return forms_list[0]
        return forms_list[2]
    except Exception:
        return ''


@register.simple_tag
def query_transform(request, **kwargs):
    """Обновление GET-параметров: {% query_transform request page=2 %}"""
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            updated[key] = value
        elif key in updated:
            del updated[key]
    return updated.urlencode()


@register.inclusion_tag('components/pagination.html')
def render_pagination(page_obj, request=None):
    """Рендер пагинации"""
    return {'page_obj': page_obj, 'request': request}


@register.inclusion_tag('components/space_card.html')
def render_space_card(space, is_favorite=False):
    """Рендер карточки помещения"""
    return {'space': space, 'is_favorite': is_favorite}


@register.filter
def timesince_hours(value):
    """Часы от текущего момента до даты"""
    from django.utils import timezone
    if not value:
        return 0
    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value)
        return (value - now).total_seconds() / 3600
    except Exception:
        return 0


@register.filter
def is_less_than_24_hours(value):
    """Проверка: до даты менее 24 часов"""
    hours = timesince_hours(value)
    return 0 < hours < 24


@register.filter
def duration_format(value):
    """Форматирование длительности в часах"""
    try:
        hours = float(value)
        if hours < 0:
            return 'уже началось'
        if hours < 1:
            return f'{int(hours * 60)} мин.'
        if hours < 24:
            return f'{int(hours)} ч.'
        days = int(hours / 24)
        rem = int(hours % 24)
        if rem:
            return f'{days} дн. {rem} ч.'
        return f'{days} дн.'
    except Exception:
        return str(value)
