"""
СЕРВИС БРОНИРОВАНИЙ

Business logic for booking operations.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction, DatabaseError
from django.db.models import QuerySet
from django.utils import timezone

from ..models import (
    Booking, BookingStatus, Space, SpacePrice,
    PricingPeriod, CustomUser
)


logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Custom exception for booking errors."""
    pass


class BookingService:
    """Service class for booking operations."""

    @staticmethod
    def calculate_total_price(
        space_id: int,
        period_id: int,
        periods_count: int
    ) -> dict[str, Any]:
        """
        Calculate booking cost.

        Args:
            space_id: Space primary key
            period_id: Period primary key
            periods_count: Number of periods

        Returns:
            Dictionary with price details or error
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
        except Exception as e:
            logger.error(f"Error calculating total price: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Ошибка при расчёте цены'
            }

    @staticmethod
    def check_availability(
        space_id: int,
        start_datetime,
        end_datetime,
        exclude_booking_id: Optional[int] = None
    ) -> bool:
        """
        Check if space is available for the given period.

        Args:
            space_id: Space primary key
            start_datetime: Start of booking period
            end_datetime: End of booking period
            exclude_booking_id: Booking ID to exclude (for updates)

        Returns:
            True if available, False otherwise
        """
        try:
            conflicting = Booking.objects.active().filter(
                space_id=space_id,
                start_datetime__lt=end_datetime,
                end_datetime__gt=start_datetime
            )

            if exclude_booking_id:
                conflicting = conflicting.exclude(pk=exclude_booking_id)

            return not conflicting.exists()
        except Exception as e:
            logger.error(f"Error checking availability: {e}", exc_info=True)
            return False  # Fail safe - assume not available

    @staticmethod
    def _get_or_create_status(code: str, defaults: dict[str, Any]) -> BookingStatus:
        """Get or create a booking status."""
        try:
            status, _ = BookingStatus.objects.get_or_create(code=code, defaults=defaults)
            return status
        except Exception as e:
            logger.error(f"Error getting/creating status '{code}': {e}", exc_info=True)
            raise BookingError(f'Ошибка при получении статуса: {code}')

    @staticmethod
    @transaction.atomic
    def create_booking(
        space: Space,
        tenant: CustomUser,
        period: PricingPeriod,
        start_datetime,
        periods_count: int,
        comment: str = ''
    ) -> Booking:
        """
        Create a new booking.

        Args:
            space: Space to book
            tenant: User making the booking
            period: Pricing period
            start_datetime: Start of booking
            periods_count: Number of periods
            comment: Optional comment

        Returns:
            Created booking

        Raises:
            BookingError: If booking cannot be created
        """
        try:
            # Get price
            try:
                price_obj = SpacePrice.objects.get(
                    space=space,
                    period=period,
                    is_active=True
                )
            except SpacePrice.DoesNotExist:
                raise BookingError('Цена для выбранного периода не найдена')

            # Calculate end datetime
            total_hours = period.hours_count * periods_count
            end_datetime = start_datetime + timedelta(hours=total_hours)

            # Check availability
            if not BookingService.check_availability(space.id, start_datetime, end_datetime):
                raise BookingError('Помещение занято в указанный период')

            # Get pending status
            pending_status = BookingService._get_or_create_status('pending', {
                'name': 'Ожидание',
                'color': 'warning',
                'sort_order': 1
            })

            # Create booking
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

        except BookingError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error creating booking: {e}", exc_info=True)
            raise BookingError('Ошибка базы данных при создании бронирования')
        except Exception as e:
            logger.error(f"Error creating booking: {e}", exc_info=True)
            raise BookingError('Неизвестная ошибка при создании бронирования')

    @staticmethod
    @transaction.atomic
    def confirm_booking(booking_id: int) -> Booking:
        """
        Confirm a pending booking.

        Args:
            booking_id: Booking primary key

        Returns:
            Updated booking

        Raises:
            BookingError: If booking cannot be confirmed
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if booking.status.code != 'pending':
                raise BookingError('Можно подтвердить только ожидающее бронирование')

            confirmed_status = BookingService._get_or_create_status('confirmed', {
                'name': 'Подтверждено',
                'color': 'success',
                'sort_order': 2
            })
            booking.status = confirmed_status
            booking.save()

            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error confirming booking: {e}", exc_info=True)
            raise BookingError('Ошибка базы данных при подтверждении')
        except Exception as e:
            logger.error(f"Error confirming booking: {e}", exc_info=True)
            raise BookingError('Ошибка при подтверждении бронирования')

    @staticmethod
    @transaction.atomic
    def cancel_booking(
        booking_id: int,
        by_user: Optional[CustomUser] = None
    ) -> Booking:
        """
        Cancel a booking.

        Args:
            booking_id: Booking primary key
            by_user: User cancelling the booking

        Returns:
            Updated booking

        Raises:
            BookingError: If booking cannot be cancelled
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if not booking.is_cancellable:
                raise BookingError('Это бронирование нельзя отменить')

            cancelled_status = BookingService._get_or_create_status('cancelled', {
                'name': 'Отменено',
                'color': 'danger',
                'sort_order': 4
            })
            booking.status = cancelled_status
            booking.save()

            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error cancelling booking: {e}", exc_info=True)
            raise BookingError('Ошибка базы данных при отмене')
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}", exc_info=True)
            raise BookingError('Ошибка при отмене бронирования')

    @staticmethod
    @transaction.atomic
    def complete_booking(booking_id: int) -> Booking:
        """
        Mark booking as completed.

        Args:
            booking_id: Booking primary key

        Returns:
            Updated booking

        Raises:
            BookingError: If booking cannot be completed
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if booking.status.code != 'confirmed':
                raise BookingError('Можно завершить только подтверждённое бронирование')

            completed_status = BookingService._get_or_create_status('completed', {
                'name': 'Завершено',
                'color': 'info',
                'sort_order': 3
            })
            booking.status = completed_status
            booking.save()

            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except DatabaseError as e:
            logger.error(f"Database error completing booking: {e}", exc_info=True)
            raise BookingError('Ошибка базы данных при завершении')
        except Exception as e:
            logger.error(f"Error completing booking: {e}", exc_info=True)
            raise BookingError('Ошибка при завершении бронирования')

    @staticmethod
    def get_user_bookings(
        user: CustomUser,
        status_code: Optional[str] = None
    ) -> QuerySet[Booking]:
        """
        Get bookings for a user.

        Args:
            user: User to get bookings for
            status_code: Optional status filter

        Returns:
            Queryset of bookings
        """
        try:
            bookings = Booking.objects.for_user(user).select_related(
                'space', 'space__city', 'status', 'period'
            ).prefetch_related('space__images')

            if status_code:
                bookings = bookings.filter(status__code=status_code)

            return bookings.order_by('-created_at')
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}", exc_info=True)
            return Booking.objects.none()

    @staticmethod
    def get_space_bookings(
        space_id: int,
        include_cancelled: bool = False
    ) -> QuerySet[Booking]:
        """
        Get bookings for a space.

        Args:
            space_id: Space primary key
            include_cancelled: Whether to include cancelled bookings

        Returns:
            Queryset of bookings
        """
        try:
            bookings = Booking.objects.for_space(space_id).select_related(
                'tenant', 'status', 'period'
            )

            if not include_cancelled:
                bookings = bookings.exclude(status__code='cancelled')

            return bookings.order_by('start_datetime')
        except Exception as e:
            logger.error(f"Error getting space bookings: {e}", exc_info=True)
            return Booking.objects.none()
