"""
====================================================================
СЕРВИС ПОЛЬЗОВАТЕЛЕЙ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит бизнес-логику для работы с пользователями,
включая управление профилями, сбор статистики и проверку прав доступа.

Основный класс:
- UserService: Сервисный класс со статическими методами для работы с пользователями

Функционал:
- Получение и создание профилей пользователей
- Сбор статистики для клиентов (бронирования, избранное, отзывы)
- Сбор статистики для владельцев помещений (доходы, просмотры, рейтинги)
- Обновление данных профиля пользователя
- Проверка возможности оставить отзыв для помещения
====================================================================
"""

from django.db.models import Sum, Count, Avg

from ..models import CustomUser, UserProfile, Booking, Review, Favorite


class UserService:
    """
    Сервис для работы с пользователями.

    Содержит статические методы для выполнения операций с пользователями,
    управления профилями и сбора статистики для разных типов пользователей.
    """

    @staticmethod
    def get_or_create_profile(user: CustomUser) -> UserProfile:
        """
        Получить или создать профиль пользователя.

        Гарантирует наличие профиля для пользователя,
        создавая его при необходимости.

        Args:
            user (CustomUser): Пользователь, для которого нужен профиль

        Returns:
            UserProfile: Профиль пользователя (существующий или созданный)
        """
        profile, created = UserProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_user_stats(user: CustomUser) -> dict:
        """
        Получить статистику пользователя (клиента).

        Собирает статистику по активностям пользователя как клиента:
        бронирования, избранные помещения, оставленные отзывы и общая сумма потраченных средств.

        Args:
            user (CustomUser): Пользователь, для которого собирается статистика

        Returns:
            dict: Словарь со статистикой пользователя:
                - bookings_total: Общее количество бронирований
                - bookings_active: Количество активных бронирований (ожидание + подтверждено)
                - bookings_completed: Количество завершенных бронирований
                - favorites_count: Количество избранных помещений
                - reviews_count: Количество оставленных отзывов
                - total_spent: Общая сумма потраченных средств (только подтвержденные и завершенные бронирования)
        """
        bookings = Booking.objects.filter(tenant=user)

        stats = {
            'bookings_total': bookings.count(),
            'bookings_active': bookings.filter(
                status__code__in=['pending', 'confirmed']
            ).count(),
            'bookings_completed': bookings.filter(
                status__code='completed'
            ).count(),
            'favorites_count': Favorite.objects.filter(user=user).count(),
            'reviews_count': Review.objects.filter(author=user).count(),
            'total_spent': bookings.filter(
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
        }

        return stats

    @staticmethod
    def get_owner_stats(user: CustomUser) -> dict:
        """
        Получить статистику владельца помещений.

        Собирает статистику для пользователей с типом 'owner':
        информация об их помещениях, доходах, просмотрах и рейтингах.

        Args:
            user (CustomUser): Пользователь-владелец, для которого собирается статистика

        Returns:
            dict: Словарь со статистикой владельца или пустой словарь,
                 если пользователь не является владельцем:
                - spaces_count: Общее количество помещений
                - spaces_active: Количество активных (видимых) помещений
                - total_views: Суммарное количество просмотров всех помещений
                - bookings_received: Общее количество полученных бронирований
                - revenue: Общий доход от подтвержденных и завершенных бронирований
                - avg_rating: Средний рейтинг всех помещений владельца
        """
        if user.user_type != 'owner':
            return {}

        spaces = user.owned_spaces.all()
        bookings = Booking.objects.filter(space__owner=user)

        stats = {
            'spaces_count': spaces.count(),
            'spaces_active': spaces.filter(is_active=True).count(),
            'total_views': sum(s.views_count for s in spaces),
            'bookings_received': bookings.count(),
            'revenue': bookings.filter(
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            'avg_rating': spaces.aggregate(
                avg=Avg('reviews__rating')
            )['avg'] or 0,
        }

        return stats

    @staticmethod
    def update_profile(user: CustomUser, user_data: dict, profile_data: dict = None) -> CustomUser:
        """
        Обновить профиль пользователя.

        Обновляет основные данные пользователя и, при необходимости,
        дополнительные данные профиля (UserProfile).

        Args:
            user (CustomUser): Пользователь, чей профиль обновляется
            user_data (dict): Словарь с данными для обновления полей CustomUser
            profile_data (dict, optional): Словарь с данными для обновления полей UserProfile

        Returns:
            CustomUser: Обновленный пользователь
        """
        # Обновляем основные данные
        for field, value in user_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        user.save()

        # Обновляем дополнительный профиль
        if profile_data:
            profile = UserService.get_or_create_profile(user)
            for field, value in profile_data.items():
                if hasattr(profile, field):
                    setattr(profile, field, value)
            profile.save()

        return user

    @staticmethod
    def can_leave_review(user: CustomUser, space_id: int) -> bool:
        """
        Проверить, может ли пользователь оставить отзыв для помещения.

        Проверяет следующие условия:
        1. Пользователь еще не оставлял отзыв для данного помещения
        2. [Опционально] Пользователь имел завершенное бронирование для данного помещения

        Args:
            user (CustomUser): Пользователь, проверяемый на возможность оставить отзыв
            space_id (int): ID помещения, для которого проверяется возможность отзыва

        Returns:
            bool: True если пользователь может оставить отзыв, False в противном случае

        Note:
            В текущей реализации проверка на наличие завершенного бронирования закомментирована,
            но может быть активирована при необходимости.
        """
        # Уже оставлял отзыв
        if Review.objects.filter(author=user, space_id=space_id).exists():
            return False

        # Проверяем, было ли завершённое бронирование (опционально)
        # has_booking = Booking.objects.filter(
        #     tenant=user,
        #     space_id=space_id,
        #     status__code='completed'
        # ).exists()

        return True