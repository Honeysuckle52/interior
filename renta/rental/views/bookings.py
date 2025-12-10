"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ БРОНИРОВАНИЙ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для всей функциональности,
связанной с бронированиями помещений, включая создание, просмотр,
подтверждение, отклонение, отмену бронирований и управление ими.

Основные представления:
- create_booking: Создание нового бронирования помещения
- booking_detail: Просмотр деталей конкретного бронирования
- confirm_booking: Подтверждение бронирования модератором
- reject_booking: Отклонение бронирования модератором
- manage_bookings: Панель управления бронированиями для администраторов
- cancel_booking: Отмена бронирования пользователем
- get_price_for_period: AJAX endpoint для получения цены за период

Вспомогательные функции:
- _get_available_periods: Получение доступных периодов для помещения
- _check_booking_overlap: Проверка пересечений с существующими бронированиями

Константы:
- HOURS_IN_DAY: Количество часов в сутках (для проверки отмены)
- SECONDS_IN_HOUR: Количество секунд в часе
- DEFAULT_*_SORT_ORDER: Порядок сортировки статусов по умолчанию
- BOOKINGS_PER_PAGE: Количество бронирований на странице пагинации

Особенности:
- Защита представлений декораторами @login_required и @require_POST
- Проверка прав доступа для разных типов пользователей
- Обработка конфликтов бронирований по времени
- Оптимизированные запросы к БД с использованием select_related и prefetch_related
- Поддержка AJAX запросов для динамического расчета цены
====================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError, IntegrityError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import BookingForm
from ..models import Space, SpacePrice, PricingPeriod, Booking, BookingStatus
from ..services.status_service import StatusService, StatusCodes
from ..core.pagination import paginate, DEFAULT_PAGE_SIZE
from ..core.decorators import moderator_required, handle_view_errors


# Константы
HOURS_IN_DAY: int = 24
SECONDS_IN_HOUR: int = 3600
BOOKINGS_PER_PAGE: int = 10

logger = logging.getLogger(__name__)


def _get_available_periods(space: Space) -> Any:
    """
    Получение доступных периодов ценообразования для помещения.

    Args:
        space (Space): Помещение для поиска периодов

    Returns:
        QuerySet[PricingPeriod]: Набор доступных периодов
    """
    try:
        return PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()
    except Exception as e:
        logger.error(f"Error getting available periods: {e}", exc_info=True)
        return PricingPeriod.objects.none()


def _check_booking_overlap(
    space: Space,
    start_datetime: datetime,
    end_datetime: datetime,
    exclude_booking_id: Optional[int] = None
) -> Optional[Booking]:
    """
    Проверка пересечения с существующими бронированиями помещения.

    Args:
        space (Space): Помещение для проверки
        start_datetime (datetime): Начало запрашиваемого периода
        end_datetime (datetime): Конец запрашиваемого периода
        exclude_booking_id (Optional[int]): ID бронирования для исключения
            (используется при редактировании существующего бронирования)

    Returns:
        Optional[Booking]: Конфликтующее бронирование или None
    """
    overlapping = Booking.objects.filter(
        space=space,
        status__code__in=[StatusCodes.PENDING, StatusCodes.CONFIRMED],
    ).filter(
        # Пересечение интервалов: start1 < end2 AND start2 < end1
        Q(start_datetime__lt=end_datetime) & Q(end_datetime__gt=start_datetime)
    )

    if exclude_booking_id:
        overlapping = overlapping.exclude(pk=exclude_booking_id)

    return overlapping.first()


