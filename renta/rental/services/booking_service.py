"""
СЕРВИС БРОНИРОВАНИЙ
Вся бизнес-логика связанная с бронированиями
"""

from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal

from ..models import (
    Booking, BookingStatus, Space, SpacePrice, 
    PricingPeriod, Transaction, TransactionStatus
)


class BookingService:
    """Сервис для работы с бронированиями"""
    
    @staticmethod
    def calculate_total_price(space_id: int, period_id: int, periods_count: int) -> dict:
        """
        Рассчитать стоимость бронирования
        
        Returns:
            dict: {'price_per_period': Decimal, 'total': Decimal, 'hours': int}
        """
        try:
            price_obj = SpacePrice.objects.select_related('period').get(
                space_id=space_id,
                period_id=period_id,
                is_active=True
            )
            
            price_per_period = price_obj.price
            total = price_per_period * periods_count
            total_hours = price_obj.period.hours_count * periods_count
            
            return {
                'price_per_period': price_per_period,
                'total': total,
                'hours': total_hours,
                'period_name': price_obj.period.description,
                'success': True
            }
        except SpacePrice.DoesNotExist:
            return {
                'success': False,
                'error': 'Цена не найдена'
            }

    @staticmethod
    def check_availability(space_id: int, start_datetime, end_datetime, exclude_booking_id=None) -> bool:
        """
        Проверить доступность помещения на указанный период
        
        Returns:
            bool: True если доступно
        """
        conflicting = Booking.objects.filter(
            space_id=space_id,
            status__code__in=['pending', 'confirmed'],
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime
        )
        
        if exclude_booking_id:
            conflicting = conflicting.exclude(pk=exclude_booking_id)
        
        return not conflicting.exists()

    @staticmethod
    @transaction.atomic
    def create_booking(
        space: Space,
        tenant,
        period: PricingPeriod,
        start_datetime,
        periods_count: int,
        comment: str = ''
    ) -> Booking:
        """
        Создать новое бронирование
        
        Returns:
            Booking: созданное бронирование
        
        Raises:
            ValueError: если помещение недоступно или цена не найдена
        """
        # Получаем цену
        try:
            price_obj = SpacePrice.objects.get(
                space=space,
                period=period,
                is_active=True
            )
        except SpacePrice.DoesNotExist:
            raise ValueError('Цена для выбранного периода не найдена')
        
        # Рассчитываем время окончания
        total_hours = period.hours_count * periods_count
        end_datetime = start_datetime + timedelta(hours=total_hours)
        
        # Проверяем доступность
        if not BookingService.check_availability(space.id, start_datetime, end_datetime):
            raise ValueError('Помещение занято в указанный период')
        
        # Получаем статус "Ожидание"
        pending_status, _ = BookingStatus.objects.get_or_create(
            code='pending',
            defaults={'name': 'Ожидание', 'color': 'warning', 'sort_order': 1}
        )
        
        # Создаем бронирование
        booking = Booking.objects.create(
            space=space,
            tenant=tenant,
            period=period,
            status=pending_status,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            periods_count=periods_count,
            price_per_period=price_obj.price,
            total_amount=price_obj.price * periods_count,
            comment=comment
        )
        
        return booking

    @staticmethod
    @transaction.atomic
    def confirm_booking(booking_id: int) -> Booking:
        """Подтвердить бронирование"""
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        
        if booking.status.code != 'pending':
            raise ValueError('Можно подтвердить только ожидающее бронирование')
        
        confirmed_status, _ = BookingStatus.objects.get_or_create(
            code='confirmed',
            defaults={'name': 'Подтверждено', 'color': 'success', 'sort_order': 2}
        )
        booking.status = confirmed_status
        booking.save()
        
        return booking

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking_id: int, by_user=None) -> Booking:
        """Отменить бронирование"""
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        
        if booking.status.code not in ['pending', 'confirmed']:
            raise ValueError('Это бронирование нельзя отменить')
        
        cancelled_status, _ = BookingStatus.objects.get_or_create(
            code='cancelled',
            defaults={'name': 'Отменено', 'color': 'danger', 'sort_order': 4}
        )
        booking.status = cancelled_status
        booking.save()
        
        return booking

    @staticmethod
    @transaction.atomic
    def complete_booking(booking_id: int) -> Booking:
        """Завершить бронирование"""
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        
        if booking.status.code != 'confirmed':
            raise ValueError('Можно завершить только подтверждённое бронирование')
        
        completed_status, _ = BookingStatus.objects.get_or_create(
            code='completed',
            defaults={'name': 'Завершено', 'color': 'info', 'sort_order': 3}
        )
        booking.status = completed_status
        booking.save()
        
        return booking

    @staticmethod
    def get_user_bookings(user, status_code=None):
        """Получить бронирования пользователя"""
        bookings = Booking.objects.filter(tenant=user).select_related(
            'space', 'space__city', 'status', 'period'
        ).prefetch_related('space__images')
        
        if status_code:
            bookings = bookings.filter(status__code=status_code)
        
        return bookings.order_by('-created_at')

    @staticmethod
    def get_space_bookings(space_id: int, include_cancelled=False):
        """Получить бронирования помещения"""
        bookings = Booking.objects.filter(space_id=space_id).select_related(
            'tenant', 'status', 'period'
        )
        
        if not include_cancelled:
            bookings = bookings.exclude(status__code='cancelled')
        
        return bookings.order_by('start_datetime')
