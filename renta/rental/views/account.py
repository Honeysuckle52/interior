"""
====================================================================
ПРЕДСТАВЛЕНИЯ ЛИЧНОГО КАБИНЕТА ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для функционала личного кабинета,
включая дашборд, управление профилем, просмотр бронирований и избранного,
а также просмотр профилей пользователей для администраторов.

Основные представления:
- dashboard: Главная страница личного кабинета со статистикой
- profile: Редактирование профиля пользователя
- my_bookings: Список бронирований пользователя с фильтрацией
- my_favorites: Список избранных помещений пользователя
- view_user_profile: Просмотр профиля другого пользователя (админ)

Константы:
- RECENT_BOOKINGS_LIMIT: Количество последних бронирований на дашборде
- RECENT_FAVORITES_LIMIT: Количество последних избранных на дашборде
- BOOKINGS_PER_PAGE: Количество бронирований на странице
- FAVORITES_PER_PAGE: Количество избранных на странице
- USER_RECENT_BOOKINGS_LIMIT: Количество бронирований в профиле пользователя

Особенности:
- Защита представлений декоратором @login_required
- Обработка ошибок с логированием и пользовательскими сообщениями
- Оптимизированные запросы к БД с использованием select_related и prefetch_related
- Пагинация для списков бронирований и избранного
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

from ..forms import UserProfileForm, UserProfileExtendedForm
from ..models import Booking, Favorite, Review, UserProfile, CustomUser

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
    Отображение главной страницы личного кабинета пользователя.

    Показывает последние бронирования, избранные помещения
    и сводную статистику пользователя.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрендеренный шаблон дашборда

    Template:
        account/dashboard.html

    Context:
        - recent_bookings: Последние бронирования пользователя
        - recent_favorites: Последние избранные помещения
        - stats: Статистика пользователя (общие бронирования, активные и т.д.)
        - error: Сообщение об ошибке (при наличии)
    """
    try:
        user = request.user

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
        }
        return render(request, 'account/dashboard.html', context)

    except Exception as e:
        logger.error(f"Error in dashboard view: {e}", exc_info=True)
        return render(request, 'account/dashboard.html', {
            'recent_bookings': [],
            'recent_favorites': [],
            'stats': {
                'bookings_total': 0,
                'bookings_active': 0,
                'favorites_count': 0,
                'reviews_count': 0,
                'total_spent': 0,
            },
            'error': 'Ошибка при загрузке данных'
        })


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """
    Отображение и обработка формы редактирования профиля пользователя.

    Позволяет пользователю изменять свои личные данные,
    контактную информацию, аватар и настройки профиля.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрендеренный шаблон профиля или редирект

    Template:
        account/profile.html

    Context:
        - user_form: Форма с основными данными пользователя
        - profile_form: Форма с дополнительными данными профиля
    """
    try:
        user = request.user

        # Get or create profile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)

        if request.method == 'POST':
            user_form = UserProfileForm(
                request.POST,
                request.FILES,
                instance=user
            )
            profile_form = UserProfileExtendedForm(
                request.POST,
                instance=user_profile
            )

            if user_form.is_valid() and profile_form.is_valid():
                try:
                    saved_user = user_form.save(commit=False)

                    # Проверяем, был ли загружен новый файл аватара
                    if 'avatar' in request.FILES:
                        saved_user.avatar = request.FILES['avatar']

                    saved_user.save()
                    profile_form.save()

                    messages.success(request, 'Профиль успешно обновлен!')
                    return redirect('profile')
                except DatabaseError as e:
                    logger.error(f"Database error saving profile: {e}", exc_info=True)
                    messages.error(request, 'Ошибка при сохранении профиля')
            else:
                messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
        else:
            user_form = UserProfileForm(instance=user)
            profile_form = UserProfileExtendedForm(instance=user_profile)

        context: dict[str, Any] = {
            'user_form': user_form,
            'profile_form': profile_form,
        }
        return render(request, 'account/profile.html', context)

    except Exception as e:
        logger.error(f"Error in profile view: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке профиля')
        return redirect('dashboard')


@login_required
def my_bookings(request: HttpRequest) -> HttpResponse:
    """
    Отображение списка всех бронирований пользователя.

    Поддерживает фильтрацию по статусу бронирования
    и отображает статистику по каждому статусу.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрендеренный шаблон списка бронирований

    Template:
        account/bookings.html

    Context:
        - bookings: Пагинированный список бронирований
        - status_filter: Текущий фильтр статуса
        - status_stats: Статистика бронирований по статусам
        - error: Сообщение об ошибке (при наличии)
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

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрендеренный шаблон списка избранного

    Template:
        account/favorites.html

    Context:
        - favorites: Пагинированный список избранных помещений
        - error: Сообщение об ошибке (при наличии)
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

    Используется администраторами при проверке бронирований
    для просмотра информации о клиенте.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID пользователя, чей профиль нужно посмотреть

    Returns:
        HttpResponse: Отрендеренный шаблон профиля пользователя или редирект

    Template:
        account/user_profile.html

    Context:
        - profile_user: Пользователь, чей профиль просматривается
        - user_stats: Статистика пользователя (бронирования, расходы)
        - recent_bookings: Последние бронирования пользователя
    """
    try:
        current_user = request.user

        # Check if user has permission to view profiles
        if not current_user.can_moderate:
            messages.error(request, 'У вас нет прав для просмотра профилей пользователей')
            return redirect('dashboard')

        # Get the user to view
        profile_user: CustomUser = get_object_or_404(
            CustomUser.objects.select_related('profile'),
            pk=pk
        )

        # Get user statistics
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

        # Get recent bookings for this user
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