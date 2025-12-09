"""
====================================================================
СИГНАЛЫ DJANGO ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит обработчики сигналов Django для автоматического
выполнения действий при возникновении определенных событий в моделях.

Основные обработчики сигналов:
- create_user_profile: Создание профиля при регистрации пользователя
- update_space_rating_on_review: Обновление рейтинга при сохранении отзыва
- update_space_rating_on_review_delete: Обновление рейтинга при удалении отзыва

Вспомогательные функции:
- update_space_rating: Пересчет среднего рейтинга помещения

Функционал:
1. Автоматическое создание UserProfile для новых пользователей
2. Автоматическое обновление кэшированного рейтинга помещений
   при добавлении, изменении или удалении отзывов
3. Подсчет общего количества отзывов для каждого помещения

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
    Автоматическое создание профиля при регистрации пользователя.

    Обработчик сигнала post_save для модели CustomUser, который
    создает связанную модель UserProfile при создании нового пользователя.

    Args:
        sender (Type[CustomUser]): Класс модели-отправителя
        instance (CustomUser): Сохраненный экземпляр пользователя
        created (bool): Флаг создания нового объекта
        **kwargs: Дополнительные аргументы сигнала

    Returns:
        None
    """
    if created:
        UserProfile.objects.get_or_create(user=instance)
        logger.info(f"Создан профиль для пользователя: {instance.username}")


def update_space_rating(space: Space) -> None:
    """
    Пересчитывает и обновляет средний рейтинг помещения.

    Вычисляет средний рейтинг по всем одобренным отзывам и обновляет
    кэшированные поля в модели Space (если они существуют).

    Args:
        space (Space): Объект помещения для обновления рейтинга

    Returns:
        None

    Note:
        Использует безопасную проверку hasattr для работы с опциональными полями
    """
    # Агрегируем данные по одобренным отзывам
    result = Review.objects.filter(
        space=space,
        is_approved=True
    ).aggregate(
        avg_rating=Avg('rating'),
        total_reviews=Count('id')
    )

    avg_rating = result['avg_rating']

    # Обновляем кэшированный рейтинг если есть такое поле
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

    Обработчик сигнала post_save для модели Review. Вызывается
    после сохранения отзыва (создания или обновления).

    Args:
        sender (Type[Review]): Класс модели-отправителя
        instance (Review): Сохраненный экземпляр отзыва
        **kwargs: Дополнительные аргументы сигнала

    Returns:
        None
    """
    # Обновляем рейтинг только если отзыв одобрен и привязан к помещению
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

    Обработчик сигнала post_delete для модели Review. Вызывается
    после удаления отзыва.

    Args:
        sender (Type[Review]): Класс модели-отправителя
        instance (Review): Удаленный экземпляр отзыва
        **kwargs: Дополнительные аргументы сигнала

    Returns:
        None
    """
    # Обновляем рейтинг даже если отзыв был удален
    if instance.space:
        update_space_rating(instance.space)