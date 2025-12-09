"""
====================================================================
СЕРВИС ПОМЕЩЕНИЙ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит бизнес-логику для работы с помещениями,
включая фильтрацию, поиск, управление избранным и получение статистики.

Основный класс:
- SpaceService: Сервисный класс со статическими методами для работы с помещениями

Функционал:
- Фильтрация помещений по множеству параметров (город, категория, площадь, цена и т.д.)
- Пагинация и сортировка результатов поиска
- Получение рекомендуемых и похожих помещений
- Управление избранными помещениями пользователей
- Сбор статистики по помещениям (рейтинги, просмотры, бронирования)
- Увеличение счетчиков просмотров
====================================================================
"""

from django.db.models import Q, Avg, Count, Min
from django.core.paginator import Paginator

from ..models import Space, City, SpaceCategory, Favorite, Review


class SpaceService:
    """
    Сервис для работы с помещениями.

    Содержит статические методы для выполнения операций с помещениями,
    таких как фильтрация, поиск, управление избранным и сбор статистики.
    """

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
        Получить отфильтрованный список помещений с пагинацией.

        Выполняет сложную фильтрацию по всем доступным параметрам,
        добавляет аннотации для сортировки и возвращает пагинированный результат.

        Args:
            search (str): Текст для поиска по названию, описанию, адресу, городу
            city_id (int): ID города для фильтрации
            category_id (int): ID категории помещения для фильтрации
            min_area (float): Минимальная площадь помещения (м²)
            max_area (float): Максимальная площадь помещения (м²)
            min_price (float): Минимальная цена аренды
            max_price (float): Максимальная цена аренды
            min_capacity (int): Минимальная вместимость (человек)
            sort_by (str): Тип сортировки:
                - 'newest': Сначала новые
                - 'price_asc': Цена по возрастанию
                - 'price_desc': Цена по убыванию
                - 'area_asc': Площадь по возрастанию
                - 'area_desc': Площадь по убыванию
                - 'popular': По популярности (просмотры)
                - 'rating': По рейтингу
            page (int): Номер страницы для пагинации (начиная с 1)
            per_page (int): Количество элементов на странице

        Returns:
            tuple: Кортеж из двух элементов:
                - page_obj: Page объект Django Paginator
                - total_count: Общее количество найденных помещений
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
        """
        Получить рекомендуемые помещения.

        Возвращает помещения, отмеченные как рекомендуемые (is_featured=True).
        Если рекомендуемых помещений недостаточно, дополняет список
        популярными помещениями (по количеству просмотров).

        Args:
            limit (int): Максимальное количество возвращаемых помещений

        Returns:
            QuerySet[Space]: Набор рекомендуемых помещений
        """
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
        """
        Получить похожие помещения.

        Находит помещения той же категории или того же города,
        что и указанное помещение, исключая само помещение.

        Args:
            space (Space): Помещение, для которого ищем похожие
            limit (int): Максимальное количество возвращаемых помещений

        Returns:
            QuerySet[Space]: Набор похожих помещений
        """
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
        """
        Увеличить счетчик просмотров помещения.

        Args:
            space_id (int): ID помещения, счетчик просмотров которого нужно увеличить
        """
        Space.objects.filter(pk=space_id).update(
            views_count=models.F('views_count') + 1
        )

    @staticmethod
    def get_space_stats(space: Space) -> dict:
        """
        Получить статистику помещения.

        Собирает полную статистику по помещению, включая:
        - Средний рейтинг
        - Количество отзывов
        - Распределение рейтингов (сколько 1, 2, 3, 4, 5 звезд)
        - Количество просмотров
        - Количество бронирований

        Args:
            space (Space): Помещение, для которого собирается статистика

        Returns:
            dict: Словарь со статистикой:
                - avg_rating: Средний рейтинг (округленный до 1 знака)
                - total_reviews: Общее количество одобренных отзывов
                - rating_distribution: Распределение рейтингов (словарь)
                - views_count: Количество просмотров
                - bookings_count: Количество бронирований
        """
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
        Добавить/удалить помещение из избранного.

        Если помещение уже в избранном - удаляет его.
        Если нет в избранном - добавляет.

        Args:
            user: Пользователь, совершающий действие
            space_id (int): ID помещения для добавления/удаления из избранного

        Returns:
            bool: True если помещение было добавлено в избранное,
                 False если было удалено из избранного
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
        """
        Проверить, находится ли помещение в избранном у пользователя.

        Args:
            user: Пользователь для проверки
            space_id (int): ID помещения для проверки

        Returns:
            bool: True если помещение в избранном, False в противном случае
                  (также возвращает False для неавторизованных пользователей)
        """
        if not user.is_authenticated:
            return False
        return Favorite.objects.filter(user=user, space_id=space_id).exists()

    @staticmethod
    def get_user_favorites(user):
        """
        Получить избранные помещения пользователя.

        Args:
            user: Пользователь, чьи избранные помещения запрашиваются

        Returns:
            QuerySet[Favorite]: Набор избранных помещений пользователя,
                               отсортированный по дате добавления (новые сначала)
        """
        return Favorite.objects.filter(
            user=user
        ).select_related(
            'space', 'space__city', 'space__category'
        ).prefetch_related(
            'space__images', 'space__prices'
        ).order_by('-created_at')