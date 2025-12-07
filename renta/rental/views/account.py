"""
ПРЕДСТАВЛЕНИЯ ЛИЧНОГО КАБИНЕТА

Handles user dashboard, profile, bookings, and favorites.
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
from django.shortcuts import render, redirect

from ..forms import UserProfileForm, UserProfileExtendedForm
from ..models import Booking, Favorite, Review, UserProfile

# Константы пагинации
RECENT_BOOKINGS_LIMIT: int = 5
RECENT_FAVORITES_LIMIT: int = 4
BOOKINGS_PER_PAGE: int = 10
FAVORITES_PER_PAGE: int = 12

logger = logging.getLogger(__name__)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Display user dashboard with recent activity.

    Args:
        request: HTTP request

    Returns:
        Rendered dashboard template
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
    Display and handle profile editing.

    Args:
        request: HTTP request

    Returns:
        Rendered profile template
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
                    user_form.save()
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
    Display all user bookings with filtering.

    Args:
        request: HTTP request

    Returns:
        Rendered bookings list template
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
    Display user's favorite spaces.

    Args:
        request: HTTP request

    Returns:
        Rendered favorites list template
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
