"""
ПРЕДСТАВЛЕНИЯ ДЛЯ ПОМЕЩЕНИЙ

Handles listing and detail views for rental spaces with filtering,
sorting, and pagination support.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.db.models import Q, Avg, Count, Min, QuerySet
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.http import HttpRequest, HttpResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string

from ..models import Space, City, SpaceCategory, Favorite

# Константы пагинации
DEFAULT_ITEMS_PER_PAGE: int = 12
MAX_ITEMS_PER_PAGE: int = 48
MIN_RATING: int = 1
MAX_RATING: int = 5
RELATED_SPACES_LIMIT: int = 4
MAX_RECENT_REVIEWS: int = 10

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


def _parse_smart_search(query: str) -> dict[str, Any]:
    """
    Parse natural language search query to extract structured filters.
    Examples:
    - "100 м²" -> {'area': 100}
    - "50 человек" -> {'capacity': 50}
    - "офис 200 м² на 30 человек" -> {'text': 'офис', 'area': 200, 'capacity': 30}
    """
    result = {'text': query, 'area': None, 'capacity': None}

    # Extract area (м², кв.м, квадратов, метров)
    area_patterns = [
        r'(\d+)\s*(?:м²|м2|кв\.?\s*м|квадрат\w*|метр\w*)',
        r'площад\w*\s*(\d+)',
        r'(\d+)\s*(?:квадрат|метр)',
    ]
    for pattern in area_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            result['area'] = int(match.group(1))
            # Remove matched part from text search
            result['text'] = re.sub(pattern, '', result['text'], flags=re.IGNORECASE)
            break

    # Extract capacity (человек, чел, людей, мест, гостей)
    capacity_patterns = [
        r'(?:на|до|для)?\s*(\d+)\s*(?:человек|чел\.?|люд\w*|мест\w*|гост\w*|персон)',
        r'вместимост\w*\s*(\d+)',
        r'(\d+)\s*(?:человек|чел|люд)',
    ]
    for pattern in capacity_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            result['capacity'] = int(match.group(1))
            result['text'] = re.sub(pattern, '', result['text'], flags=re.IGNORECASE)
            break

    # Clean up remaining text
    result['text'] = ' '.join(result['text'].split()).strip()

    return result


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
            parsed = _parse_smart_search(filters['search_query'])

            # Apply text search
            if parsed['text']:
                spaces = spaces.filter(
                    Q(title__icontains=parsed['text']) |
                    Q(description__icontains=parsed['text']) |
                    Q(address__icontains=parsed['text']) |
                    Q(city__name__icontains=parsed['text']) |
                    Q(category__name__icontains=parsed['text'])
                )

            # Apply parsed area filter
            if parsed['area']:
                # Search for spaces with area close to requested (±20%)
                min_area = parsed['area'] * 0.8
                max_area = parsed['area'] * 1.2
                spaces = spaces.filter(area_sqm__gte=min_area, area_sqm__lte=max_area)

            # Apply parsed capacity filter
            if parsed['capacity']:
                spaces = spaces.filter(max_capacity__gte=parsed['capacity'])

        if filters.get('city_id'):
            spaces = spaces.filter(city_id=filters['city_id'])

        if filters.get('category_ids'):
            spaces = spaces.filter(category_id__in=filters['category_ids'])

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
    sort_options: dict[str, str] = {
        'price_asc': 'min_price_value',
        'price_desc': '-min_price_value',
        'area_asc': 'area_sqm',
        'area_desc': '-area_sqm',
        'newest': '-created_at',
        'popular': '-views_count',
        'rating': '-avg_rating',
    }
    order_field: str = sort_options.get(sort_by, '-created_at')
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
        spaces: QuerySet[Space] = Space.objects.active().select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period', 'reviews'
        )

        # Get filter data
        cities: QuerySet[City] = City.objects.filter(is_active=True).order_by('name')
        categories: QuerySet[SpaceCategory] = SpaceCategory.objects.filter(is_active=True).order_by('name')

        category_ids = request.GET.getlist('category')
        category_ids = [_parse_int(c) for c in category_ids if _parse_int(c)]

        # Parse filter parameters
        filters: dict[str, Any] = {
            'search_query': request.GET.get('search', '').strip(),
            'city_id': _parse_int(request.GET.get('city', '')),
            'category_ids': category_ids if category_ids else None,
            'min_area': _parse_float(request.GET.get('min_area', '')),
            'max_area': _parse_float(request.GET.get('max_area', '')),
            'min_capacity': _parse_int(request.GET.get('min_capacity', '')),
            'min_price': _parse_float(request.GET.get('min_price', '')),
            'max_price': _parse_float(request.GET.get('max_price', '')),
        }
        sort_by: str = request.GET.get('sort', 'newest')

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
        per_page: int = min(
            _parse_int(request.GET.get('per_page', ''), DEFAULT_ITEMS_PER_PAGE) or DEFAULT_ITEMS_PER_PAGE,
            MAX_ITEMS_PER_PAGE
        )
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

        context: dict[str, Any] = {
            'spaces': spaces_page,
            'cities': cities,
            'categories': categories,
            'search_query': filters['search_query'],
            'selected_city': request.GET.get('city', ''),
            'selected_categories': [str(c) for c in category_ids],  # List of selected categories
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


def spaces_ajax(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint для живой фильтрации помещений.
    Возвращает HTML карточек и количество результатов.
    """
    try:
        # Base queryset with optimizations
        spaces: QuerySet[Space] = Space.objects.active().select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period', 'reviews'
        )

        category_ids = request.GET.getlist('category')
        category_ids = [_parse_int(c) for c in category_ids if _parse_int(c)]

        # Parse filter parameters
        filters: dict[str, Any] = {
            'search_query': request.GET.get('search', '').strip(),
            'city_id': _parse_int(request.GET.get('city', '')),
            'category_ids': category_ids if category_ids else None,
            'min_area': _parse_float(request.GET.get('min_area', '')),
            'max_area': _parse_float(request.GET.get('max_area', '')),
            'min_capacity': _parse_int(request.GET.get('min_capacity', '')),
            'min_price': _parse_float(request.GET.get('min_price', '')),
            'max_price': _parse_float(request.GET.get('max_price', '')),
        }
        sort_by: str = request.GET.get('sort', 'newest')

        # Apply filters
        spaces = _apply_filters(spaces, filters)

        # Add annotations
        spaces = spaces.annotate(
            min_price_value=Min('prices__price'),
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews', filter=Q(reviews__is_approved=True))
        )

        # Apply sorting
        spaces = _apply_sorting(spaces, sort_by)

        # Pagination
        per_page: int = min(
            _parse_int(request.GET.get('per_page', ''), DEFAULT_ITEMS_PER_PAGE) or DEFAULT_ITEMS_PER_PAGE,
            MAX_ITEMS_PER_PAGE
        )
        paginator = Paginator(spaces, per_page)
        page_number = request.GET.get('page', 1)

        try:
            spaces_page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            spaces_page = paginator.get_page(1)

        # Get favorite IDs for authenticated users
        favorite_ids: set[int] = set()
        if request.user.is_authenticated:
            favorite_ids = set(
                Favorite.objects.filter(user=request.user)
                .values_list('space_id', flat=True)
            )

        # Рендерим только карточки
        html = render_to_string('spaces/_spaces_grid.html', {
            'spaces': spaces_page,
            'favorite_ids': favorite_ids,
        }, request=request)

        return JsonResponse({
            'success': True,
            'html': html,
            'total_count': paginator.count,
            'has_next': spaces_page.has_next(),
            'has_previous': spaces_page.has_previous(),
            'current_page': spaces_page.number,
            'total_pages': paginator.num_pages,
        })

    except Exception as e:
        logger.error(f"Error in spaces_ajax: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
        space: Space = get_object_or_404(
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
        related_spaces: QuerySet[Space] = Space.objects.active().filter(
            Q(category=space.category) | Q(city=space.city)
        ).exclude(
            pk=pk
        ).select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        ).annotate(
            min_price_value=Min('prices__price')
        ).order_by('?')[:RELATED_SPACES_LIMIT]

        # Approved reviews with stats
        approved_reviews = space.reviews.filter(is_approved=True)
        reviews = approved_reviews.select_related(
            'author', 'author__profile'
        ).order_by('-created_at')[:MAX_RECENT_REVIEWS]

        reviews_stats: dict[str, Any] = approved_reviews.aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id')
        )
        avg_rating: float = reviews_stats['avg_rating'] or 0
        reviews_count: int = reviews_stats['total_count'] or 0

        # Rating distribution
        rating_distribution: dict[int, int] = {
            i: approved_reviews.filter(rating=i).count()
            for i in range(MIN_RATING, MAX_RATING + 1)
        }

        # Convert to list for template iteration
        rating_list = []
        for star in range(5, 0, -1):
            count = rating_distribution.get(star, 0)
            percent = (count / reviews_count * 100) if reviews_count > 0 else 0
            rating_list.append({
                'star': star,
                'count': count,
                'percent': round(percent, 1)
            })

        # Check favorite and review permissions for authenticated users
        is_favorite: bool = False
        can_review: bool = False
        if request.user.is_authenticated:
            is_favorite = Favorite.objects.filter(
                user=request.user, space=space
            ).exists()
            can_review = not space.reviews.filter(author=request.user).exists()

        context: dict[str, Any] = {
            'space': space,
            'images': images,
            'main_image': main_image,
            'space_prices': space_prices,
            'related_spaces': related_spaces,
            'reviews': reviews,
            'avg_rating': round(avg_rating, 1),
            'reviews_count': reviews_count,
            'rating_distribution': rating_distribution,
            'rating_list': rating_list,  # Added for template iteration
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
