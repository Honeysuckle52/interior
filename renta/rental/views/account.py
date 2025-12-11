"""
====================================================================
ПРЕДСТАВЛЕНИЯ ЛИЧНОГО КАБИНЕТА ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db import DatabaseError
from django.db.models import Sum, Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from ..forms import UserProfileForm
from ..models import Booking, Favorite, Review, CustomUser

# Константы пагинации
RECENT_BOOKINGS_LIMIT: int = 5
RECENT_FAVORITES_LIMIT: int = 4
BOOKINGS_PER_PAGE: int = 10
FAVORITES_PER_PAGE: int = 12
USER_RECENT_BOOKINGS_LIMIT: int = 10

logger = logging.getLogger(__name__)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Объединённая страница личного кабинета и профиля.

    Включает:
    - Редактирование профиля
    - Статистику пользователя
    - Последние бронирования
    - Последние избранные
    - Быстрые действия
    """
    try:
        user = request.user

        # Handle profile form submission
        if request.method == 'POST':
            user_form = UserProfileForm(
                request.POST,
                request.FILES,
                instance=user
            )

            if user_form.is_valid():
                try:
                    saved_user = user_form.save(commit=False)
                    if 'avatar' in request.FILES:
                        saved_user.avatar = request.FILES['avatar']
                    saved_user.save()

                    messages.success(request, 'Профиль успешно обновлён!')
                    return redirect('dashboard')
                except DatabaseError as e:
                    logger.error(f"Database error saving profile: {e}", exc_info=True)
                    messages.error(request, 'Ошибка при сохранении профиля')
            else:
                error_messages = []
                for field, errors in user_form.errors.items():
                    field_name = user_form.fields.get(field).label if field in user_form.fields else field
                    for error in errors:
                        error_messages.append(f"{field_name}: {error}")

                if error_messages:
                    messages.error(request, 'Ошибки: ' + '; '.join(error_messages))
                else:
                    messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
        else:
            user_form = UserProfileForm(instance=user)

        # Recent bookings
        recent_bookings = Booking.objects.filter(
            tenant=user
        ).select_related(
            'space', 'space__city', 'status', 'period'
        ).prefetch_related(
            'space__images'
        ).order_by('-created_at')[:RECENT_BOOKINGS_LIMIT]

        # Recent favorites
        recent_favorites = Favorite.objects.filter(
            user=user
        ).select_related(
            'space', 'space__city', 'space__category'
        ).prefetch_related(
            'space__images', 'space__prices'
        ).order_by('-created_at')[:RECENT_FAVORITES_LIMIT]

        # User statistics
        stats: dict[str, Any] = {
            'bookings_total': Booking.objects.filter(tenant=user).count(),
            'bookings_active': Booking.objects.active().filter(tenant=user).count(),
            'favorites_count': Favorite.objects.filter(user=user).count(),
            'reviews_count': Review.objects.filter(author=user).count(),
            'total_spent': Booking.objects.filter(
                tenant=user,
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
        }

        context: dict[str, Any] = {
            'recent_bookings': recent_bookings,
            'recent_favorites': recent_favorites,
            'stats': stats,
            'user_form': user_form,
            'active_tab': request.GET.get('tab', 'overview'),
        }
        return render(request, 'account/dashboard.html', context)

    except Exception as e:
        logger.error(f"Error in dashboard view: {e}", exc_info=True)
        messages.error(request, 'Произошла ошибка при загрузке дашборда')
        return redirect('home')


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """
    Перенаправление со старой страницы профиля на dashboard с вкладкой профиля.
    """
    return redirect('dashboard')


@login_required
def my_bookings(request: HttpRequest) -> HttpResponse:
    """
    Отображение списка всех бронирований пользователя.
    """
    try:
        user = request.user

        bookings = Booking.objects.filter(
            tenant=user
        ).select_related(
            'space', 'space__city', 'space__category', 'status', 'period'
        ).prefetch_related(
            'space__images'
        ).order_by('-created_at')

        # Filter by status
        status_filter: str = request.GET.get('status', '')
        if status_filter:
            bookings = bookings.filter(status__code=status_filter)

        # Status statistics
        status_stats = Booking.objects.filter(tenant=user).values(
            'status__code', 'status__name', 'status__color'
        ).annotate(count=Count('id'))

        paginator = Paginator(bookings, BOOKINGS_PER_PAGE)
        page_number = request.GET.get('page', 1)

        try:
            bookings_page: Page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            bookings_page = paginator.get_page(1)

        context: dict[str, Any] = {
            'bookings': bookings_page,
            'status_filter': status_filter,
            'status_stats': status_stats,
        }
        return render(request, 'account/bookings.html', context)

    except Exception as e:
        logger.error(f"Error in my_bookings view: {e}", exc_info=True)
        return render(request, 'account/bookings.html', {
            'bookings': [],
            'status_filter': '',
            'status_stats': [],
            'error': 'Ошибка при загрузке бронирований'
        })


@login_required
def my_favorites(request: HttpRequest) -> HttpResponse:
    """
    Отображение списка избранных помещений пользователя.
    """
    try:
        favorites = Favorite.objects.filter(
            user=request.user
        ).select_related(
            'space', 'space__city', 'space__city__region', 'space__category'
        ).prefetch_related(
            'space__images', 'space__prices', 'space__prices__period'
        ).order_by('-created_at')

        paginator = Paginator(favorites, FAVORITES_PER_PAGE)
        page_number = request.GET.get('page', 1)

        try:
            favorites_page: Page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            favorites_page = paginator.get_page(1)

        return render(request, 'account/favorites.html', {'favorites': favorites_page})

    except Exception as e:
        logger.error(f"Error in my_favorites view: {e}", exc_info=True)
        return render(request, 'account/favorites.html', {
            'favorites': [],
            'error': 'Ошибка при загрузке избранного'
        })


@login_required
def view_user_profile(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Просмотр профиля другого пользователя (только для администраторов).
    """
    try:
        current_user = request.user

        if not current_user.can_moderate:
            messages.error(request, 'У вас нет прав для просмотра профилей пользователей')
            return redirect('dashboard')

        profile_user: CustomUser = get_object_or_404(
            CustomUser.objects.select_related('profile'),
            pk=pk
        )

        user_stats: dict[str, int] = {
            'total_bookings': Booking.objects.filter(tenant=profile_user).count(),
            'confirmed_bookings': Booking.objects.filter(
                tenant=profile_user,
                status__code__in=['confirmed', 'completed']
            ).count(),
            'cancelled_bookings': Booking.objects.filter(
                tenant=profile_user,
                status__code='cancelled'
            ).count(),
            'pending_bookings': Booking.objects.filter(
                tenant=profile_user,
                status__code='pending'
            ).count(),
            'total_spent': Booking.objects.filter(
                tenant=profile_user,
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
        }

        recent_bookings = Booking.objects.filter(
            tenant=profile_user
        ).select_related(
            'space', 'space__city', 'status', 'period'
        ).order_by('-created_at')[:USER_RECENT_BOOKINGS_LIMIT]

        context: dict[str, Any] = {
            'profile_user': profile_user,
            'user_stats': user_stats,
            'recent_bookings': recent_bookings,
        }
        return render(request, 'account/user_profile.html', context)

    except Exception as e:
        logger.error(f"Error in view_user_profile view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке профиля пользователя')
        return redirect('manage_bookings')


@login_required
def public_user_profile(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Публичный просмотр профиля пользователя (автора отзыва).
    Доступен всем авторизованным пользователям.
    Показывает ограниченную информацию без модераторских действий.
    """
    try:
        profile_user: CustomUser = get_object_or_404(
            CustomUser,
            pk=pk
        )

        # Статистика (только публичная)
        user_stats: dict[str, int] = {
            'reviews_count': Review.objects.filter(author=profile_user, is_approved=True).count(),
        }

        # Последние одобренные отзывы пользователя
        recent_reviews = Review.objects.filter(
            author=profile_user,
            is_approved=True
        ).select_related(
            'space', 'space__city'
        ).order_by('-created_at')[:5]

        context: dict[str, Any] = {
            'profile_user': profile_user,
            'user_stats': user_stats,
            'recent_reviews': recent_reviews,
        }
        return render(request, 'account/public_profile.html', context)

    except Exception as e:
        logger.error(f"Error in public_user_profile view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке профиля пользователя')
        return redirect('home')
