"""
ПРЕДСТАВЛЕНИЯ ДЛЯ ПОМЕЩЕНИЙ

Handles listing and detail views for rental spaces with filtering,
sorting, and pagination support.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Q, Avg, Count, Min, QuerySet
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404

from ..models import Space, City, SpaceCategory, Favorite


logger = logging.getLogger(__name__)


def _parse_int(value: str, default: int | None = None) -> int | None:
    """Safely parse integer from string."""
    if not value:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_float(value: str, default: float | None = None) -> float | None:
    """Safely parse float from string."""
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _apply_filters(
    spaces: QuerySet[Space],
    filters: dict[str, Any]
) -> QuerySet[Space]:
    """
    Apply all filters to the spaces queryset.

    Args:
        spaces: Base queryset
        filters: Dictionary with filter values

    Returns:
        Filtered queryset
    """
    try:
        if filters.get('search_query'):
            spaces = spaces.filter(
                Q(title__icontains=filters['search_query']) |
                Q(description__icontains=filters['search_query']) |
                Q(address__icontains=filters['search_query']) |
                Q(city__name__icontains=filters['search_query'])
            )

        if filters.get('city_id'):
            spaces = spaces.filter(city_id=filters['city_id'])

        if filters.get('category_id'):
            spaces = spaces.filter(category_id=filters['category_id'])

        if filters.get('min_area'):
            spaces = spaces.filter(area_sqm__gte=filters['min_area'])

        if filters.get('max_area'):
            spaces = spaces.filter(area_sqm__lte=filters['max_area'])

        if filters.get('min_capacity'):
            spaces = spaces.filter(max_capacity__gte=filters['min_capacity'])

        if filters.get('min_price'):
            spaces = spaces.filter(
                prices__price__gte=filters['min_price'],
                prices__is_active=True
            )

        if filters.get('max_price'):
            spaces = spaces.filter(
                prices__price__lte=filters['max_price'],
                prices__is_active=True
            )

        return spaces.distinct()
    except Exception as e:
        logger.error(f"Error applying filters: {e}", exc_info=True)
        return spaces.distinct()


def _apply_sorting(spaces: QuerySet[Space], sort_by: str) -> QuerySet[Space]:
    """
    Apply sorting to the spaces queryset.

    Args:
        spaces: Queryset to sort
        sort_by: Sort option key

    Returns:
        Sorted queryset
    """
    sort_options = {
        'price_asc': 'min_price_value',
        'price_desc': '-min_price_value',
        'area_asc': 'area_sqm',
        'area_desc': '-area_sqm',
        'newest': '-created_at',
        'popular': '-views_count',
        'rating': '-avg_rating',
    }
    order_field = sort_options.get(sort_by, '-created_at')
    try:
        return spaces.order_by(order_field)
    except Exception as e:
        logger.error(f"Error applying sorting: {e}", exc_info=True)
        return spaces.order_by('-created_at')


def spaces_list(request: HttpRequest) -> HttpResponse:
    """
    Display paginated list of spaces with filtering and sorting.

    Args:
        request: HTTP request object

    Returns:
        Rendered spaces list template
    """
    try:
        # Base queryset with optimizations
        spaces = Space.objects.active().select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period', 'reviews'
        )

        # Get filter data
        cities = City.objects.filter(is_active=True).order_by('name')
        categories = SpaceCategory.objects.filter(is_active=True).order_by('name')

        # Parse filter parameters
        filters = {
            'search_query': request.GET.get('search', '').strip(),
            'city_id': _parse_int(request.GET.get('city', '')),
            'category_id': _parse_int(request.GET.get('category', '')),
            'min_area': _parse_float(request.GET.get('min_area', '')),
            'max_area': _parse_float(request.GET.get('max_area', '')),
            'min_capacity': _parse_int(request.GET.get('min_capacity', '')),
            'min_price': _parse_float(request.GET.get('min_price', '')),
            'max_price': _parse_float(request.GET.get('max_price', '')),
        }
        sort_by = request.GET.get('sort', 'newest')

        # Apply filters
        spaces = _apply_filters(spaces, filters)

        # Add annotations for sorting and display
        spaces = spaces.annotate(
            min_price_value=Min('prices__price'),
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews', filter=Q(reviews__is_approved=True))
        )

        # Apply sorting
        spaces = _apply_sorting(spaces, sort_by)

        # Pagination
        per_page = min(_parse_int(request.GET.get('per_page', ''), 12) or 12, 48)
        paginator = Paginator(spaces, per_page)
        page_number = request.GET.get('page', 1)

        try:
            spaces_page: Page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            spaces_page = paginator.get_page(1)

        # Get favorite IDs for authenticated users
        favorite_ids: set[int] = set()
        if request.user.is_authenticated:
            favorite_ids = set(
                Favorite.objects.filter(user=request.user)
                .values_list('space_id', flat=True)
            )

        context = {
            'spaces': spaces_page,
            'cities': cities,
            'categories': categories,
            'search_query': filters['search_query'],
            'selected_city': request.GET.get('city', ''),
            'selected_category': request.GET.get('category', ''),
            'min_area': request.GET.get('min_area', ''),
            'max_area': request.GET.get('max_area', ''),
            'min_price': request.GET.get('min_price', ''),
            'max_price': request.GET.get('max_price', ''),
            'min_capacity': request.GET.get('min_capacity', ''),
            'sort_by': sort_by,
            'favorite_ids': favorite_ids,
            'total_count': paginator.count,
        }
        return render(request, 'spaces/list.html', context)

    except Exception as e:
        logger.error(f"Error in spaces_list view: {e}", exc_info=True)
        return render(request, 'spaces/list.html', {
            'spaces': [],
            'cities': [],
            'categories': [],
            'error': 'Произошла ошибка при загрузке помещений'
        })


def space_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Display detailed information about a specific space.

    Args:
        request: HTTP request object
        pk: Space primary key

    Returns:
        Rendered space detail template
    """
    try:
        space = get_object_or_404(
            Space.objects.select_related(
                'city', 'city__region', 'category', 'owner', 'owner__profile'
            ).prefetch_related(
                'images',
                'prices',
                'prices__period',
                'reviews',
                'reviews__author'
            ),
            pk=pk,
            is_active=True
        )

        # Atomically increment views counter
        try:
            space.increment_views()
        except Exception as e:
            logger.warning(f"Failed to increment views for space {pk}: {e}")

        # Get images
        images = space.get_all_images()
        main_image = images.filter(is_primary=True).first() or images.first()

        # Get active prices
        space_prices = space.prices.filter(is_active=True).select_related('period')

        # Related spaces (same category or city)
        related_spaces = Space.objects.active().filter(
            Q(category=space.category) | Q(city=space.city)
        ).exclude(
            pk=pk
        ).select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        ).annotate(
            min_price_value=Min('prices__price')
        ).order_by('?')[:4]

        # Approved reviews with stats
        approved_reviews = space.reviews.filter(is_approved=True)
        reviews = approved_reviews.select_related(
            'author', 'author__profile'
        ).order_by('-created_at')[:10]

        reviews_stats = approved_reviews.aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id')
        )
        avg_rating = reviews_stats['avg_rating'] or 0
        reviews_count = reviews_stats['total_count'] or 0

        # Rating distribution
        rating_distribution = {
            i: approved_reviews.filter(rating=i).count()
            for i in range(1, 6)
        }

        # Check favorite and review permissions for authenticated users
        is_favorite = False
        can_review = False
        if request.user.is_authenticated:
            is_favorite = Favorite.objects.filter(
                user=request.user, space=space
            ).exists()
            can_review = not space.reviews.filter(author=request.user).exists()

        context = {
            'space': space,
            'images': images,
            'main_image': main_image,
            'space_prices': space_prices,
            'related_spaces': related_spaces,
            'reviews': reviews,
            'avg_rating': round(avg_rating, 1),
            'reviews_count': reviews_count,
            'rating_distribution': rating_distribution,
            'is_favorite': is_favorite,
            'can_review': can_review,
        }
        return render(request, 'spaces/detail.html', context)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in space_detail view for pk={pk}: {e}", exc_info=True)
        return render(request, 'errors/500.html', {
            'error': 'Произошла ошибка при загрузке помещения'
        }, status=500)
