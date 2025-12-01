"""
СИГНАЛЫ DJANGO
Автоматические действия при событиях в моделях
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import CustomUser, UserProfile, Review, Space


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Автоматическое создание профиля при регистрации пользователя
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Review)
def update_space_rating_on_review(sender, instance, **kwargs):
    """
    Обновление среднего рейтинга помещения при добавлении/изменении отзыва
    (можно добавить кеширование рейтинга в модель Space)
    """
    # Пока просто логируем, можно добавить кеширование
    pass


@receiver(post_delete, sender=Review)
def update_space_rating_on_review_delete(sender, instance, **kwargs):
    """
    Обновление рейтинга при удалении отзыва
    """
    pass
