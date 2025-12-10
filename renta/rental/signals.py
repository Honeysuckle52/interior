"""
====================================================================
СИГНАЛЫ DJANGO ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит обработчики сигналов Django для автоматического
выполнения действий при возникновении определенных событий в моделях.

Основные обработчики сигналов:
- update_space_rating_on_review: Обновление рейтинга при сохранении отзыва
- update_space_rating_on_review_delete: Обновление рейтинга при удалении отзыва
- deactivate_spaces_on_category_change: Деактивация помещений при деактивации категории

Вспомогательные функции:
- update_space_rating: Пересчет среднего рейтинга помещения

Функционал:
1. Автоматическое обновление кэшированного рейтинга помещений
   при добавлении, изменении или удалении отзывов
2. Подсчет общего количества отзывов для каждого помещения
3. Деактивация помещений при деактивации категории

Особенности:
- Использование сигналов post_save и post_delete для реагирования на изменения
- Логирование всех автоматических действий для отладки
- Проверка на наличие полей перед обновлением (безопасная работа с моделями)
- Оптимизация через кэширование рейтингов в модели Space
====================================================================
"""

from __future__ import annotations

from typing import Any, Type
import logging

from django.db.models.signals import post_save, post_delete, pre_save
from django.db.models import Avg, Count
from django.dispatch import receiver

from .models import CustomUser, Review, Space, SpaceCategory

logger = logging.getLogger(__name__)




def update_space_rating(space: Space) -> None:
    """
    Пересчитывает и обновляет средний рейтинг помещения.
    """
    result = Review.objects.filter(
        space=space,
        is_approved=True
    ).aggregate(
        avg_rating=Avg('rating'),
        total_reviews=Count('id')
    )

    avg_rating = result['avg_rating']

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
    Обновление среднего рейтинга помещения при добавлении/изменении отзыва.
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
    Обновление рейтинга при удалении отзыва.
    """
    if instance.space:
        update_space_rating(instance.space)


@receiver(post_save, sender=SpaceCategory)
def deactivate_spaces_on_category_change(
    sender: Type[SpaceCategory],
    instance: SpaceCategory,
    **kwargs: Any
) -> None:
    """
    Деактивация помещений при деактивации категории.

    Когда категория становится неактивной, все связанные с ней
    помещения также деактивируются.

    Args:
        sender (Type[SpaceCategory]): Класс модели-отправителя
        instance (SpaceCategory): Экземпляр категории
        **kwargs: Дополнительные аргументы сигнала
    """
    if not instance.is_active:
        # Деактивируем все помещения в этой категории
        updated_count = Space.objects.filter(
            category=instance,
            is_active=True
        ).update(is_active=False)

        if updated_count > 0:
            logger.info(
                f"Деактивировано {updated_count} помещений "
                f"при деактивации категории '{instance.name}'"
            )
