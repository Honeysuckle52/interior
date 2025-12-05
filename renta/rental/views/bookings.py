"""
ПРЕДСТАВЛЕНИЯ ДЛЯ БРОНИРОВАНИЙ

Handles booking creation, viewing, and cancellation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import BookingForm
from ..models import (
    Space, SpacePrice, PricingPeriod, Booking, BookingStatus
)


logger = logging.getLogger(__name__)


def _get_available_periods(space: Space) -> Any:
    """Get available pricing periods for a space."""
    try:
        return PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()
    except Exception as e:
        logger.error(f"Error getting available periods: {e}", exc_info=True)
        return PricingPeriod.objects.none()


def _get_or_create_status(code: str, defaults: dict[str, Any]) -> BookingStatus:
    """Get or create a booking status."""
    try:
        status, _ = BookingStatus.objects.get_or_create(code=code, defaults=defaults)
        return status
    except Exception as e:
        logger.error(f"Error getting/creating status '{code}': {e}", exc_info=True)
        raise


@login_required
def create_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Create a new booking for a space.

    Args:
        request: HTTP request
        pk: Space primary key

    Returns:
        Rendered booking form or redirect on success
    """
    try:
        space = get_object_or_404(
            Space.objects.select_related('city', 'category', 'owner')
            .prefetch_related('images', 'prices', 'prices__period'),
            pk=pk,
            is_active=True
        )

        prices = space.prices.filter(is_active=True).select_related('period')
        available_periods = _get_available_periods(space)

        if request.method == 'POST':
            form = BookingForm(request.POST)
            form.fields['period'].queryset = available_periods

            if form.is_valid():
                try:
                    booking = form.save(commit=False)
                    booking.space = space
                    booking.tenant = request.user

                    # Get price for selected period
                    try:
                        price_obj = SpacePrice.objects.get(
                            space=space,
                            period=booking.period,
                            is_active=True
                        )
                        booking.price_per_period = price_obj.price
                    except SpacePrice.DoesNotExist:
                        messages.error(request, 'Выбранный период недоступен')
                        return redirect('space_detail', pk=pk)

                    # Calculate total amount
                    booking.total_amount = booking.price_per_period * booking.periods_count

                    # Set dates
                    start_date = form.cleaned_data['start_date']
                    start_time = form.cleaned_data['start_time']
                    booking.start_datetime = timezone.make_aware(
                        datetime.combine(start_date, start_time)
                    )

                    # Calculate end datetime
                    total_hours = booking.period.hours_count * booking.periods_count
                    booking.end_datetime = booking.start_datetime + timedelta(hours=total_hours)

                    # Validate start date is in future
                    if booking.start_datetime <= timezone.now():
                        messages.error(request, 'Дата начала должна быть в будущем')
                        return render(request, 'bookings/create.html', {
                            'space': space, 'prices': prices, 'form': form
                        })

                    # Set pending status
                    booking.status = _get_or_create_status('pending', {
                        'name': 'Ожидание',
                        'color': 'warning',
                        'sort_order': 1
                    })

                    booking.save()

                    messages.success(
                        request,
                        f'Бронирование #{booking.id} успешно создано! '
                        f'Сумма: {booking.total_amount} ₽'
                    )
                    return redirect('booking_detail', pk=booking.pk)

                except (DatabaseError, IntegrityError) as e:
                    logger.error(f"Database error creating booking: {e}", exc_info=True)
                    messages.error(request, 'Ошибка при создании бронирования. Попробуйте снова.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
        else:
            form = BookingForm()
            form.fields['period'].queryset = available_periods

        context = {
            'space': space,
            'prices': prices,
            'form': form,
        }
        return render(request, 'bookings/create.html', context)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in create_booking view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Произошла ошибка. Попробуйте позже.')
        return redirect('spaces_list')


@login_required
def booking_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Display booking details.

    Args:
        request: HTTP request
        pk: Booking primary key

    Returns:
        Rendered booking detail template
    """
    try:
        booking = get_object_or_404(
            Booking.objects.select_related(
                'space', 'space__city', 'space__category', 'space__owner',
                'status', 'period', 'tenant'
            ).prefetch_related('space__images', 'transactions'),
            pk=pk,
            tenant=request.user
        )

        context = {
            'booking': booking,
            'can_cancel': booking.is_cancellable,
            'can_review': (
                booking.status.code == 'completed' and
                not hasattr(booking, 'review')
            ),
        }
        return render(request, 'bookings/detail.html', context)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in booking_detail view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке бронирования')
        return redirect('my_bookings')


@login_required
@require_POST
def cancel_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Cancel a booking.

    Args:
        request: HTTP request
        pk: Booking primary key

    Returns:
        Redirect to bookings list or detail page
    """
    try:
        booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

        if not booking.is_cancellable:
            messages.error(request, 'Это бронирование нельзя отменить')
            return redirect('booking_detail', pk=pk)

        # Warning for late cancellation
        hours_until_start = (booking.start_datetime - timezone.now()).total_seconds() / 3600
        if hours_until_start < 24:
            messages.warning(
                request,
                'Отмена менее чем за 24 часа до начала аренды может быть платной'
            )

        # Update status
        booking.status = _get_or_create_status('cancelled', {
            'name': 'Отменено',
            'color': 'danger',
            'sort_order': 4
        })
        booking.save()

        messages.success(request, f'Бронирование #{booking.id} успешно отменено')
        return redirect('my_bookings')

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in cancel_booking view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при отмене бронирования')
        return redirect('my_bookings')


@login_required
def get_price_for_period(
    request: HttpRequest,
    space_id: int,
    period_id: int
) -> JsonResponse:
    """
    AJAX endpoint to get price for a specific period.

    Args:
        request: HTTP request
        space_id: Space primary key
        period_id: Period primary key

    Returns:
        JSON response with price information
    """
    try:
        price = SpacePrice.objects.select_related('period').get(
            space_id=space_id,
            period_id=period_id,
            is_active=True
        )
        return JsonResponse({
            'success': True,
            'price': float(price.price),
            'period_hours': price.period.hours_count,
            'period_name': price.period.description
        })
    except SpacePrice.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Цена не найдена'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_price_for_period: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка сервера'
        }, status=500)
