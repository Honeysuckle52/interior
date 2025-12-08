"""
ПРЕДСТАВЛЕНИЯ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ (Модератор)

Управление пользователями: просмотр, блокировка, разблокировка.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from ..models import CustomUser, Booking, Review, Favorite

USERS_PER_PAGE: int = 20

logger = logging.getLogger(__name__)


def moderator_required(view_func):
    """Декоратор для проверки прав модератора."""
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Необходимо войти в систему')
            return redirect('login')
        if not request.user.can_moderate:
            messages.error(request, 'У вас нет прав для доступа к этой странице')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_users_queryset(request: HttpRequest):
    """Общая логика получения и фильтрации пользователей."""
    # Получаем всех пользователей кроме суперпользователей
    users = CustomUser.objects.filter(
        is_superuser=False
    ).annotate(
        bookings_count=Count('bookings'),
        reviews_count=Count('reviews'),
        total_spent=Sum('bookings__total_amount', filter=Q(bookings__status__code__in=['confirmed', 'completed']))
    ).order_by('-created_at')

    # Фильтрация по типу
    user_type_filter = request.GET.get('type', '')
    if user_type_filter:
        users = users.filter(user_type=user_type_filter)

    # Фильтрация по статусу
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True, is_blocked=False)
    elif status_filter == 'blocked':
        users = users.filter(is_blocked=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    # Поиск
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
    Страница управления пользователями для модераторов.
    """
    try:
        users, user_type_filter, status_filter, search_query = _get_users_queryset(request)

        # Статистика
        stats = {
            'total': CustomUser.objects.filter(is_superuser=False).count(),
            'users': CustomUser.objects.filter(user_type='user', is_superuser=False).count(),
            'moderators': CustomUser.objects.filter(user_type='moderator').count(),
            'blocked': CustomUser.objects.filter(is_blocked=True).count(),
            'verified': CustomUser.objects.filter(email_verified=True, is_superuser=False).count(),
        }

        # Пагинация
        paginator = Paginator(users, USERS_PER_PAGE)
        page_number = request.GET.get('page', 1)

        try:
            users_page: Page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            users_page = paginator.get_page(1)

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
    Возвращает HTML таблицы и обновленную статистику.
    """
    try:
        users, user_type_filter, status_filter, search_query = _get_users_queryset(request)

        # Статистика
        stats = {
            'total': CustomUser.objects.filter(is_superuser=False).count(),
            'users': CustomUser.objects.filter(user_type='user', is_superuser=False).count(),
            'moderators': CustomUser.objects.filter(user_type='moderator').count(),
            'blocked': CustomUser.objects.filter(is_blocked=True).count(),
            'verified': CustomUser.objects.filter(email_verified=True, is_superuser=False).count(),
        }

        # Пагинация
        paginator = Paginator(users, USERS_PER_PAGE)
        page_number = request.GET.get('page', 1)

        try:
            users_page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            users_page = paginator.get_page(1)

        # Рендерим только таблицу
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

    Args:
        request: HTTP request
        pk: User primary key

    Returns:
        Rendered user detail template
    """
    try:
        user = get_object_or_404(
            CustomUser.objects.select_related('profile'),
            pk=pk
        )

        # Нельзя просматривать суперпользователей
        if user.is_superuser and not request.user.is_superuser:
            messages.error(request, 'Нет доступа к этому пользователю')
            return redirect('manage_users')

        # Статистика пользователя
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

        # Последние бронирования
        recent_bookings = Booking.objects.filter(
            tenant=user
        ).select_related(
            'space', 'space__city', 'status', 'period'
        ).order_by('-created_at')[:10]

        # Последние отзывы
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
@require_POST
def block_user(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Блокировка пользователя.

    Args:
        request: HTTP request
        pk: User primary key

    Returns:
        Redirect to user detail or users list
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        # Нельзя блокировать модераторов и администраторов
        if user.can_moderate:
            messages.error(request, 'Нельзя заблокировать модератора или администратора')
            return redirect('user_detail_mod', pk=pk)

        # Нельзя блокировать суперпользователей
        if user.is_superuser:
            messages.error(request, 'Нельзя заблокировать суперпользователя')
            return redirect('user_detail_mod', pk=pk)

        user.is_blocked = True
        user.save()

        messages.success(request, f'Пользователь {user.username} заблокирован')
        logger.info(f"User {user.username} blocked by {request.user.username}")

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

    Args:
        request: HTTP request
        pk: User primary key

    Returns:
        Redirect to user detail or users list
    """
    try:
        user = get_object_or_404(CustomUser, pk=pk)

        user.is_blocked = False
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

    Args:
        request: HTTP request
        pk: User primary key

    Returns:
        Redirect to user detail
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
