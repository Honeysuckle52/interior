"""
СИГНАЛЫ DJANGO
Автоматические действия при событиях в моделях
"""
from __future__ import annotations

from typing import Any, Type
import logging

from django.db.models.signals import post_save, post_delete
from django.db.models import Avg, Count
from django.dispatch import receiver

from .models import CustomUser, UserProfile, Review, Space

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_user_profile(
    sender: Type[CustomUser],
    instance: CustomUser,
    created: bool,
    **kwargs: Any
) -> None:
    """
    Автоматическое создание профиля при регистрации пользователя
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
        logger.info(f"Создан профиль для пользователя: {instance.username}")


def update_space_rating(space: Space) -> None:
    """
    Пересчитывает и обновляет средний рейтинг помещения
    """
    result = Review.objects.filter(
        space=space,
        is_approved=True
    ).aggregate(
        avg_rating=Avg('rating'),
        total_reviews=Count('id')
    )

    avg_rating = result['avg_rating']
    # Обновляем кешированный рейтинг если есть такое поле
    if hasattr(space, 'cached_rating'):
        space.cached_rating = avg_rating or 0
        space.reviews_count = result['total_reviews'] or 0
        space.save(update_fields=['cached_rating', 'reviews_count'])
        logger.debug(f"Обновлён рейтинг помещения {space.id}: {avg_rating}")


@receiver(post_save, sender=Review)
def update_space_rating_on_review(
    sender: Type[Review],
    instance: Review,
    **kwargs: Any
) -> None:
    """
    Обновление среднего рейтинга помещения при добавлении/изменении отзыва
    """
    if instance.space and instance.is_approved:
        update_space_rating(instance.space)


@receiver(post_delete, sender=Review)
def update_space_rating_on_review_delete(
    sender: Type[Review],
    instance: Review,
    **kwargs: Any
) -> None:
    """
    Обновление рейтинга при удалении отзыва
    """
    if instance.space:
        update_space_rating(instance.space)
