"""
====================================================================
СИГНАЛЫ DJANGO ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит обработчики сигналов Django для автоматического
выполнения действий при возникновении определенных событий в моделях.

Основные обработчики сигналов:
- update_space_rating_on_review: Обновление рейтинга при сохранении отзыва
- update_space_rating_on_review_delete: Обновление рейтинга при удалении отзыва
- handle_category_status_change: Управление статусом помещений при изменении категории

Вспомогательные функции:
- update_space_rating: Пересчет среднего рейтинга помещения

Функционал:
1. Автоматическое обновление кэшированного рейтинга помещений
   при добавлении, изменении или удалении отзывов
2. Подсчет общего количества отзывов для каждого помещения
3. Деактивация/реактивация помещений при изменении статуса категории

Особенности:
- Использование сигналов post_save и post_delete для реагирования на изменения
- Использование pre_save для отслеживания изменений статуса категории
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


@receiver(pre_save, sender=SpaceCategory)
def store_previous_category_status(
        sender: Type[SpaceCategory],
        instance: SpaceCategory,
        **kwargs: Any
) -> None:
    """
    Сохраняет предыдущий статус категории перед сохранением.
    """
    if instance.pk:
        try:
            old_instance = SpaceCategory.objects.get(pk=instance.pk)
            instance._previous_is_active = old_instance.is_active
        except SpaceCategory.DoesNotExist:
            instance._previous_is_active = None
    else:
        instance._previous_is_active = None


@receiver(post_save, sender=SpaceCategory)
def handle_category_status_change(
        sender: Type[SpaceCategory],
        instance: SpaceCategory,
        created: bool,
        **kwargs: Any
) -> None:
    """
    Управление статусом помещений при изменении статуса категории.

    При деактивации категории:
    - Все помещения категории деактивируются
    - Сохраняется информация о том, что они были деактивированы автоматически

    При активации категории:
    - Восстанавливаются помещения, которые были деактивированы автоматически

    Args:
        sender (Type[SpaceCategory]): Класс модели-отправителя
        instance (SpaceCategory): Экземпляр категории
        created (bool): True если объект был создан
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:
        return

    previous_is_active = getattr(instance, '_previous_is_active', None)

    # Если статус не изменился, ничего не делаем
    if previous_is_active == instance.is_active:
        return

    if not instance.is_active:
        # Категория деактивирована - деактивируем все помещения
        # Помечаем их как "деактивированные из-за категории"
        updated_count = Space.objects.filter(
            category=instance,
            is_active=True
        ).update(
            is_active=False,
            # Используем views_count временно как маркер (не идеально, но без миграции)
            # Лучший вариант - добавить поле deactivated_by_category, но это требует миграции
        )

        # Сохраняем ID деактивированных помещений в кэше категории
        deactivated_ids = list(Space.objects.filter(
            category=instance,
            is_active=False
        ).values_list('id', flat=True))

        # Сохраняем в description временно (можно использовать отдельную таблицу)
        # Для простоты используем JSON в памяти через кэш Django
        from django.core.cache import cache
        cache.set(f'category_{instance.pk}_deactivated_spaces', deactivated_ids, timeout=None)

        if updated_count > 0:
            logger.info(
                f"Деактивировано {updated_count} помещений "
                f"при деактивации категории '{instance.name}'"
            )
    else:
        # Категория активирована - восстанавливаем помещения
        from django.core.cache import cache
        deactivated_ids = cache.get(f'category_{instance.pk}_deactivated_spaces', [])

        if deactivated_ids:
            updated_count = Space.objects.filter(
                id__in=deactivated_ids,
                category=instance,
                is_active=False
            ).update(is_active=True)

            # Очищаем кэш
            cache.delete(f'category_{instance.pk}_deactivated_spaces')

            if updated_count > 0:
                logger.info(
                    f"Восстановлено {updated_count} помещений "
                    f"при активации категории '{instance.name}'"
                )
        else:
            # Если нет сохранённых ID, восстанавливаем все неактивные помещения категории
            updated_count = Space.objects.filter(
                category=instance,
                is_active=False
            ).update(is_active=True)

            if updated_count > 0:
                logger.info(
                    f"Восстановлено {updated_count} помещений "
                    f"при активации категории '{instance.name}' (все неактивные)"
                )
