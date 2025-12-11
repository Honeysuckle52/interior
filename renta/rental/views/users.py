"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для управления пользователями,
доступные только модераторам и администраторам сайта. Включает просмотр
списка пользователей, детальной информации, блокировку/разблокировку
и ручное подтверждение email.

Основные представления:
- manage_users: Список пользователей с фильтрацией и пагинацией
- users_ajax: AJAX endpoint для динамической фильтрации пользователей
- user_detail: Детальная страница пользователя со статистикой
- block_user: Блокировка пользователя (POST)
- unblock_user: Разблокировка пользователя (POST)
- verify_user_email: Ручное подтверждение email пользователя (POST)
- edit_user: Редактирование пользователя (GET/POST)

Декораторы:
- moderator_required: Проверка прав модератора/администратора

Вспомогательные функции:
- _get_users_queryset: Общая логика получения и фильтрации пользователей

Константы:
- USERS_PER_PAGE: Количество пользователей на странице по умолчанию

Особенности:
- Защита от блокировки администраторов и суперпользователей
- Подробная статистика по пользователям (бронирования, отзывы, траты)
- AJAX фильтрация для обновления списка без перезагрузки страницы
- Логирование всех административных действий
====================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.utils import timezone

from ..models import CustomUser, Booking, Review, Favorite
from ..core.pagination import paginate
from ..core.decorators import moderator_required
from ..forms.users import UserEditForm


USERS_PER_PAGE: int = 20

logger = logging.getLogger(__name__)


def _get_users_queryset(request: HttpRequest):
    """
    Общая логика получения и фильтрации пользователей.
    """
    users = CustomUser.objects.filter(
        is_superuser=False
    ).annotate(
        bookings_count=Count('bookings'),
        reviews_count=Count('reviews'),
        total_spent=Sum('bookings__total_amount', filter=Q(bookings__status__code__in=['confirmed', 'completed']))
    ).order_by('-created_at')

    user_type_filter = request.GET.get('type', '')
    if user_type_filter:
        users = users.filter(user_type=user_type_filter)

    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True, is_blocked=False)
    elif status_filter == 'blocked':
        users = users.filter(is_blocked=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    search_query = request.GET.get('search', '').strip()
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(company__icontains=search_query)
        )

    return users, user_type_filter, status_filter, search_query


