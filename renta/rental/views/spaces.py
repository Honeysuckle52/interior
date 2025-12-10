"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ ПОМЕЩЕНИЙ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для всей функциональности,
связанной с помещениями для аренды, включая просмотр списка, деталей,
фильтрацию, сортировку, а также управление помещениями для администраторов.

Основные представления:
- spaces_list: Список помещений с фильтрацией, сортировкой и пагинацией
- spaces_ajax: AJAX endpoint для динамической фильтрации помещений
- space_detail: Детальная страница помещения с отзывами, изображениями и ценами
- manage_spaces: Панель управления помещениями для администраторов
- add_space: Добавление нового помещения
- edit_space: Редактирование существующего помещения
- delete_space: Удаление помещения

Вспомогательные функции:
- _parse_int, _parse_float: Безопасный парсинг числовых значений
- _parse_smart_search: "Умный" поиск с извлечением числовых параметров
- _apply_filters: Применение фильтров к queryset
- _apply_sorting: Применение сортировки к queryset

Константы:
- DEFAULT_ITEMS_PER_PAGE: Количество элементов на странице по умолчанию
- MAX_ITEMS_PER_PAGE: Максимальное количество элементов на странице
- MIN_RATING, MAX_RATING: Границы рейтинга
- RELATED_SPACES_LIMIT: Количество похожих помещений на детальной странице
- MAX_RECENT_REVIEWS: Максимальное количество отображаемых отзывов

Особенности:
- "Умный" поиск с распознаванием числовых параметров (площадь, вместимость)
- AJAX фильтрация без перезагрузки страницы
- Оптимизированные запросы к БД с select_related и prefetch_related
- Статистика отзывов и рейтингов на детальной странице
- Пагинация с настраиваемым количеством элементов на странице
====================================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.db.models import Q, Avg, Count, Min, QuerySet
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.http import HttpRequest, HttpResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from ..models import Space, City, SpaceCategory, Favorite, SpaceImage, SpacePrice, PricingPeriod
from ..forms.spaces import SpaceForm, SpaceImageForm
from ..services.geocoding_service import geocode_address

# Константы пагинации
DEFAULT_ITEMS_PER_PAGE: int = 12
MAX_ITEMS_PER_PAGE: int = 48
MIN_RATING: int = 1
MAX_RATING: int = 5
RELATED_SPACES_LIMIT: int = 4
MAX_RECENT_REVIEWS: int = 10

logger = logging.getLogger(__name__)


