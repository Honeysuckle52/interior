"""
СЕРВИС ПОМЕЩЕНИЙ
Бизнес-логика для работы с помещениями
"""

from django.db.models import Q, Avg, Count, Min
from django.core.paginator import Paginator

from ..models import Space, City, SpaceCategory, Favorite, Review


class SpaceService:
    """Сервис для работы с помещениями"""

    @staticmethod
    def get_filtered_spaces(
        search: str = None,
        city_id: int = None,
        category_id: int = None,
        min_area: float = None,
        max_area: float = None,
        min_price: float = None,
        max_price: float = None,
        min_capacity: int = None,
        sort_by: str = 'newest',
        page: int = 1,
        per_page: int = 12
    ):
        """
        Получить отфильтрованный список помещений с пагинацией
        
        Returns:
            tuple: (Page объект, общее количество)
        """
        spaces = Space.objects.filter(is_active=True).select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period', 'reviews'
        )
        
        # Поиск по тексту
        if search:
            spaces = spaces.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(address__icontains=search) |
                Q(city__name__icontains=search)
            )
        
        # Фильтры
        if city_id:
            spaces = spaces.filter(city_id=city_id)
        
        if category_id:
            spaces = spaces.filter(category_id=category_id)
        
        if min_area:
            spaces = spaces.filter(area_sqm__gte=min_area)
        
        if max_area:
            spaces = spaces.filter(area_sqm__lte=max_area)
        
        if min_capacity:
            spaces = spaces.filter(max_capacity__gte=min_capacity)
        
        if min_price:
            spaces = spaces.filter(prices__price__gte=min_price, prices__is_active=True)
        
        if max_price:
            spaces = spaces.filter(prices__price__lte=max_price, prices__is_active=True)
        
        # Убираем дубликаты
        spaces = spaces.distinct()
        
        # Аннотации для сортировки
        spaces = spaces.annotate(
            min_price_value=Min('prices__price'),
            avg_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews', filter=Q(reviews__is_approved=True))
        )
        
        # Сортировка
        sort_mapping = {
            'price_asc': 'min_price_value',
            'price_desc': '-min_price_value',
            'area_asc': 'area_sqm',
            'area_desc': '-area_sqm',
            'newest': '-created_at',
            'popular': '-views_count',
            'rating': '-avg_rating',
        }
        order = sort_mapping.get(sort_by, '-created_at')
        spaces = spaces.order_by(order)
        
        # Пагинация
        paginator = Paginator(spaces, per_page)
        page_obj = paginator.get_page(page)
        
        return page_obj, paginator.count

    @staticmethod
    def get_featured_spaces(limit: int = 6):
        """Получить рекомендуемые помещения"""
        spaces = Space.objects.filter(
            is_active=True,
            is_featured=True
        ).select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        )[:limit]
        
        # Если мало рекомендуемых, добавляем популярные
        if spaces.count() < limit:
            spaces = Space.objects.filter(
                is_active=True
            ).select_related(
                'city', 'category'
            ).prefetch_related(
                'images', 'prices'
            ).order_by('-views_count')[:limit]
        
        return spaces

    @staticmethod
    def get_related_spaces(space: Space, limit: int = 4):
        """Получить похожие помещения"""
        return Space.objects.filter(
            is_active=True
        ).filter(
            Q(category=space.category) | Q(city=space.city)
        ).exclude(
            pk=space.pk
        ).select_related(
            'city', 'category'
        ).prefetch_related(
            'images', 'prices'
        ).annotate(
            min_price_value=Min('prices__price')
        ).order_by('?')[:limit]

    @staticmethod
    def increment_views(space_id: int):
        """Увеличить счётчик просмотров"""
        Space.objects.filter(pk=space_id).update(
            views_count=models.F('views_count') + 1
        )

    @staticmethod
    def get_space_stats(space: Space) -> dict:
        """Получить статистику помещения"""
        reviews = space.reviews.filter(is_approved=True)
        stats = reviews.aggregate(
            avg_rating=Avg('rating'),
            total_reviews=Count('id')
        )
        
        # Распределение рейтингов
        rating_distribution = {}
        for i in range(1, 6):
            rating_distribution[i] = reviews.filter(rating=i).count()
        
        return {
            'avg_rating': round(stats['avg_rating'] or 0, 1),
            'total_reviews': stats['total_reviews'] or 0,
            'rating_distribution': rating_distribution,
            'views_count': space.views_count,
            'bookings_count': space.bookings.count(),
        }

    @staticmethod
    def toggle_favorite(user, space_id: int) -> bool:
        """
        Добавить/удалить из избранного
        
        Returns:
            bool: True если добавлено, False если удалено
        """
        favorite, created = Favorite.objects.get_or_create(
            user=user,
            space_id=space_id
        )
        
        if not created:
            favorite.delete()
            return False
        
        return True

    @staticmethod
    def is_favorite(user, space_id: int) -> bool:
        """Проверить, в избранном ли помещение"""
        if not user.is_authenticated:
            return False
        return Favorite.objects.filter(user=user, space_id=space_id).exists()

    @staticmethod
    def get_user_favorites(user):
        """Получить избранные помещения пользователя"""
        return Favorite.objects.filter(
            user=user
        ).select_related(
            'space', 'space__city', 'space__category'
        ).prefetch_related(
            'space__images', 'space__prices'
        ).order_by('-created_at')
