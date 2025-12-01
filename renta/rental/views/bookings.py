"""
ПРЕДСТАВЛЕНИЯ ДЛЯ БРОНИРОВАНИЙ
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from ..models import (
    Space, SpacePrice, PricingPeriod, Booking, BookingStatus
)
from ..forms import BookingForm


@login_required
def create_booking(request, pk):
    """
    Создание нового бронирования
    """
    space = get_object_or_404(
        Space.objects.select_related('city', 'category', 'owner')
        .prefetch_related('images', 'prices', 'prices__period'),
        pk=pk,
        is_active=True
    )
    
    # Получаем доступные цены
    prices = space.prices.filter(is_active=True).select_related('period')
    
    if request.method == 'POST':
        form = BookingForm(request.POST)
        
        # Ограничиваем выбор периодов теми, что доступны для этого помещения
        available_periods = PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()
        form.fields['period'].queryset = available_periods
        
        if form.is_valid():
            booking = form.save(commit=False)
            booking.space = space
            booking.tenant = request.user
            
            # Получаем цену за выбранный период
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
            
            # Рассчитываем общую стоимость
            booking.total_amount = booking.price_per_period * booking.periods_count
            
            # Формируем даты
            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            booking.start_datetime = timezone.make_aware(
                datetime.combine(start_date, start_time)
            )
            
            # Рассчитываем время окончания
            total_hours = booking.period.hours_count * booking.periods_count
            booking.end_datetime = booking.start_datetime + timedelta(hours=total_hours)
            
            # Проверяем, что дата начала в будущем
            if booking.start_datetime <= timezone.now():
                messages.error(request, 'Дата начала должна быть в будущем')
                return render(request, 'bookings/create.html', {
                    'space': space, 'prices': prices, 'form': form
                })
            
            # Устанавливаем статус "Ожидание подтверждения"
            pending_status, _ = BookingStatus.objects.get_or_create(
                code='pending',
                defaults={'name': 'Ожидание', 'color': 'warning', 'sort_order': 1}
            )
            booking.status = pending_status
            
            booking.save()
            
            messages.success(
                request, 
                f'Бронирование #{booking.id} успешно создано! '
                f'Сумма: {booking.total_amount} ₽'
            )
            return redirect('booking_detail', pk=booking.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = BookingForm()
        form.fields['period'].queryset = PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()
    
    context = {
        'space': space,
        'prices': prices,
        'form': form,
    }
    return render(request, 'bookings/create.html', context)


@login_required
def booking_detail(request, pk):
    """
    Детальная информация о бронировании
    """
    booking = get_object_or_404(
        Booking.objects.select_related(
            'space', 'space__city', 'space__category', 'space__owner',
            'status', 'period', 'tenant'
        ).prefetch_related('space__images', 'transactions'),
        pk=pk,
        tenant=request.user
    )
    
    # Проверяем возможность отмены
    can_cancel = booking.status.code in ['pending', 'confirmed']
    
    # Проверяем возможность оставить отзыв
    can_review = (
        booking.status.code == 'completed' and 
        not hasattr(booking, 'review')
    )
    
    context = {
        'booking': booking,
        'can_cancel': can_cancel,
        'can_review': can_review,
    }
    return render(request, 'bookings/detail.html', context)


@login_required
@require_POST
def cancel_booking(request, pk):
    """
    Отмена бронирования
    """
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user)
    
    # Проверяем, можно ли отменить
    if booking.status.code not in ['pending', 'confirmed']:
        messages.error(request, 'Это бронирование нельзя отменить')
        return redirect('booking_detail', pk=pk)
    
    # Проверяем, что до начала аренды больше 24 часов
    hours_until_start = (booking.start_datetime - timezone.now()).total_seconds() / 3600
    if hours_until_start < 24:
        messages.warning(
            request, 
            'Отмена менее чем за 24 часа до начала аренды может быть платной'
        )
    
    # Меняем статус на "Отменено"
    cancelled_status, _ = BookingStatus.objects.get_or_create(
        code='cancelled',
        defaults={'name': 'Отменено', 'color': 'danger', 'sort_order': 4}
    )
    booking.status = cancelled_status
    booking.save()
    
    messages.success(request, f'Бронирование #{booking.id} успешно отменено')
    return redirect('my_bookings')


@login_required
def get_price_for_period(request, space_id, period_id):
    """
    AJAX: получить цену за период для калькулятора
    """
    try:
        price = SpacePrice.objects.get(
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
        })
