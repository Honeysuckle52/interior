"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ ОПЛАТЫ ЧЕРЕЗ ЮKASSA
====================================================================
Обработка платежей, webhook уведомлений и возврата после оплаты.
====================================================================
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from ..models import Booking
from ..services.payment_service import PaymentService
from ..services.status_service import StatusCodes

logger = logging.getLogger(__name__)


@login_required
@require_POST
def initiate_payment(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Инициировать платеж предоплаты для бронирования.

    Args:
        request: HTTP запрос
        pk: ID бронирования

    Returns:
        Редирект на страницу оплаты ЮKassa или обратно с ошибкой
    """
    booking = get_object_or_404(
        Booking.objects.select_related('space', 'tenant', 'status'),
        pk=pk,
        tenant=request.user
    )

    # Проверяем, что бронирование в нужном статусе
    if booking.status.code not in [StatusCodes.PENDING, StatusCodes.CONFIRMED]:
        messages.error(request, 'Оплата недоступна для этого бронирования')
        return redirect('booking_detail', pk=pk)

    # Проверяем, не оплачено ли уже
    if booking.prepayment_paid:
        messages.info(request, 'Предоплата уже внесена')
        return redirect('booking_detail', pk=pk)

    # Проверяем настройку ЮKassa
    if not PaymentService.is_configured():
        messages.error(request, 'Платежная система временно недоступна')
        return redirect('booking_detail', pk=pk)

    # Формируем URL возврата
    return_url = request.build_absolute_uri(f'/payments/{pk}/return/')

    # Создаем платеж
    result = PaymentService.create_payment(booking, return_url)

    if result['success']:
        # Сохраняем ID платежа
        booking.payment_id = result['payment_id']
        booking.save(update_fields=['payment_id'])

        # Редирект на страницу оплаты ЮKassa
        return redirect(result['confirmation_url'])
    else:
        messages.error(request, result.get('error', 'Ошибка создания платежа'))
        return redirect('booking_detail', pk=pk)


@login_required
@require_GET
def payment_return(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Страница возврата после оплаты.

    Args:
        request: HTTP запрос
        pk: ID бронирования

    Returns:
        Страница результата оплаты
    """
    booking = get_object_or_404(
        Booking.objects.select_related('space', 'tenant', 'status'),
        pk=pk,
        tenant=request.user
    )

    # Проверяем статус платежа
    if booking.payment_id:
        result = PaymentService.check_payment_status(booking.payment_id)

        if result['success'] and result['paid']:
            # Обновляем данные бронирования если еще не обновлены
            if not booking.prepayment_paid:
                from django.utils import timezone
                booking.prepayment_paid = True
                booking.prepayment_amount = result['amount']
                booking.prepayment_paid_at = timezone.now()
                booking.save()

                # Отправляем квитанцию
                PaymentService.send_payment_receipt(booking, result['amount'])

            messages.success(
                request,
                f'Предоплата {booking.prepayment_amount} ₽ успешно внесена! '
                f'Квитанция отправлена на {booking.tenant.email}'
            )
        elif result['success'] and result['status'] == 'pending':
            messages.info(request, 'Платеж обрабатывается. Статус будет обновлен автоматически.')
        elif result['success'] and result['status'] == 'canceled':
            messages.warning(request, 'Платеж был отменен')
        else:
            messages.warning(request, 'Не удалось проверить статус платежа')

    return redirect('booking_detail', pk=pk)


@csrf_exempt
@require_POST
def payment_webhook(request: HttpRequest) -> JsonResponse:
    """
    Webhook для уведомлений от ЮKassa.

    Args:
        request: HTTP запрос с данными события

    Returns:
        JsonResponse с результатом обработки
    """
    try:
        # Парсим JSON данные
        event_data = json.loads(request.body)

        logger.info(f"Received webhook: {event_data.get('event')}")

        # Обрабатываем событие
        result = PaymentService.process_webhook(event_data)

        if result['success']:
            return JsonResponse({'status': 'ok'})
        else:
            return JsonResponse({'status': 'error', 'message': result.get('error')}, status=400)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def payment_status(request: HttpRequest, pk: int) -> JsonResponse:
    """
    AJAX endpoint для проверки статуса оплаты.

    Args:
        request: HTTP запрос
        pk: ID бронирования

    Returns:
        JSON с информацией об оплате
    """
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

    data = {
        'prepayment_paid': booking.prepayment_paid,
        'prepayment_amount': float(booking.prepayment_amount) if booking.prepayment_amount else 0,
        'total_amount': float(booking.total_amount),
        'remaining_amount': float(booking.total_amount - (booking.prepayment_amount or 0)),
    }

    # Если есть payment_id, проверяем актуальный статус
    if booking.payment_id and not booking.prepayment_paid:
        result = PaymentService.check_payment_status(booking.payment_id)
        if result['success']:
            data['payment_status'] = result['status']
            data['payment_paid'] = result['paid']

    return JsonResponse(data)


@login_required
def check_cancellation_penalty(request: HttpRequest, pk: int) -> JsonResponse:
    """
    AJAX endpoint для проверки штрафа при отмене.

    Args:
        request: HTTP запрос
        pk: ID бронирования

    Returns:
        JSON с информацией о штрафе
    """
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

    penalty_info = PaymentService.check_cancellation_penalty(booking)

    return JsonResponse({
        'has_penalty': penalty_info['has_penalty'],
        'penalty_amount': float(penalty_info['penalty_amount']),
        'hours_until_start': penalty_info['hours_until_start'],
        'message': penalty_info['message']
    })
