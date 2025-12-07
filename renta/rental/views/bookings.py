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
from ..models import Space, SpacePrice, PricingPeriod, Booking
from ..services.status_service import StatusService

logger = logging.getLogger(__name__)


def _get_available_periods(space: Space) -> Any:
    """Получить доступные периоды для помещения"""
    try:
        return PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()
    except Exception as e:
        logger.error(f"Ошибка получения периодов: {e}", exc_info=True)
        return PricingPeriod.objects.none()


@login_required
def create_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """Создание бронирования"""
    try:
        space = get_object_or_404(
            Space.objects.select_related('city', 'category', 'owner')
            .prefetch_related('images', 'prices', 'prices__period'),
            pk=pk, is_active=True
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

                    # Получаем цену
                    try:
                        price_obj = SpacePrice.objects.get(
                            space=space, period=booking.period, is_active=True
                        )
                        booking.price_per_period = price_obj.price
                    except SpacePrice.DoesNotExist:
                        messages.error(request, 'Выбранный период недоступен')
                        return redirect('space_detail', pk=pk)

                    booking.total_amount = booking.price_per_period * booking.periods_count

                    # Установка дат
                    start_date = form.cleaned_data['start_date']
                    start_time = form.cleaned_data['start_time']
                    booking.start_datetime = timezone.make_aware(
                        datetime.combine(start_date, start_time)
                    )

                    total_hours = booking.period.hours_count * booking.periods_count
                    booking.end_datetime = booking.start_datetime + timedelta(hours=total_hours)

                    if booking.start_datetime <= timezone.now():
                        messages.error(request, 'Дата начала должна быть в будущем')
                        return render(request, 'bookings/create.html', {
                            'space': space, 'prices': prices, 'form': form
                        })

                    booking.status = StatusService.get_pending()
                    booking.save()

                    messages.success(
                        request,
                        f'Бронирование #{booking.id} создано! Сумма: {booking.total_amount} ₽'
                    )
                    return redirect('booking_detail', pk=booking.pk)

                except (DatabaseError, IntegrityError) as e:
                    logger.error(f"Ошибка БД: {e}", exc_info=True)
                    messages.error(request, 'Ошибка при создании. Попробуйте снова.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
        else:
            form = BookingForm()
            form.fields['period'].queryset = available_periods

        return render(request, 'bookings/create.html', {
            'space': space, 'prices': prices, 'form': form
        })

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Ошибка в create_booking pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Произошла ошибка')
        return redirect('spaces_list')


@login_required
def booking_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Детали бронирования"""
    try:
        booking = get_object_or_404(
            Booking.objects.select_related(
                'space', 'space__city', 'space__category', 'space__owner',
                'status', 'period', 'tenant'
            ).prefetch_related('space__images', 'transactions'),
            pk=pk, tenant=request.user
        )

        return render(request, 'bookings/detail.html', {
            'booking': booking,
            'can_cancel': booking.is_cancellable,
            'can_review': booking.status.code == 'completed' and not hasattr(booking, 'review'),
        })

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Ошибка booking_detail pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка загрузки')
        return redirect('my_bookings')


@login_required
@require_POST
def cancel_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """Отмена бронирования"""
    try:
        booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

        if not booking.is_cancellable:
            messages.error(request, 'Бронирование нельзя отменить')
            return redirect('booking_detail', pk=pk)

        hours_until = (booking.start_datetime - timezone.now()).total_seconds() / 3600
        if hours_until < 24:
            messages.warning(request, 'Отмена менее чем за 24 часа может быть платной')

        booking.status = StatusService.get_cancelled()
        booking.save()

        messages.success(request, f'Бронирование #{booking.id} отменено')
        return redirect('my_bookings')

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Ошибка cancel_booking pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка отмены')
        return redirect('my_bookings')


@login_required
def get_price_for_period(request: HttpRequest, space_id: int, period_id: int) -> JsonResponse:
    """AJAX: получение цены периода"""
    try:
        price = SpacePrice.objects.select_related('period').get(
            space_id=space_id, period_id=period_id, is_active=True
        )
        return JsonResponse({
            'success': True,
            'price': float(price.price),
            'period_hours': price.period.hours_count,
            'period_name': price.period.description
        })
    except SpacePrice.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Цена не найдена'}, status=404)
    except Exception as e:
        logger.error(f"Ошибка get_price_for_period: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Ошибка сервера'}, status=500)
