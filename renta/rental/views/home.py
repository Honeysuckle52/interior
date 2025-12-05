"""
ГЛАВНАЯ СТРАНИЦА

Displays featured spaces, categories, and statistics.
"""

from __future__ import annotations

import logging

from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..models import Space, City, SpaceCategory


logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    """
    Display homepage with featured content.

    Args:
        request: HTTP request

    Returns:
        Rendered homepage template
    """
    try:
        # Cities for search form
        cities = City.objects.filter(is_active=True).order_by('name')

        # Categories with space counts
        categories = SpaceCategory.objects.filter(is_active=True).annotate(
            spaces_count=Count('spaces', filter=Q(spaces__is_active=True))
        )

        # Featured spaces
        featured_spaces = Space.objects.featured().with_relations()[:6]

        # If not enough featured, get newest
        if featured_spaces.count() < 6:
            featured_spaces = Space.objects.active().with_relations().order_by(
                '-created_at'
            )[:6]

        # Popular spaces by views
        popular_spaces = Space.objects.active().select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        ).order_by('-views_count')[:4]

        # Homepage statistics
        stats = {
            'spaces_count': Space.objects.active().count(),
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

    except Exception as e:
        logger.error(f"Error in home view: {e}", exc_info=True)
        # Return minimal context on error
        return render(request, 'home.html', {
            'cities': [],
            'categories': [],
            'featured_spaces': [],
            'popular_spaces': [],
            'stats': {'spaces_count': 0, 'cities_count': 0, 'categories_count': 0},
            'error': 'Произошла ошибка при загрузке данных'
        })
