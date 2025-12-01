"""
ГЛАВНАЯ СТРАНИЦА
"""

from django.shortcuts import render
from django.db.models import Count, Q

from ..models import Space, City, SpaceCategory


def home(request):
    """
    Главная страница сайта
    """
    # Получаем города для формы поиска
    cities = City.objects.filter(is_active=True).order_by('name')
    
    # Получаем категории для навигации
    categories = SpaceCategory.objects.filter(is_active=True).annotate(
        spaces_count=Count('spaces', filter=Q(spaces__is_active=True))
    )
    
    # Получаем рекомендуемые помещения
    featured_spaces = Space.objects.filter(
        is_active=True,
        is_featured=True
    ).select_related(
        'city', 'city__region', 'category', 'owner'
    ).prefetch_related(
        'images', 'prices', 'prices__period'
    )[:6]
    
    # Если рекомендуемых мало, добавляем последние добавленные
    if featured_spaces.count() < 6:
        featured_spaces = Space.objects.filter(
            is_active=True
        ).select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period'
        ).order_by('-created_at')[:6]
    
    # Популярные помещения (по просмотрам)
    popular_spaces = Space.objects.filter(
        is_active=True
    ).select_related(
        'city', 'category'
    ).prefetch_related(
        'images', 'prices'
    ).order_by('-views_count')[:4]
    
    # Статистика для главной страницы
    stats = {
        'spaces_count': Space.objects.filter(is_active=True).count(),
        'cities_count': City.objects.filter(
            is_active=True, 
            spaces__is_active=True
        ).distinct().count(),
        'categories_count': SpaceCategory.objects.filter(
            is_active=True,
            spaces__is_active=True
        ).distinct().count(),
    }
    
    context = {
        'cities': cities,
        'categories': categories,
        'featured_spaces': featured_spaces,
        'popular_spaces': popular_spaces,
        'stats': stats,
    }
    return render(request, 'home.html', context)
