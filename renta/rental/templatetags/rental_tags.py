"""
====================================================================
КАСТОМНЫЕ TEMPLATE TAGS ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит пользовательские теги и фильтры для шаблонов Django,
специализированные для отображения данных сайта аренды помещений.

Основные категории:
- Фильтры форматирования (цены, площади, телефоны, даты)
- Фильтры для рейтингов (звезды, склонения)
- Фильтры для работы с текстом (обрезка, склонения)
- Пользовательские теги (пагинация, карточки помещений, работа с GET-параметрами)

Использование:
1. Добавить в шаблон: {% load rental_tags %}
2. Использовать фильтры: {{ price|format_price }}
3. Использовать теги: {% render_space_card space %}
====================================================================
"""

from django import template
from django.utils.safestring import mark_safe
from decimal import Decimal

register = template.Library()


@register.filter
def format_price(value):
    """
    Форматирование цены для отображения.

    Преобразует числовое значение в удобочитаемый формат
    с разделителями тысяч и символом рубля.

    Args:
        value (Decimal, int, float, str): Значение для форматирования

    Returns:
        str: Отформатированная цена или "—" для пустых значений

    Examples:
        {{ 150000|format_price }} -> "150 000 ₽"
        {{ None|format_price }} -> "—"
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
    Форматирование площади для отображения.

    Преобразует числовое значение площади в квадратных метрах
    в удобочитаемый формат с единицами измерения.

    Args:
        value (Decimal, int, float, str): Площадь в м²

    Returns:
        str: Отформатированная площадь или "—" для пустых значений

    Examples:
        {{ 45.5|format_area }} -> "45.5 м²"
        {{ 100|format_area }} -> "100 м²"
        {{ None|format_area }} -> "—"
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
    Генерация HTML кода для отображения звезд рейтинга.

    Создает иконки FontAwesome для отображения рейтинга:
    - Полные звезды для целых значений
    - Половина звезды для значений с 0.5
    - Пустые звезды для оставшейся части

    Args:
        value (float, int, str): Рейтинг от 0 до 5

    Returns:
        SafeString: HTML код звезд рейтинга

    Examples:
        {{ 4.5|rating_stars }} -> HTML с 4 полными звездами и 1 полузвездой
        Небезопасное значение оборачивается в mark_safe для корректного отображения
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
    Генерация простых текстовых звезд рейтинга.

    Использует Unicode символы звезд для отображения рейтинга
    без зависимостей от внешних библиотек иконок.

    Args:
        value (float, int, str): Рейтинг от 0 до 5

    Returns:
        str: Текстовое представление звезд рейтинга

    Examples:
        {{ 3|rating_stars_simple }} -> "★★★☆☆"
        {{ None|rating_stars_simple }} -> "☆☆☆☆☆"
    """
    try:
        rating = int(float(value))
        return '★' * rating + '☆' * (5 - rating)
    except:
        return '☆☆☆☆☆'


