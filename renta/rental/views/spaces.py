"""
ПРЕДСТАВЛЕНИЯ ДЛЯ ПОМЕЩЕНИЙ
"""

from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Avg, Count, Min
from django.core.paginator import Paginator

from ..models import Space, City, SpaceCategory, Favorite


def spaces_list(request):
    """
    Страница со списком всех помещений и фильтрацией
    """
    # Базовый queryset с оптимизацией
    spaces = Space.objects.filter(is_active=True).select_related(
        'city', 'city__region', 'category', 'owner'
    ).prefetch_related(
        'images', 'prices', 'prices__period', 'reviews'
    )
    
    # Получаем данные для фильтров
    cities = City.objects.filter(is_active=True).order_by('name')
    categories = SpaceCategory.objects.filter(is_active=True).order_by('name')
    
    # Обработка фильтров
    search_query = request.GET.get('search', '').strip()
    selected_city = request.GET.get('city', '')
    selected_category = request.GET.get('category', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_capacity = request.GET.get('min_capacity', '')
    sort_by = request.GET.get('sort', 'newest')
    
    # Применяем фильтры
    if search_query:
        spaces = spaces.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__name__icontains=search_query)
        )
    
    if selected_city:
        try:
            spaces = spaces.filter(city_id=int(selected_city))
        except ValueError:
            pass
    
    if selected_category:
        try:
            spaces = spaces.filter(category_id=int(selected_category))
        except ValueError:
            pass
    
    if min_area:
        try:
            spaces = spaces.filter(area_sqm__gte=float(min_area))
        except ValueError:
            pass
    
    if max_area:
        try:
            spaces = spaces.filter(area_sqm__lte=float(max_area))
        except ValueError:
            pass
    
    if min_capacity:
        try:
            spaces = spaces.filter(max_capacity__gte=int(min_capacity))
        except ValueError:
            pass
    
    # Фильтр по цене (через подзапрос)
    if min_price:
        try:
            spaces = spaces.filter(
                prices__price__gte=float(min_price), 
                prices__is_active=True
            )
        except ValueError:
            pass
    
    if max_price:
        try:
            spaces = spaces.filter(
                prices__price__lte=float(max_price), 
                prices__is_active=True
            )
        except ValueError:
            pass
    
    # Убираем дубликаты (могут появиться из-за join с ценами)
    spaces = spaces.distinct()
    
    # Добавляем аннотации для сортировки и отображения
    spaces = spaces.annotate(
        min_price_value=Min('prices__price'),
        avg_rating=Avg('reviews__rating'),
        reviews_count=Count('reviews', filter=Q(reviews__is_approved=True))
    )
    
    # Сортировка
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
    spaces = spaces.order_by(order_field)
    
    # Пагинация
    per_page = request.GET.get('per_page', 12)
    try:
        per_page = min(int(per_page), 48)  # Максимум 48 на страницу
    except ValueError:
        per_page = 12
    
    paginator = Paginator(spaces, per_page)
    page_number = request.GET.get('page', 1)
    spaces_page = paginator.get_page(page_number)
    
    # Проверяем избранное для авторизованного пользователя
    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(
            Favorite.objects.filter(user=request.user)
            .values_list('space_id', flat=True)
        )
    
    context = {
        'spaces': spaces_page,
        'cities': cities,
        'categories': categories,
        'search_query': search_query,
        'selected_city': selected_city,
        'selected_category': selected_category,
        'min_area': min_area,
        'max_area': max_area,
        'min_price': min_price,
        'max_price': max_price,
        'min_capacity': min_capacity,
        'sort_by': sort_by,
        'favorite_ids': favorite_ids,
        'total_count': paginator.count,
    }
    return render(request, 'spaces/list.html', context)


def space_detail(request, pk):
    """
    Страница с детальной информацией о помещении
    """
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
    
    # Увеличиваем счетчик просмотров (атомарно)
    Space.objects.filter(pk=pk).update(views_count=space.views_count + 1)
    
    # Получаем все изображения
    images = space.images.all().order_by('-is_primary', 'sort_order')
    main_image = images.filter(is_primary=True).first() or images.first()
    
    # Получаем активные цены
    space_prices = space.prices.filter(is_active=True).select_related('period')
    
    # Похожие помещения (по категории, городу, площади)
    related_spaces = Space.objects.filter(
        is_active=True
    ).filter(
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
    
    # Отзывы (одобренные)
    reviews = space.reviews.filter(is_approved=True).select_related(
        'author', 'author__profile'
    ).order_by('-created_at')[:10]
    
    # Агрегация отзывов
    reviews_stats = space.reviews.filter(is_approved=True).aggregate(
        avg_rating=Avg('rating'),
        total_count=Count('id')
    )
    avg_rating = reviews_stats['avg_rating'] or 0
    reviews_count = reviews_stats['total_count'] or 0
    
    # Распределение рейтингов
    rating_distribution = {}
    for i in range(1, 6):
        rating_distribution[i] = space.reviews.filter(
            is_approved=True, rating=i
        ).count()
    
    # Проверяем, в избранном ли (для авторизованных)
    is_favorite = False
    can_review = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(
            user=request.user, space=space
        ).exists()
        # Может оставить отзыв, если ещё не оставлял
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
