"""
====================================================================
СЕРВИС БРОНИРОВАНИЙ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит бизнес-логику для операций с бронированиями,
включая создание, подтверждение, отмену и завершение бронирований,
а также расчет стоимости и проверку доступности.

Основные классы:
- BookingError: Кастомное исключение для ошибок бронирования
- BookingService: Сервисный класс с бизнес-логикой бронирования

Функционал:
- Расчет стоимости бронирования с учетом периода и количества
- Проверка доступности помещений в указанные даты
- Создание новых бронирований с транзакционной безопасностью
- Управление статусами бронирований (подтверждение, отмена, завершение)
- Получение списков бронирований для пользователей и помещений
====================================================================
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
from .status_service import StatusService
from ..core.exceptions import BookingError


logger = logging.getLogger(__name__)


class BookingService:
    """
    Сервисный класс для операций с бронированиями.

    Содержит статические методы для выполнения основных операций
    с бронированиями, обеспечивая транзакционную безопасность
    и централизованную логику.
    """

    @staticmethod
    def calculate_total_price(
        space_id: int,
        period_id: int,
        periods_count: int
    ) -> dict[str, Any]:
        """
        Расчет стоимости бронирования.

        Вычисляет общую стоимость аренды на основе цены помещения
        за выбранный период и количества периодов.

        Args:
            space_id (int): ID помещения
            period_id (int): ID периода аренды
            periods_count (int): Количество периодов

        Returns:
            dict[str, Any]: Словарь с деталями расчета или ошибкой
                - success (bool): Флаг успешности расчета
                - price_per_period (Decimal): Цена за один период
                - total (Decimal): Общая стоимость
                - hours (int): Общее количество часов
                - period_name (str): Описание периода
                - error (str): Сообщение об ошибке (при неудаче)
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
        Проверка доступности помещения в указанный период.

        Проверяет, свободно ли помещение в запрашиваемый промежуток
        времени, исключая указанное бронирование (для обновлений).

        Args:
            space_id (int): ID помещения
            start_datetime: Дата и время начала аренды
            end_datetime: Дата и время окончания аренды
            exclude_booking_id (Optional[int]): ID бронирования для исключения
                (используется при редактировании существующего бронирования)

        Returns:
            bool: True если помещение доступно, False если занято
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
        Создание нового бронирования.

        Создает новое бронирование с проверкой доступности,
        расчетом стоимости и транзакционной безопасностью.

        Args:
            space (Space): Помещение для бронирования
            tenant (CustomUser): Пользователь, создающий бронирование
            period (PricingPeriod): Период аренды
            start_datetime: Дата и время начала аренды
            periods_count (int): Количество периодов
            comment (str): Дополнительный комментарий (по умолчанию '')

        Returns:
            Booking: Созданное бронирование

        Raises:
            BookingError: При невозможности создать бронирование
                (помещение занято, цена не найдена, ошибка БД и т.д.)
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

            pending_status = StatusService.get_pending_status()

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
        Подтверждение ожидающего бронирования.

        Изменяет статус бронирования с 'pending' на 'confirmed'
        с транзакционной безопасностью.

        Args:
            booking_id (int): ID бронирования для подтверждения

        Returns:
            Booking: Подтвержденное бронирование

        Raises:
            BookingError: При невозможности подтвердить бронирование
                (бронирование не найдено, неверный статус, ошибка БД)
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if booking.status.code != 'pending':
                raise BookingError('Можно подтвердить только ожидающее бронирование')

            booking.status = StatusService.get_confirmed_status()
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
        Отмена бронирования.

        Изменяет статус бронирования на 'cancelled' с проверкой
        возможности отмены и транзакционной безопасностью.

        Args:
            booking_id (int): ID бронирования для отмены
            by_user (Optional[CustomUser]): Пользователь, отменяющий бронирование
                (в текущей реализации не используется, оставлен для будущего расширения)

        Returns:
            Booking: Отмененное бронирование

        Raises:
            BookingError: При невозможности отменить бронирование
                (бронирование не найдено, отмена невозможна, ошибка БД)
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if not booking.is_cancellable:
                raise BookingError('Это бронирование нельзя отменить')

            booking.status = StatusService.get_cancelled_status()
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
        Завершение бронирования.

        Изменяет статус бронирования с 'confirmed' на 'completed'
        после успешного завершения аренды.

        Args:
            booking_id (int): ID бронирования для завершения

        Returns:
            Booking: Завершенное бронирование

        Raises:
            BookingError: При невозможности завершить бронирование
                (бронирование не найдено, неверный статус, ошибка БД)
        """
        try:
            booking = Booking.objects.select_for_update().get(pk=booking_id)

            if booking.status.code != 'confirmed':
                raise BookingError('Можно завершить только подтверждённое бронирование')

            booking.status = StatusService.get_completed_status()
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
        Получение списка бронирований пользователя.

        Возвращает все бронирования пользователя с возможностью
        фильтрации по статусу и предзагрузкой связанных данных.

        Args:
            user (CustomUser): Пользователь, чьи бронирования запрашиваются
            status_code (Optional[str]): Код статуса для фильтрации
                (например, 'pending', 'confirmed', 'completed', 'cancelled')

        Returns:
            QuerySet[Booking]: Набор бронирований пользователя,
                отсортированный по дате создания (новые сначала)
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
        Получение списка бронирований помещения.

        Возвращает все бронирования указанного помещения
        с возможностью включения или исключения отмененных.

        Args:
            space_id (int): ID помещения
            include_cancelled (bool): Включать ли отмененные бронирования

        Returns:
            QuerySet[Booking]: Набор бронирований помещения,
                отсортированный по дате начала аренды
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