@login_required
@moderator_required
def manage_users(request: HttpRequest) -> HttpResponse:
    """
    Страница управления пользователями для модераторов и администраторов.
    """
    try:
        users, user_type_filter, status_filter, search_query = _get_users_queryset(request)

        stats = {
            'total': CustomUser.objects.filter(is_superuser=False).count(),
            'users': CustomUser.objects.filter(user_type='user', is_superuser=False).count(),
            'moderators': CustomUser.objects.filter(user_type='moderator').count(),
            'blocked': CustomUser.objects.filter(is_blocked=True).count(),
            'verified': CustomUser.objects.filter(email_verified=True, is_superuser=False).count(),
        }

        users_page, paginator = paginate(users, request, USERS_PER_PAGE)

        context: dict[str, Any] = {
            'users': users_page,
            'stats': stats,
            'user_type_filter': user_type_filter,
            'status_filter': status_filter,
            'search_query': search_query,
        }
        return render(request, 'users/manage.html', context)

    except Exception as e:
        logger.error(f"Error in manage_users view: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке списка пользователей')
        return redirect('dashboard')


@login_required
@moderator_required
def users_ajax(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint для живой фильтрации пользователей.
    """
    try:
        users, user_type_filter, status_filter, search_query = _get_users_queryset(request)

        stats = {
            'total': CustomUser.objects.filter(is_superuser=False).count(),
            'users': CustomUser.objects.filter(user_type='user', is_superuser=False).count(),
            'moderators': CustomUser.objects.filter(user_type='moderator').count(),
            'blocked': CustomUser.objects.filter(is_blocked=True).count(),
            'verified': CustomUser.objects.filter(email_verified=True, is_superuser=False).count(),
        }

        users_page, paginator = paginate(users, request, USERS_PER_PAGE)

        html = render_to_string('users/_users_table.html', {
            'users': users_page,
            'search_query': search_query,
            'user_type_filter': user_type_filter,
            'status_filter': status_filter,
        }, request=request)

        return JsonResponse({
            'success': True,
            'html': html,
            'stats': stats,
            'total_count': paginator.count,
        })

    except Exception as e:
        logger.error(f"Error in users_ajax: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@moderator_required
def user_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Детальная страница пользователя для модератора.
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        if user.is_superuser and not request.user.is_superuser:
            messages.error(request, 'Нет доступа к этому пользователю')
            return redirect('manage_users')

        user_stats = {
            'total_bookings': Booking.objects.filter(tenant=user).count(),
            'confirmed_bookings': Booking.objects.filter(
                tenant=user, status__code__in=['confirmed', 'completed']
            ).count(),
            'cancelled_bookings': Booking.objects.filter(
                tenant=user, status__code='cancelled'
            ).count(),
            'pending_bookings': Booking.objects.filter(
                tenant=user, status__code='pending'
            ).count(),
            'total_spent': Booking.objects.filter(
                tenant=user, status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
            'reviews_count': Review.objects.filter(author=user).count(),
            'favorites_count': Favorite.objects.filter(user=user).count(),
        }

        recent_bookings = Booking.objects.filter(
            tenant=user
        ).select_related(
            'space', 'space__city', 'status', 'period'
        ).order_by('-created_at')[:10]

        recent_reviews = Review.objects.filter(
            author=user
        ).select_related('space').order_by('-created_at')[:5]

        context: dict[str, Any] = {
            'profile_user': user,
            'user_stats': user_stats,
            'recent_bookings': recent_bookings,
            'recent_reviews': recent_reviews,
        }
        return render(request, 'users/detail.html', context)

    except Exception as e:
        logger.error(f"Error in user_detail view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке данных пользователя')
        return redirect('manage_users')


@login_required
@moderator_required
def edit_user(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование пользователя модератором/администратором.
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        # Суперпользователей могут редактировать только суперпользователи
        if user.is_superuser and not request.user.is_superuser:
            messages.error(request, 'Нет доступа к редактированию этого пользователя')
            return redirect('manage_users')

        # Модераторов могут редактировать только админы
        if user.user_type == 'moderator' and not request.user.is_superuser:
            messages.error(request, 'Только администратор может редактировать модератора')
            return redirect('user_detail_mod', pk=pk)

        if request.method == 'POST':
            form = UserEditForm(request.POST, instance=user, current_user=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, f'Данные пользователя {user.username} обновлены')
                logger.info(f"User {user.username} edited by {request.user.username}")
                return redirect('user_detail_mod', pk=pk)
        else:
            form = UserEditForm(instance=user, current_user=request.user)

        context: dict[str, Any] = {
            'form': form,
            'edit_user': user,
        }
        return render(request, 'users/edit.html', context)

    except Exception as e:
        logger.error(f"Error in edit_user view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при редактировании пользователя')
        return redirect('manage_users')


@login_required
@moderator_required
@require_POST
def block_user(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Блокировка пользователя с указанием причины.
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        if user.can_moderate:
            messages.error(request, 'Нельзя заблокировать модератора или администратора')
            return redirect('user_detail_mod', pk=pk)

        if user.is_superuser:
            messages.error(request, 'Нельзя заблокировать суперпользователя')
            return redirect('user_detail_mod', pk=pk)

        block_reason = request.POST.get('block_reason', '').strip()

        user.is_blocked = True
        user.block_reason = block_reason
        user.blocked_at = timezone.now()
        user.blocked_by = request.user
        user.save()

        messages.success(request, f'Пользователь {user.username} заблокирован')
        logger.info(f"User {user.username} blocked by {request.user.username}. Reason: {block_reason}")

        return redirect('user_detail_mod', pk=pk)

    except Exception as e:
        logger.error(f"Error in block_user view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при блокировке пользователя')
        return redirect('manage_users')


@login_required
@moderator_required
@require_POST
def unblock_user(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Разблокировка пользователя.
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        user.is_blocked = False
        user.block_reason = ''
        user.blocked_at = None
        user.blocked_by = None
        user.save()

        messages.success(request, f'Пользователь {user.username} разблокирован')
        logger.info(f"User {user.username} unblocked by {request.user.username}")

        return redirect('user_detail_mod', pk=pk)

    except Exception as e:
        logger.error(f"Error in unblock_user view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при разблокировке пользователя')
        return redirect('manage_users')


@login_required
@moderator_required
@require_POST
def verify_user_email(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Ручное подтверждение email пользователя модератором.
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        user.email_verified = True
        user.save()

        messages.success(request, f'Email пользователя {user.username} подтверждён')

        return redirect('user_detail_mod', pk=pk)

    except Exception as e:
        logger.error(f"Error in verify_user_email view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при подтверждении email')
        return redirect('manage_users')