@register.filter
def truncate_chars(value, max_length=100):
    """
    Обрезка текста до указанной длины с сохранением целых слов.

    Если текст превышает максимальную длину, обрезает его
    до последнего полного слова и добавляет многоточие.

    Args:
        value (str): Текст для обрезки
        max_length (int): Максимальная длина результата

    Returns:
        str: Обрезанный текст или оригинал если он короче

    Examples:
        {{ "Очень длинный текст"|truncate_chars:10 }} -> "Очень длинный..."
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
    Форматирование российского номера телефона для отображения.

    Преобразует сырой номер телефона в удобочитаемый формат
    с разделителями и кодом страны.

    Args:
        value (str): Номер телефона в любом формате

    Returns:
        str: Отформатированный номер телефона

    Examples:
        {{ "79991234567"|phone_format }} -> "+7 (999) 123-45-67"
        {{ "+7 999 123 45 67"|phone_format }} -> "+7 (999) 123-45-67"
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
    Русское склонение слов в зависимости от числа.

    Выбирает правильную форму слова из трех вариантов
    для русского языка в зависимости от числа.

    Args:
        value (int): Число для которого нужно выбрать форму
        forms (str): Строка с тремя формами через запятую
            (1 объект, 2 объекта, 5 объектов)

    Returns:
        str: Правильная форма слова для указанного числа

    Examples:
        {{ 1|pluralize_ru:"помещение,помещения,помещений" }} -> "помещение"
        {{ 3|pluralize_ru:"помещение,помещения,помещений" }} -> "помещения"
        {{ 7|pluralize_ru:"помещение,помещения,помещений" }} -> "помещений"
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
    Обновление или добавление GET-параметров в URL.

    Полезно для создания ссылок пагинации и фильтрации
    с сохранением текущих параметров запроса.

    Args:
        request: Объект HTTP запроса
        **kwargs: Параметры для добавления или обновления
            (если значение None - параметр удаляется)

    Returns:
        str: URL-кодированная строка параметров

    Examples:
        {% query_transform request page=2 %} -> "page=2&search=test"
        {% query_transform request search=None %} -> удаляет search параметр
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
    Рендеринг компонента пагинации.

    Args:
        page_obj: Объект страницы Django Paginator
        request: Объект HTTP запроса для сохранения GET-параметров

    Returns:
        dict: Контекст для шаблона пагинации
    """
    return {
        'page_obj': page_obj,
        'request': request,
    }


@register.inclusion_tag('components/space_card.html')
def render_space_card(space, is_favorite=False):
    """
    Рендеринг карточки помещения.

    Args:
        space: Объект помещения (Space)
        is_favorite (bool): Флаг находится ли помещение в избранном

    Returns:
        dict: Контекст для шаблона карточки помещения
    """
    return {
        'space': space,
        'is_favorite': is_favorite,
    }


@register.filter
def timesince_hours(value):
    """
    Расчет количества часов между текущим моментом и указанной датой.

    Args:
        value (datetime): Дата для сравнения

    Returns:
        float: Количество часов до даты
            - Положительное: дата в будущем
            - Отрицательное: дата в прошлом
            - 0: ошибка или пустое значение
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
    Проверка, что до указанной даты осталось менее 24 часов.

    Args:
        value (datetime): Дата для проверки

    Returns:
        bool: True если до даты менее 24 часов, False в противном случае
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
    Форматирование длительности в часах в удобочитаемый формат.

    Преобразует количество часов в дни и часы,
    а для коротких периодов - в минуты.

    Args:
        value (float, int, str): Количество часов

    Returns:
        str: Отформатированная длительность

    Examples:
        {{ 0.5|duration_format }} -> "30 мин."
        {{ 5|duration_format }} -> "5 ч."
        {{ 30|duration_format }} -> "1 дн. 6 ч."
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
    Получение значения из словаря по ключу в шаблонах Django.

    Позволяет использовать переменные как ключи для доступа к словарям,
    что невозможно со стандартным синтаксисом {{ dictionary.key }}.

    Args:
        dictionary (dict): Словарь для поиска
        key: Ключ для поиска в словаре

    Returns:
        Любое значение найденное по ключу или None

    Examples:
        {% with my_key="title" %}
            {{ space_data|get_item:my_key }}
        {% endwith %}
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def dot_decimal(value):
    """
    Конвертирует числа с запятой в числа с точкой для CSS.

    Django использует локаль RU и форматирует числа с запятой (33,3),
    но CSS требует точку (33.3) для корректной работы width: X%.

    Args:
        value: Число или строка с числом

    Returns:
        str: Число с точкой в качестве десятичного разделителя

    Examples:
        {{ 33.3|dot_decimal }} -> "33.3"
        {{ "33,3"|dot_decimal }} -> "33.3"
    """
    if value is None:
        return "0"
    try:
        # Преобразуем в строку и заменяем запятую на точку
        str_value = str(value).replace(',', '.')
        # Проверяем что это валидное число
        float(str_value)
        return str_value
    except (ValueError, TypeError):
        return "0"