def _parse_int(value: str, default: int | None = None) -> int | None:
    """
    Безопасный парсинг целочисленного значения из строки.

    Args:
        value (str): Строка для парсинга
        default (int | None): Значение по умолчанию при ошибке

    Returns:
        int | None: Распарсенное целое число или значение по умолчанию
    """
    if not value:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_float(value: str, default: float | None = None) -> float | None:
    """
    Безопасный парсинг вещественного числа из строки.

    Args:
        value (str): Строка для парсинга
        default (float | None): Значение по умолчанию при ошибке

    Returns:
        float | None: Распарсенное вещественное число или значение по умолчанию
    """
    if not value:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_smart_search(query: str) -> dict[str, Any]:
    """
    Парсинг естественно-языкового поискового запроса для извлечения структурированных фильтров.

    Примеры:
    - "100 м²" -> {'text': '', 'area': 100, 'capacity': None}
    - "50 человек" -> {'text': '', 'area': None, 'capacity': 50}
    - "офис 200 м² на 30 человек" -> {'text': 'офис', 'area': 200, 'capacity': 30}

    Args:
        query (str): Поисковый запрос пользователя

    Returns:
        dict[str, Any]: Словарь с извлеченными параметрами:
            - text: Текстовый поисковый запрос (очищенный от числовых параметров)
            - area: Извлеченная площадь помещения
            - capacity: Извлеченная вместимость помещения
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
    Применение всех фильтров к queryset помещений.

    Args:
        spaces (QuerySet[Space]): Базовый queryset помещений
        filters (dict[str, Any]): Словарь с значениями фильтров

    Returns:
        QuerySet[Space]: Отфильтрованный queryset
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
            category_ids = filters['category_ids']
            if isinstance(category_ids, list):
                spaces = spaces.filter(category_id__in=category_ids)
            else:
                spaces = spaces.filter(category_id=category_ids)

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
    Применение сортировки к queryset помещений.

    Args:
        spaces (QuerySet[Space]): Queryset для сортировки
        sort_by (str): Ключ варианта сортировки

    Returns:
        QuerySet[Space]: Отсортированный queryset
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
    Отображение пагинированного списка помещений с фильтрацией и сортировкой.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка шаблона списка помещений

    Template:
        spaces/list.html

    Context:
        - spaces: Пагинированный список помещений
        - cities: Список городов для фильтра
        - categories: Список категорий для фильтра
        - search_query: Текущий поисковый запрос
        - selected_city: Выбранный город
        - selected_categories: Выбранные категории
        - min_area, max_area, min_price, max_price, min_capacity: Числовые фильтры
        - sort_by: Текущая сортировка
        - favorite_ids: Множество ID избранных помещений для авторизованных пользователей
        - total_count: Общее количество найденных помещений
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

        category_param = request.GET.get('category', '')
        category_ids = []
        if category_param:
            parsed_id = _parse_int(category_param)
            if parsed_id:
                category_ids = [parsed_id]

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
            'selected_categories': [str(c) for c in category_ids],
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
    AJAX endpoint для динамической (живой) фильтрации помещений.

    Используется для обновления списка помещений без перезагрузки страницы.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        JsonResponse: JSON с HTML карточек и метаданными пагинации

    Response Format:
        {
            'success': bool,
            'html': str (HTML карточек),
            'total_count': int,
            'has_next': bool,
            'has_previous': bool,
            'current_page': int,
            'total_pages': int
        }
    """
    try:
        # Base queryset with optimizations
        spaces: QuerySet[Space] = Space.objects.active().select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period', 'reviews'
        )

        category_param = request.GET.get('category', '')
        category_ids = []
        if category_param:
            parsed_id = _parse_int(category_param)
            if parsed_id:
                category_ids = [parsed_id]

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
    Детальная страница помещения.

    Отображает полную информацию о помещении, включая изображения,
    цены, отзывы, статистику рейтингов и похожие помещения.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID помещения

    Returns:
        HttpResponse: Отрисовка детальной страницы помещения

    Template:
        spaces/detail.html

    Context:
        - space: Объект помещения
        - images: Все изображения помещения
        - main_image: Главное (основное) изображение
        - space_prices: Активные цены помещения по периодам
        - related_spaces: Похожие помещения (та же категория или город)
        - reviews: Последние одобренные отзывы
        - avg_rating: Средний рейтинг (округленный до 1 знака)
        - reviews_count: Общее количество одобренных отзывов
        - rating_distribution: Распределение рейтингов по звездам
        - rating_list: Список рейтингов для итерации в шаблоне
        - is_favorite: Находится ли помещение в избранном у пользователя
        - can_review: Может ли пользователь оставить отзыв для этого помещения
    """
    try:
        space: Space = get_object_or_404(
            Space.objects.select_related(
                'city', 'city__region', 'category', 'owner'
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
            'author'
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
            'rating_list': rating_list,
            'is_favorite': is_favorite,
            'can_review': can_review,
            'yandex_maps_api_key': getattr(settings, 'YANDEX_GEOCODER_API_KEY', ''),
        }
        return render(request, 'spaces/detail.html', context)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in space_detail view for pk={pk}: {e}", exc_info=True)
        return render(request, 'errors/500.html', {
            'error': 'Произошла ошибка при загрузке помещения'
        }, status=500)


@login_required
def manage_spaces(request: HttpRequest) -> HttpResponse:
    """
    Страница управления помещениями для администраторов и модераторов.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка страницы управления помещениями

    Template:
        spaces/manage.html

    Context:
        - spaces: Пагинированный список всех помещений
        - stats: Статистика помещений (всего, активных, рекомендуемых, неактивных)
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для управления помещениями')
        return redirect('dashboard')

    spaces = Space.objects.select_related(
        'city', 'category', 'owner'
    ).prefetch_related('images').order_by('-created_at')

    # Статистика
    stats = {
        'total': spaces.count(),
        'active': spaces.filter(is_active=True).count(),
        'featured': spaces.filter(is_featured=True).count(),
        'inactive': spaces.filter(is_active=False).count(),
    }

    # Пагинация
    paginator = Paginator(spaces, 12)
    page_number = request.GET.get('page', 1)
    try:
        spaces_page = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        spaces_page = paginator.get_page(1)

    return render(request, 'spaces/manage.html', {
        'spaces': spaces_page,
        'stats': stats,
    })


