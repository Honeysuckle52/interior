"""
ПРЕДСТАВЛЕНИЯ ДЛЯ РАБОТЫ С ИЗБРАННЫМ
"""

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from ..models import Space, Favorite


@login_required
@require_POST
def toggle_favorite(request, pk):
    """
    Добавить/удалить помещение из избранного (AJAX)
    
    Returns:
        JsonResponse с статусом операции
    """
    space = get_object_or_404(Space, pk=pk, is_active=True)
    
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        space=space
    )
    
    if not created:
        # Уже в избранном - удаляем
        favorite.delete()
        return JsonResponse({
            'status': 'removed',
            'message': 'Удалено из избранного',
            'favorites_count': Favorite.objects.filter(user=request.user).count()
        })
    
    # Добавлено в избранное
    return JsonResponse({
        'status': 'added',
        'message': 'Добавлено в избранное',
        'favorites_count': Favorite.objects.filter(user=request.user).count()
    })


@login_required
def check_favorite(request, pk):
    """
    Проверить, в избранном ли помещение (AJAX)
    """
    is_favorite = Favorite.objects.filter(
        user=request.user, 
        space_id=pk
    ).exists()
    
    return JsonResponse({
        'is_favorite': is_favorite
    })
