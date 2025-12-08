"""
КАСТОМНЫЕ TEMPLATE TAGS
"""

from django import template
from django.utils.safestring import mark_safe
from decimal import Decimal

register = template.Library()


@register.filter
def format_price(value):
    """
    Форматирование цены: {{ price|format_price }}
    """
    if value is None:
        return '—'

    try:
        price = Decimal(str(value))
        formatted = '{:,.0f}'.format(price).replace(',', ' ')
        return f"{formatted} ₽"
    except:
        return str(value)


@register.filter
def format_area(value):
    """
    Форматирование площади: {{ area|format_area }}
    """
    if value is None:
        return '—'

    try:
        area = Decimal(str(value))
        if area == int(area):
            return f"{int(area)} м²"
        return f"{area:.1f} м²"
    except:
        return str(value)


@register.filter
def rating_stars(value):
    """
    Звёзды рейтинга: {{ rating|rating_stars }}
    """
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
    except:
        return ''


@register.filter
def rating_stars_simple(value):
    """
    Простые звёзды: {{ rating|rating_stars_simple }}
    """
    try:
        rating = int(float(value))
        return '★' * rating + '☆' * (5 - rating)
    except:
        return '☆☆☆☆☆'


@register.filter
def truncate_chars(value, max_length=100):
    """
    Обрезка текста: {{ text|truncate_chars:50 }}
    """
    if not value:
        return ''

    text = str(value)
    if len(text) <= max_length:
        return text

    return text[:max_length - 3].rsplit(' ', 1)[0] + '...'


@register.filter
def phone_format(value):
    """
    Форматирование телефона: {{ phone|phone_format }}
    """
    if not value:
        return ''

    import re
    digits = re.sub(r'\D', '', str(value))

    if len(digits) == 11 and digits[0] in '78':
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

    return value


@register.filter
def pluralize_ru(value, forms):
    """
    Русское склонение: {{ count|pluralize_ru:"помещение,помещения,помещений" }}
    """
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
        else:
            return forms_list[2]
    except:
        return ''


@register.simple_tag
def query_transform(request, **kwargs):
    """
    Обновление GET-параметров: {% query_transform request page=2 %}
    """
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            updated[key] = value
        elif key in updated:
            del updated[key]
    return updated.urlencode()


@register.inclusion_tag('components/pagination.html')
def render_pagination(page_obj, request=None):
    """
    Рендер пагинации: {% render_pagination page_obj request %}
    """
    return {
        'page_obj': page_obj,
        'request': request,
    }


@register.inclusion_tag('components/space_card.html')
def render_space_card(space, is_favorite=False):
    """
    Рендер карточки помещения: {% render_space_card space %}
    """
    return {
        'space': space,
        'is_favorite': is_favorite,
    }


@register.filter
def timesince_hours(value):
    """
    Количество часов от текущего момента до даты: {{ date|timesince_hours }}
    Возвращает положительное число если дата в будущем, отрицательное если в прошлом.
    """
    from django.utils import timezone

    if not value:
        return 0

    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value)

        delta = value - now
        hours = delta.total_seconds() / 3600
        return hours
    except Exception:
        return 0


@register.filter
def is_less_than_24_hours(value):
    """
    Проверяет, что до даты осталось менее 24 часов: {{ date|is_less_than_24_hours }}
    """
    from django.utils import timezone

    if not value:
        return False

    try:
        now = timezone.now()
        if timezone.is_naive(value):
            value = timezone.make_aware(value)

        delta = value - now
        hours = delta.total_seconds() / 3600
        return 0 < hours < 24
    except Exception:
        return False


@register.filter
def duration_format(value):
    """
    Форматирование длительности в часах: {{ hours|duration_format }}
    """
    try:
        hours = float(value)
        if hours < 0:
            return "уже началось"

        if hours < 1:
            minutes = int(hours * 60)
            return f"{minutes} мин."
        elif hours < 24:
            return f"{int(hours)} ч."
        else:
            days = int(hours / 24)
            remaining_hours = int(hours % 24)
            if remaining_hours:
                return f"{days} дн. {remaining_hours} ч."
            return f"{days} дн."
    except Exception:
        return str(value)


@register.filter
def get_item(dictionary, key):
    """
    Получение значения из словаря по ключу: {{ dict|get_item:key }}
    Используется для доступа к словарям в шаблонах где ключ - переменная.
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None
