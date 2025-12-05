"""
ПРЕДСТАВЛЕНИЯ ДЛЯ РАБОТЫ С ИЗБРАННЫМ

Handles adding/removing spaces from favorites.
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
    Toggle space in user's favorites (AJAX).

    Args:
        request: HTTP request
        pk: Space primary key

    Returns:
        JSON response with operation status
    """
    try:
        space = get_object_or_404(Space, pk=pk, is_active=True)

        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            space=space
        )

        if not created:
            favorite.delete()
            return JsonResponse({
                'status': 'removed',
                'message': 'Удалено из избранного',
                'favorites_count': Favorite.objects.filter(user=request.user).count()
            })

        return JsonResponse({
            'status': 'added',
            'message': 'Добавлено в избранное',
            'favorites_count': Favorite.objects.filter(user=request.user).count()
        })

    except Http404:
        return JsonResponse({
            'status': 'error',
            'message': 'Помещение не найдено'
        }, status=404)
    except DatabaseError as e:
        logger.error(f"Database error in toggle_favorite: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Ошибка базы данных'
        }, status=500)
    except Exception as e:
        logger.error(f"Error in toggle_favorite view for pk={pk}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Произошла ошибка'
        }, status=500)


@login_required
def check_favorite(request: HttpRequest, pk: int) -> JsonResponse:
    """
    Check if space is in user's favorites (AJAX).

    Args:
        request: HTTP request
        pk: Space primary key

    Returns:
        JSON response with favorite status
    """
    try:
        is_favorite = Favorite.objects.filter(
            user=request.user,
            space_id=pk
        ).exists()

        return JsonResponse({'is_favorite': is_favorite})

    except Exception as e:
        logger.error(f"Error in check_favorite view for pk={pk}: {e}", exc_info=True)
        return JsonResponse({
            'is_favorite': False,
            'error': 'Произошла ошибка'
        }, status=500)