@login_required
def create_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Создание нового бронирования для помещения.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID помещения для бронирования

    Returns:
        HttpResponse: Отрисовка формы бронирования или редирект при успехе

    Template:
        bookings/create.html

    Context:
        - space: Помещение для бронирования
        - prices: Активные цены помещения
        - form: Форма создания бронирования
    """
    try:
        space: Space = get_object_or_404(
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
                    booking: Booking = form.save(commit=False)
                    booking.space = space
                    booking.tenant = request.user

                    try:
                        price_obj: SpacePrice = SpacePrice.objects.get(
                            space=space,
                            period=booking.period,
                            is_active=True
                        )
                        booking.price_per_period = price_obj.price
                    except SpacePrice.DoesNotExist:
                        messages.error(request, 'Выбранный период недоступен')
                        return redirect('space_detail', pk=pk)

                    booking.total_amount = booking.price_per_period * booking.periods_count

                    start_date = form.cleaned_data['start_date']
                    start_time = form.cleaned_data['start_time']
                    booking.start_datetime = timezone.make_aware(
                        datetime.combine(start_date, start_time)
                    )

                    total_hours: int = booking.period.hours_count * booking.periods_count
                    booking.end_datetime = booking.start_datetime + timedelta(hours=total_hours)

                    if booking.start_datetime <= timezone.now():
                        messages.error(request, 'Дата начала должна быть в будущем')
                        return render(request, 'bookings/create.html', {
                            'space': space, 'prices': prices, 'form': form
                        })

                    conflicting_booking = _check_booking_overlap(
                        space, booking.start_datetime, booking.end_datetime
                    )
                    if conflicting_booking:
                        messages.error(
                            request,
                            f'Помещение уже забронировано на это время '
                            f'({conflicting_booking.start_datetime.strftime("%d.%m.%Y %H:%M")} - '
                            f'{conflicting_booking.end_datetime.strftime("%d.%m.%Y %H:%M")}). '
                            f'Пожалуйста, выберите другое время.'
                        )
                        return render(request, 'bookings/create.html', {
                            'space': space, 'prices': prices, 'form': form
                        })

                    booking.status = StatusService.get_pending_status()
                    booking.save()

                    messages.success(
                        request,
                        f'Бронирование #{booking.id} создано! '
                        f'Сумма: {booking.total_amount:.2f} ₽'
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

        context: dict[str, Any] = {
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
    Просмотр деталей бронирования.

    Администраторы и модераторы могут просматривать любые бронирования,
    обычные пользователи - только свои.

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID бронирования

    Returns:
        HttpResponse: Отрисовка страницы деталей бронирования

    Template:
        bookings/detail.html

    Context:
        - booking: Объект бронирования
        - can_cancel: Может ли пользователь отменить бронирование
        - can_manage: Может ли пользователь управлять бронированием (админ/модератор)
        - is_owner: Является ли пользователь владельцем бронирования
        - can_review: Может ли пользователь оставить отзыв для этого бронирования
    """
    try:
        user = request.user

        if user.can_moderate:
            booking: Booking = get_object_or_404(
                Booking.objects.select_related(
                    'space', 'space__city', 'space__category', 'space__owner',
                    'status', 'period', 'tenant'
                ).prefetch_related('space__images', 'transactions'),
                pk=pk
            )
        else:
            booking = get_object_or_404(
                Booking.objects.select_related(
                    'space', 'space__city', 'space__category', 'space__owner',
                    'status', 'period', 'tenant'
                ).prefetch_related('space__images', 'transactions'),
                pk=pk,
                tenant=user
            )

        can_manage: bool = user.can_moderate and booking.status.code == StatusCodes.PENDING
        is_owner: bool = booking.tenant == user

        context: dict[str, Any] = {
            'booking': booking,
            'can_cancel': booking.is_cancellable and is_owner,
            'can_manage': can_manage,
            'is_owner': is_owner,
            'can_review': (
                booking.status.code == StatusCodes.COMPLETED and
                not hasattr(booking, 'review') and
                is_owner
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
def confirm_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Подтверждение ожидающего бронирования (только для модераторов/администраторов).

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID бронирования для подтверждения

    Returns:
        HttpResponse: Редирект на страницу деталей бронирования
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для подтверждения бронирований')
            return redirect('booking_detail', pk=pk)

        booking: Booking = get_object_or_404(Booking, pk=pk)

        if booking.status.code != StatusCodes.PENDING:
            messages.error(request, 'Можно подтвердить только бронирования в статусе ожидания')
            return redirect('booking_detail', pk=pk)

        moderator_comment = request.POST.get('moderator_comment', '').strip()
        if moderator_comment:
            booking.moderator_comment = moderator_comment

        booking.status = StatusService.get_confirmed_status()
        booking.save()

        messages.success(request, f'Бронирование #{booking.id} успешно подтверждено!')
        return redirect('booking_detail', pk=pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in confirm_booking view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при подтверждении бронирования')
        return redirect('booking_detail', pk=pk)


@login_required
@require_POST
def reject_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Отклонение ожидающего бронирования (только для модераторов/администраторов).

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID бронирования для отклонения

    Returns:
        HttpResponse: Редирект на страницу деталей бронирования
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для отклонения бронирований')
            return redirect('booking_detail', pk=pk)

        booking: Booking = get_object_or_404(Booking, pk=pk)

        if booking.status.code != StatusCodes.PENDING:
            messages.error(request, 'Можно отклонить только бронирования в статусе ожидания')
            return redirect('booking_detail', pk=pk)

        moderator_comment = request.POST.get('moderator_comment', '').strip()
        if moderator_comment:
            booking.moderator_comment = moderator_comment

        booking.status = StatusService.get_cancelled_status()
        booking.save()

        messages.success(request, f'Бронирование #{booking.id} отклонено')
        return redirect('booking_detail', pk=pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in reject_booking view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при отклонении бронирования')
        return redirect('booking_detail', pk=pk)


@login_required
def manage_bookings(request: HttpRequest) -> HttpResponse:
    """
    Панель управления бронированиями для администраторов и модераторов.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка страницы управления бронированиями

    Template:
        bookings/manage.html

    Context:
        - bookings: Пагинированный список бронирований
        - status_filter: Текущий фильтр по статусу
        - pending_only: Флаг отображения только ожидающих бронирований
        - status_stats: Статистика бронирований по статусам
        - pending_count: Количество ожидающих бронирований
        - confirmed_count: Количество подтвержденных бронирований
        - completed_count: Количество завершенных бронирований
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для управления бронированиями')
            return redirect('dashboard')

        bookings = Booking.objects.select_related(
            'space', 'space__city', 'space__category',
            'status', 'period', 'tenant'
        ).prefetch_related('space__images').order_by('-created_at')

        status_filter: str = request.GET.get('status', '')
        if status_filter:
            bookings = bookings.filter(status__code=status_filter)

        pending_only: bool = request.GET.get('pending') == '1'
        if pending_only:
            bookings = bookings.filter(status__code=StatusCodes.PENDING)

        from django.db.models import Count
        status_stats = Booking.objects.values(
            'status__code', 'status__name', 'status__color'
        ).annotate(count=Count('id'))

        pending_count: int = Booking.objects.filter(status__code=StatusCodes.PENDING).count()
        confirmed_count: int = Booking.objects.filter(status__code=StatusCodes.CONFIRMED).count()
        completed_count: int = Booking.objects.filter(status__code=StatusCodes.COMPLETED).count()

        bookings_page, paginator = paginate(bookings, request, BOOKINGS_PER_PAGE)

        context: dict[str, Any] = {
            'bookings': bookings_page,
            'status_filter': status_filter,
            'pending_only': pending_only,
            'status_stats': status_stats,
            'pending_count': pending_count,
            'confirmed_count': confirmed_count,
            'completed_count': completed_count,
        }
        return render(request, 'bookings/manage.html', context)

    except Exception as e:
        logger.error(f"Error in manage_bookings view: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке бронирований')
        return redirect('dashboard')


@login_required
@require_POST
def cancel_booking(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Отмена бронирования пользователем.

    Проверяет возможность отмены и предупреждает о возможных санкциях
    при поздней отмене (менее 24 часов до начала).

    Args:
        request (HttpRequest): Объект HTTP запроса
        pk (int): ID бронирования для отмены

    Returns:
        HttpResponse: Редирект на список бронирований пользователя
    """
    try:
        booking: Booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

        if not booking.is_cancellable:
            messages.error(request, 'Это бронирование нельзя отменить')
            return redirect('booking_detail', pk=pk)

        hours_until_start: float = (
            booking.start_datetime - timezone.now()
        ).total_seconds() / SECONDS_IN_HOUR

        refund_message = ''
        if booking.prepayment_paid:
            from ..services.payment_service import PaymentService

            refund_result = PaymentService.process_cancellation_refund(booking)

            if refund_result.get('refunded'):
                refund_message = f' Возврат {refund_result["amount"]} ₽ оформлен.'
            elif refund_result.get('has_penalty'):
                refund_message = f' Предоплата {refund_result["penalty_amount"]} ₽ удержана (отмена менее чем за 24 часа).'

        if hours_until_start < HOURS_IN_DAY and not refund_message:
            messages.warning(
                request,
                'Внимание: отмена менее чем за 24 часа до начала '
                'может повлечь штрафные санкции.'
            )

        booking.status = StatusService.get_cancelled_status()
        booking.save()

        messages.success(request, f'Бронирование #{booking.id} отменено.{refund_message}')
        return redirect('my_bookings')

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in cancel_booking view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при отмене бронирования')
        return redirect('my_bookings')


@login_required
def get_price_for_period(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint для получения цены за период.
    """
    try:
        space_id = request.GET.get('space_id')
        period_id = request.GET.get('period_id')
        periods_count = request.GET.get('periods_count', 1)

        if not space_id or not period_id:
            return JsonResponse({'success': False, 'error': 'Не указаны параметры'})

        try:
            periods_count = int(periods_count)
            if periods_count < 1:
                periods_count = 1
        except (ValueError, TypeError):
            periods_count = 1

        try:
            price_obj = SpacePrice.objects.select_related('period').get(
                space_id=space_id,
                period_id=period_id,
                is_active=True
            )

            total = price_obj.price * periods_count
            total_hours = price_obj.period.hours_count * periods_count

            return JsonResponse({
                'success': True,
                'price_per_period': float(price_obj.price),
                'total': float(total),
                'hours': total_hours,
                'period_name': price_obj.period.description,
            })

        except SpacePrice.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Цена не найдена'})

    except Exception as e:
        logger.error(f"Error in get_price_for_period: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Ошибка сервера'})
