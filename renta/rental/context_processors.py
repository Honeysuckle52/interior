"""
CONTEXT PROCESSORS
Глобальные данные, доступные во всех шаблонах
"""
from __future__ import annotations  # для поддержки forward references

from typing import Any  # добавлены type hints
from datetime import datetime  # правильный импорт

from django.http import HttpRequest  # для типизации
from django.core.cache import cache  # кеширование

from .models import City, SpaceCategory


def global_context(request: HttpRequest) -> dict[str, Any]:  # type hints
    """
    Добавляет глобальные данные в контекст всех шаблонов
    """
    header_cities = cache.get('header_cities')
    if header_cities is None:
        header_cities = list(City.objects.filter(is_active=True).order_by('name')[:20])
        cache.set('header_cities', header_cities, 60 * 15)  # 15 минут

    header_categories = cache.get('header_categories')
    if header_categories is None:
        header_categories = list(SpaceCategory.objects.filter(is_active=True).order_by('name'))
        cache.set('header_categories', header_categories, 60 * 15)  # 15 минут

    context: dict[str, Any] = {
        # Города для выпадающего списка в хедере
        'header_cities': header_cities,

        # Категории для навигации
        'header_categories': header_categories,

        # Название компании
        'company_name': 'ООО "ИНТЕРЬЕР"',
        'company_phone': '+7 (999) 123-45-67',
        'company_email': 'info@interior.ru',

        # Текущий год для футера
        'current_year': datetime.now().year,
    }

    # Количество избранного для авторизованных пользователей
    if request.user.is_authenticated:
        from .models import Favorite
        cache_key = f'favorites_count_{request.user.id}'
        favorites_count = cache.get(cache_key)
        if favorites_count is None:
            favorites_count = Favorite.objects.filter(user=request.user).count()
            cache.set(cache_key, favorites_count, 60 * 5)  # 5 минут
        context['favorites_count'] = favorites_count

    return context