@login_required
def add_space(request: HttpRequest) -> HttpResponse:
    """
    Добавление нового помещения.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка формы добавления или редирект при успехе

    Template:
        spaces/add.html

    Context:
        - form: Форма добавления помещения
        - pricing_periods: Все доступные периоды ценообразования
        - yandex_api_key: API ключ Яндекс.Карт для геокодирования
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для добавления помещений')
        return redirect('dashboard')

    pricing_periods = PricingPeriod.objects.all().order_by('sort_order')
    yandex_api_key = getattr(settings, 'YANDEX_MAPS_API_KEY', '')

    if request.method == 'POST':
        form = SpaceForm(request.POST)
        images = request.FILES.getlist('images')
        if not images:
            messages.error(request, 'Необходимо загрузить хотя бы одну фотографию помещения')
            return render(request, 'spaces/add.html', {
                'form': form,
                'pricing_periods': pricing_periods,
                'yandex_api_key': yandex_api_key,
            })

        if form.is_valid():
            space = form.save(commit=False)
            space.owner = request.user

            # Серверное геокодирование убрано - используется клиентское через ymaps.geocode()
            space.latitude = request.POST.get('latitude')
            space.longitude = request.POST.get('longitude')

            space.save()

            # Сохраняем изображения
            for i, image_file in enumerate(images):
                SpaceImage.objects.create(
                    space=space,
                    image=image_file,
                    is_primary=(i == 0),
                    sort_order=i
                )

            # Сохраняем цены
            for period in pricing_periods:
                price_value = request.POST.get(f'price_{period.id}')
                if price_value:
                    try:
                        SpacePrice.objects.create(
                            space=space,
                            period=period,
                            price=float(price_value),
                            is_active=True
                        )
                    except (ValueError, TypeError):
                        pass

            messages.success(request, f'Помещение "{space.title}" успешно добавлено')
            return redirect('manage_spaces')
    else:
        form = SpaceForm()

    return render(request, 'spaces/add.html', {
        'form': form,
        'pricing_periods': pricing_periods,
        'yandex_api_key': yandex_api_key,
    })


@login_required
def edit_space(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование существующего помещения.
    """
    space = get_object_or_404(Space, pk=pk)

    if not request.user.can_moderate and space.owner != request.user:
        messages.error(request, 'У вас нет прав для редактирования этого помещения')
        return redirect('dashboard')

    pricing_periods = PricingPeriod.objects.all().order_by('sort_order')
    current_prices = {sp.period_id: sp.price for sp in space.prices.all()}
    yandex_api_key = getattr(settings, 'YANDEX_MAPS_API_KEY', '')

    if request.method == 'POST':
        form = SpaceForm(request.POST, instance=space)
        if form.is_valid():
            space = form.save(commit=False)

            # Серверное геокодирование убрано - используется клиентское через ymaps.geocode()
            space.latitude = request.POST.get('latitude')
            space.longitude = request.POST.get('longitude')

            space.save()

            # Обновляем цены
            for period in pricing_periods:
                price_value = request.POST.get(f'price_{period.id}')
                if price_value:
                    try:
                        SpacePrice.objects.update_or_create(
                            space=space,
                            period=period,
                            defaults={'price': float(price_value), 'is_active': True}
                        )
                    except (ValueError, TypeError):
                        pass

            # Обработка новых изображений
            new_images = request.FILES.getlist('images')
            if new_images:
                max_order = space.images.count()
                for i, image_file in enumerate(new_images):
                    SpaceImage.objects.create(
                        space=space,
                        image=image_file,
                        is_primary=False,
                        sort_order=max_order + i
                    )

            # Обработка удаления изображений
            delete_images = request.POST.getlist('delete_images')
            if delete_images:
                SpaceImage.objects.filter(id__in=delete_images, space=space).delete()

            # Обработка главного изображения
            primary_image_id = request.POST.get('primary_image')
            if primary_image_id:
                space.images.update(is_primary=False)
                space.images.filter(id=primary_image_id).update(is_primary=True)

            messages.success(request, f'Помещение "{space.title}" успешно обновлено')
            return redirect('manage_spaces')
    else:
        form = SpaceForm(instance=space)

    return render(request, 'spaces/edit.html', {
        'form': form,
        'space': space,
        'pricing_periods': pricing_periods,
        'current_prices': current_prices,
        'yandex_api_key': yandex_api_key,
    })


@login_required
def delete_space(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Удаление помещения.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID помещения для удаления

    Returns:
        HttpResponse: Редирект на страницу управления помещениями
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для удаления помещений')
        return redirect('dashboard')

    space = get_object_or_404(Space, pk=pk)

    if request.method == 'POST':
        space_title = space.title
        space.delete()
        messages.success(request, f'Помещение "{space_title}" успешно удалено')

    return redirect('manage_spaces')
