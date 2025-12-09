"""
====================================================================
ГЛАВНАЯ СТРАНИЦА САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представление главной страницы сайта, которое
отображает рекомендуемые помещения, популярные категории, города
и общую статистику платформы.

Основное представление:
- home: Главная страница сайта с различными секциями контента

Константы:
- FEATURED_SPACES_LIMIT: Количество рекомендуемых помещений для отображения
- POPULAR_SPACES_LIMIT: Количество популярных помещений для отображения

Секции главной страницы:
1. Форма поиска помещений с фильтрацией по городам
2. Популярные категории помещений с количеством доступных помещений
3. Рекомендуемые (featured) помещения
4. Популярные помещения (по количеству просмотров)
5. Статистика платформы

Особенности:
- Использование кастомных менеджеров моделей (featured(), active(), with_relations())
- Аннотации для подсчета количества помещений в категориях
- Резервный механизм: если недостаточно рекомендуемых помещений,
  отображаются последние добавленные помещения
- Обработка ошибок с предоставлением минимального контекста при сбое
====================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..models import Space, City, SpaceCategory, CustomUser

# Константы
FEATURED_SPACES_LIMIT: int = 6
POPULAR_SPACES_LIMIT: int = 4

logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    """
    Отображение главной страницы с рекомендуемым контентом.

    Главная страница включает:
    - Список городов для формы поиска
    - Категории помещений с количеством доступных помещений
    - Рекомендуемые (featured) помещения
    - Популярные помещения (по количеству просмотров)
    - Статистику платформы

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка шаблона главной страницы

    Template:
        home.html

    Context:
        - cities: Активные города для формы поиска
        - categories: Активные категории с количеством помещений
        - featured_spaces: Рекомендуемые помещения
        - popular_spaces: Популярные помещения (по просмотрам)
        - stats: Статистика платформы
        - error: Сообщение об ошибке (при наличии)
    """
    try:
        # Cities for search form
        cities: QuerySet[City] = City.objects.filter(is_active=True).order_by('name')

        # Categories with space counts
        categories: QuerySet[SpaceCategory] = SpaceCategory.objects.filter(is_active=True).annotate(
            spaces_count=Count('spaces', filter=Q(spaces__is_active=True))
        )

        # Featured spaces
        featured_spaces: QuerySet[Space] = Space.objects.featured().with_relations()[:FEATURED_SPACES_LIMIT]

        # Если недостаточно рекомендуемых помещений, показываем последние добавленные
        if featured_spaces.count() < FEATURED_SPACES_LIMIT:
            featured_spaces = Space.objects.active().with_relations().order_by(
                '-created_at'
            )[:FEATURED_SPACES_LIMIT]

        # Popular spaces by views
        popular_spaces: QuerySet[Space] = Space.objects.active().select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        ).order_by('-views_count')[:POPULAR_SPACES_LIMIT]

        # Platform statistics
        stats: dict[str, int] = {
            'spaces_count': Space.objects.active().count(),
            'cities_count': City.objects.filter(
                is_active=True,
                spaces__is_active=True
            ).distinct().count(),
            'categories_count': SpaceCategory.objects.filter(
                is_active=True,
                spaces__is_active=True
            ).distinct().count(),
            # Добавлен счетчик пользователей
            'users_count': CustomUser.objects.filter(is_active=True).count(),
        }

        context: dict[str, Any] = {
            'cities': cities,
            'categories': categories,
            'featured_spaces': featured_spaces,
            'popular_spaces': popular_spaces,
            'stats': stats,
        }
        return render(request, 'home.html', context)

    except Exception as e:
        logger.error(f"Error in home view: {e}", exc_info=True)
        # Return minimal context on error for graceful degradation
        return render(request, 'home.html', {
            'cities': [],
            'categories': [],
            'featured_spaces': [],
            'popular_spaces': [],
            'stats': {'spaces_count': 0, 'cities_count': 0, 'categories_count': 0, 'users_count': 0},
            'error': 'Произошла ошибка при загрузке данных'
        })