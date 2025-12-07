"""
СЕРВИС БРОНИРОВАНИЙ
Бизнес-логика бронирований
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction, DatabaseError
from django.db.models import QuerySet

from ..models import Booking, Space, SpacePrice, PricingPeriod, CustomUser
from .status_service import StatusService

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """Ошибка бронирования"""
    pass


class BookingService:
    """Сервис бронирований"""

    @staticmethod
    def calculate_total_price(space_id: int, period_id: int, periods_count: int) -> dict[str, Any]:
        """Расчёт стоимости бронирования"""
        try:
            price_obj = SpacePrice.objects.select_related('period').get(
                space_id=space_id,
                period_id=period_id,
                is_active=True
            )
            return {
                'price_per_period': price_obj.price,
                'total': price_obj.price * periods_count,
                'hours': price_obj.period.hours_count * periods_count,
                'period_name': price_obj.period.description,
                'success': True
            }
        except SpacePrice.DoesNotExist:
            return {'success': False, 'error': 'Цена не найдена'}
        except Exception as e:
            logger.error(f"Ошибка расчёта цены: {e}", exc_info=True)
            return {'success': False, 'error': 'Ошибка расчёта'}

    @staticmethod
    def check_availability(
        space_id: int,
        start_datetime,
        end_datetime,
        exclude_booking_id: Optional[int] = None
    ) -> bool:
        """Проверка доступности помещения"""
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
            logger.error(f"Ошибка проверки доступности: {e}", exc_info=True)
            return False

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
        """Создание бронирования"""
        try:
            # Получаем цену
            try:
                price_obj = SpacePrice.objects.get(space=space, period=period, is_active=True)
            except SpacePrice.DoesNotExist:
                raise BookingError('Цена для периода не найдена')

            # Расчёт времени окончания
            total_hours = period.hours_count * periods_count
            end_datetime = start_datetime + timedelta(hours=total_hours)

            # Проверка доступности
            if not BookingService.check_availability(space.id, start_datetime, end_datetime):
                raise BookingError('Помещение занято')

            # Создание бронирования
            booking = Booking.objects.create(
                space=space,
                tenant=tenant,
                period=period,
                status=StatusService.get_pending(),
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
            logger.error(f"Ошибка БД при создании: {e}", exc_info=True)
            raise BookingError('Ошибка базы данных')
        except Exception as e:
            logger.error(f"Ошибка создания бронирования: {e}", exc_info=True)
            raise BookingError('Неизвестная ошибка')

    @staticmethod
    @transaction.atomic
    def confirm_booking(booking_id: int) -> Booking:
        """Подтверждение бронирования"""
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
            if booking.status.code != 'pending':
                raise BookingError('Можно подтвердить только ожидающее бронирование')

            booking.status = StatusService.get_confirmed()
            booking.save()
            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except Exception as e:
            logger.error(f"Ошибка подтверждения: {e}", exc_info=True)
            raise BookingError('Ошибка подтверждения')

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking_id: int, by_user: Optional[CustomUser] = None) -> Booking:
        """Отмена бронирования"""
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
            if not booking.is_cancellable:
                raise BookingError('Бронирование нельзя отменить')

            booking.status = StatusService.get_cancelled()
            booking.save()
            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except Exception as e:
            logger.error(f"Ошибка отмены: {e}", exc_info=True)
            raise BookingError('Ошибка отмены')

    @staticmethod
    @transaction.atomic
    def complete_booking(booking_id: int) -> Booking:
        """Завершение бронирования"""
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)
            if booking.status.code != 'confirmed':
                raise BookingError('Можно завершить только подтверждённое бронирование')

            booking.status = StatusService.get_completed()
            booking.save()
            return booking

        except Booking.DoesNotExist:
            raise BookingError('Бронирование не найдено')
        except BookingError:
            raise
        except Exception as e:
            logger.error(f"Ошибка завершения: {e}", exc_info=True)
            raise BookingError('Ошибка завершения')

    @staticmethod
    def get_user_bookings(user: CustomUser, status_code: Optional[str] = None) -> QuerySet[Booking]:
        """Получение бронирований пользователя"""
        try:
            bookings = Booking.objects.for_user(user).select_related(
                'space', 'space__city', 'status', 'period'
            ).prefetch_related('space__images')

            if status_code:
                bookings = bookings.filter(status__code=status_code)
            return bookings.order_by('-created_at')
        except Exception as e:
            logger.error(f"Ошибка получения бронирований: {e}", exc_info=True)
            return Booking.objects.none()

    @staticmethod
    def get_space_bookings(space_id: int, include_cancelled: bool = False) -> QuerySet[Booking]:
        """Получение бронирований помещения"""
        try:
            bookings = Booking.objects.for_space(space_id).select_related('tenant', 'status', 'period')
            if not include_cancelled:
                bookings = bookings.exclude(status__code='cancelled')
            return bookings.order_by('start_datetime')
        except Exception as e:
            logger.error(f"Ошибка получения бронирований помещения: {e}", exc_info=True)
            return Booking.objects.none()
