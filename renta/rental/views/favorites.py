"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ РАБОТЫ С ИЗБРАННЫМ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для управления функционалом
избранных помещений пользователей. Предоставляет AJAX endpoints для
добавления/удаления помещений из избранного и проверки статуса избранного.

Основные представления:
- toggle_favorite: AJAX endpoint для переключения статуса помещения в избранном
- check_favorite: AJAX endpoint для проверки, находится ли помещение в избранном

Особенности:
- Представления работают только через AJAX (используют @require_POST)
- Защита декораторами @login_required и @require_POST
- Оптимизированные запросы к базе данных
- Подробное логирование ошибок для отладки
- Дружественные JSON ответы для фронтенд интеграции
====================================================================
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Space, Favorite


logger = logging.getLogger(__name__)


@login_required
@require_POST
def toggle_favorite(request: HttpRequest, pk: int) -> JsonResponse:
    """
    AJAX endpoint для добавления/удаления помещения из избранного.

    Если помещение уже в избранном - удаляет его.
    Если помещение не в избранном - добавляет его.
    Возвращает актуальное количество избранных помещений пользователя.

    Args:
        request (HttpRequest): Объект HTTP запроса (должен быть POST)
        pk (int): ID помещения для добавления/удаления из избранного

    Returns:
        JsonResponse: JSON с результатом операции:
            - status: 'added' | 'removed' | 'error'
            - message: Человекочитаемое сообщение о результате
            - favorites_count: Актуальное количество избранных помещений пользователя

    HTTP Status Codes:
        - 200: Успешная операция
        - 404: Помещение не найдено или неактивно
        - 403: Пользователь не аутентифицирован
        - 405: Метод не POST
        - 500: Внутренняя ошибка сервера

    Примеры успешного ответа:
        Добавление: {'status': 'added', 'message': 'Добавлено в избранное', 'favorites_count': 5}
        Удаление: {'status': 'removed', 'message': 'Удалено из избранного', 'favorites_count': 4}
    """
    try:
        # Проверяем существование и активность помещения
        space = get_object_or_404(Space, pk=pk, is_active=True)

        # Используем get_or_create для атомарной операции
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            space=space
        )

        if not created:
            # Помещение уже было в избранном - удаляем
            favorite.delete()
            return JsonResponse({
                'status': 'removed',
                'message': 'Удалено из избранного',
                'favorites_count': Favorite.objects.filter(user=request.user).count()
            })

        # Помещение добавлено в избранное
        return JsonResponse({
            'status': 'added',
            'message': 'Добавлено в избранное',
            'favorites_count': Favorite.objects.filter(user=request.user).count()
        })

    except Http404:
        # Помещение не найдено или неактивно
        return JsonResponse({
            'status': 'error',
            'message': 'Помещение не найдено'
        }, status=404)
    except DatabaseError as e:
        # Ошибка базы данных
        logger.error(f"Database error in toggle_favorite: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Ошибка базы данных'
        }, status=500)
    except Exception as e:
        # Любая другая ошибка
        logger.error(f"Error in toggle_favorite view for pk={pk}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Произошла ошибка'
        }, status=500)


@login_required
def check_favorite(request: HttpRequest, pk: int) -> JsonResponse:
    """
    AJAX endpoint для проверки, находится ли помещение в избранном у пользователя.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID помещения для проверки

    Returns:
        JsonResponse: JSON с результатом проверки:
            - is_favorite (bool): Находится ли помещение в избранном
            - error (опционально): Сообщение об ошибке

    HTTP Status Codes:
        - 200: Успешная проверка
        - 500: Внутренняя ошибка сервера

    Примеры ответа:
        В избранном: {'is_favorite': true}
        Не в избранном: {'is_favorite': false}
        Ошибка: {'is_favorite': false, 'error': 'Произошла ошибка'}
    """
    try:
        # Проверяем существование записи в избранном
        is_favorite = Favorite.objects.filter(
            user=request.user,
            space_id=pk
        ).exists()

        return JsonResponse({'is_favorite': is_favorite})

    except Exception as e:
        # Логируем ошибку и возвращаем безопасный ответ
        logger.error(f"Error in check_favorite view for pk={pk}: {e}", exc_info=True)
        return JsonResponse({
            'is_favorite': False,
            'error': 'Произошла ошибка'
        }, status=500)