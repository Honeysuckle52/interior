"""
====================================================================
CONTEXT PROCESSORS ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит контекстные процессоры Django, которые добавляют
глобальные данные во все шаблоны сайта, обеспечивая единый доступ
к общим данным без необходимости передачи их в каждое представление.

Основной контекстный процессор:
- global_context: Добавляет глобальные данные в контекст всех шаблонов

Глобальные данные:
- header_cities: Список активных городов для выпадающего меню в хедере
- header_categories: Список активных категорий для навигации
- company_name, company_phone, company_email: Контактная информация компании
- current_year: Текущий год для отображения в футере
- favorites_count: Количество избранных помещений для авторизованных пользователей

Особенности:
- Использование кэширования для оптимизации производительности
- Умное обновление кэша при изменении данных (кэш сбрасывается при CRUD операциях)
- Динамическое обновление счетчика избранного для каждого пользователя
- Поддержка type hints для лучшей читаемости кода
====================================================================
"""

from __future__ import annotations  # для поддержки forward references

from typing import Any  # добавлены type hints
from datetime import datetime  # правильный импорт

from django.http import HttpRequest  # для типизации
from django.core.cache import cache  # кеширование

from .models import City, SpaceCategory


def global_context(request: HttpRequest) -> dict[str, Any]:
    """
    Добавляет глобальные данные в контекст всех шаблонов.

    Этот контекстный процессор автоматически вызывается Django
    при рендеринге любого шаблона и добавляет указанные данные
    в контекст шаблона.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        dict[str, Any]: Словарь с глобальными данными для шаблонов

    Ключи словаря:
        - header_cities: Список активных городов (кешируется на 15 минут)
        - header_categories: Список активных категорий (кешируется на 15 минут)
        - company_name: Название компании
        - company_phone: Телефон компании
        - company_email: Email компании
        - current_year: Текущий год для футера
        - favorites_count: Количество избранных помещений (только для авторизованных пользователей)
    """
    # Кеширование списка городов для хедера
    header_cities = cache.get('header_cities')
    if header_cities is None:
        header_cities = list(City.objects.filter(is_active=True).order_by('name')[:20])
        cache.set('header_cities', header_cities, 60 * 15)  # 15 минут

    # Кеширование списка категорий для хедера
    header_categories = cache.get('header_categories')
    if header_categories is None:
        header_categories = list(SpaceCategory.objects.filter(is_active=True).order_by('name'))
        cache.set('header_categories', header_categories, 60 * 15)  # 15 минут

    # Базовый контекст
    context: dict[str, Any] = {
        # Города для выпадающего списка в хедере (кешируются)
        'header_cities': header_cities,

        # Категории для навигации (кешируются)
        'header_categories': header_categories,

        # Название компании
        'company_name': 'ООО "ИНТЕРЬЕР"',

        # Контактный телефон компании
        'company_phone': '+7 (999) 123-45-67',

        # Email компании
        'company_email': 'info@interior.ru',

        # Текущий год для футера (обновляется автоматически)
        'current_year': datetime.now().year,
    }

    # Количество избранного для авторизованных пользователей
    if request.user.is_authenticated:
        from .models import Favorite

        # Уникальный ключ кэша для каждого пользователя
        cache_key = f'favorites_count_{request.user.id}'
        favorites_count = cache.get(cache_key)

        if favorites_count is None:
            # Получаем актуальное количество избранных помещений
            favorites_count = Favorite.objects.filter(user=request.user).count()
            # Кэшируем на 5 минут
            cache.set(cache_key, favorites_count, 60 * 5)

        context['favorites_count'] = favorites_count

    return context