"""
СЕРВИС ПОЛЬЗОВАТЕЛЕЙ
Бизнес-логика для работы с пользователями
"""

from django.db.models import Sum, Avg

from ..models import CustomUser, UserProfile, Booking, Review, Favorite


class UserService:
    """Сервис пользователей"""

    @staticmethod
    def get_or_create_profile(user: CustomUser) -> UserProfile:
        """Получить или создать профиль"""
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def get_user_stats(user: CustomUser) -> dict:
        """Статистика пользователя (клиента)"""
        bookings = Booking.objects.filter(tenant=user)

        return {
            'bookings_total': bookings.count(),
            'bookings_active': bookings.filter(status__code__in=['pending', 'confirmed']).count(),
            'bookings_completed': bookings.filter(status__code='completed').count(),
            'favorites_count': Favorite.objects.filter(user=user).count(),
            'reviews_count': Review.objects.filter(author=user).count(),
            'total_spent': bookings.filter(
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
        }

    @staticmethod
    def get_owner_stats(user: CustomUser) -> dict:
        """Статистика владельца помещений"""
        if user.user_type != 'owner':
            return {}

        spaces = user.owned_spaces.all()
        bookings = Booking.objects.filter(space__owner=user)

        return {
            'spaces_count': spaces.count(),
            'spaces_active': spaces.filter(is_active=True).count(),
            'total_views': sum(s.views_count for s in spaces),
            'bookings_received': bookings.count(),
            'revenue': bookings.filter(
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            'avg_rating': spaces.aggregate(avg=Avg('reviews__rating'))['avg'] or 0,
        }

    @staticmethod
    def update_profile(user: CustomUser, user_data: dict, profile_data: dict = None) -> CustomUser:
        """Обновить профиль пользователя"""
        for field, value in user_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        user.save()

        if profile_data:
            profile = UserService.get_or_create_profile(user)
            for field, value in profile_data.items():
                if hasattr(profile, field):
                    setattr(profile, field, value)
            profile.save()

        return user

    @staticmethod
    def can_leave_review(user: CustomUser, space_id: int) -> bool:
        """Проверка возможности оставить отзыв"""
        return not Review.objects.filter(author=user, space_id=space_id).exists()
