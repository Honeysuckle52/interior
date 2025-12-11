"""
====================================================================
СЕРВИС ОПЛАТЫ ЧЕРЕЗ ЮKASSA ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Интеграция с платежной системой ЮKassa для обработки предоплаты
бронирований (10% от суммы).

Основные функции:
- Создание платежа через API ЮKassa
- Обработка webhook уведомлений (все события)
- Проверка статуса платежа
- Подтверждение/отмена холдированных платежей
- Возврат средств
- Отправка квитанций на email

Поддерживаемые webhook события:
- payment.waiting_for_capture - Платеж требует подтверждения
- payment.succeeded - Успешный платёж
- payment.canceled - Отмена платежа
- refund.succeeded - Успешный возврат

Особенности:
- Предоплата 10% от суммы бронирования
- Предоплата сгорает при отмене менее чем за 24 часа
- Квитанция отправляется на email пользователя
====================================================================
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Dict, Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

if TYPE_CHECKING:
    from ..models import Booking, Transaction

logger = logging.getLogger(__name__)

# Константы
PREPAYMENT_PERCENT = Decimal('10')  # 10% предоплаты
CANCELLATION_HOURS = 24  # Часов до начала для бесплатной отмены


class PaymentStatus:
    """Статусы платежа ЮKassa."""
    PENDING = 'pending'
    WAITING_FOR_CAPTURE = 'waiting_for_capture'
    SUCCEEDED = 'succeeded'
    CANCELED = 'canceled'


class RefundStatus:
    """Статусы возврата ЮKassa."""
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    CANCELED = 'canceled'


class WebhookEvent:
    """Типы событий webhook от ЮKassa."""
    PAYMENT_WAITING_FOR_CAPTURE = 'payment.waiting_for_capture'
    PAYMENT_SUCCEEDED = 'payment.succeeded'
    PAYMENT_CANCELED = 'payment.canceled'
    REFUND_SUCCEEDED = 'refund.succeeded'


class PaymentService:
    """
    Сервис для работы с платежами через ЮKassa.

    Требует установки переменных окружения:
    - YOOKASSA_SHOP_ID: ID магазина в ЮKassa
    - YOOKASSA_SECRET_KEY: Секретный ключ API
    """

    _shop_id: Optional[str] = None
    _secret_key: Optional[str] = None
    _initialized: bool = False

    @classmethod
    def _initialize(cls) -> bool:
        """
        Инициализация SDK ЮKassa.

        Returns:
            bool: True если инициализация успешна
        """
        if cls._initialized:
            return True

        cls._shop_id = getattr(settings, 'YOOKASSA_SHOP_ID', None)
        cls._secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', None)

        if not cls._shop_id or not cls._secret_key:
            logger.warning("ЮKassa credentials not configured")
            return False

        try:
            from yookassa import Configuration
            Configuration.account_id = cls._shop_id
            Configuration.secret_key = cls._secret_key
            cls._initialized = True
            logger.info("ЮKassa SDK initialized successfully")
            return True
        except ImportError:
            logger.error("yookassa package not installed. Run: pip install yookassa")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize ЮKassa: {e}")
            return False

    @classmethod
    def calculate_prepayment(cls, total_amount: Decimal) -> Decimal:
        """
        Рассчитать сумму предоплаты (10% от общей суммы).

        Args:
            total_amount: Общая сумма бронирования

        Returns:
            Decimal: Сумма предоплаты
        """
        prepayment = (total_amount * PREPAYMENT_PERCENT / Decimal('100')).quantize(Decimal('0.01'))
        # Минимальная сумма платежа в ЮKassa - 1 рубль
        return max(prepayment, Decimal('1.00'))

    @classmethod
    def create_payment(
        cls,
        booking: 'Booking',
        return_url: str,
        description: Optional[str] = None,
        capture: bool = True  # Добавлен параметр capture для двухстадийной оплаты
    ) -> Dict[str, Any]:
        """
        Создать платеж в ЮKassa.

        Args:
            booking: Объект бронирования
            return_url: URL для возврата после оплаты
            description: Описание платежа
            capture: True для автоматического списания, False для холдирования

        Returns:
            dict: Информация о платеже с ключами:
                - success: bool
                - payment_id: str (ID платежа в ЮKassa)
                - confirmation_url: str (URL для оплаты)
                - error: str (при ошибке)
        """
        if not cls._initialize():
            return {
                'success': False,
                'error': 'Платежная система не настроена. Обратитесь к администратору.'
            }

        try:
            from yookassa import Payment

            prepayment_amount = cls.calculate_prepayment(booking.total_amount)
            idempotence_key = str(uuid.uuid4())

            if not description:
                description = f"Предоплата 10% за бронирование #{booking.id} - {booking.space.title}"

            # Создаем платеж
            payment = Payment.create({
                "amount": {
                    "value": str(prepayment_amount),
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": capture,  # Автоматическое списание или холдирование
                "description": description[:128],  # Макс. 128 символов
                "metadata": {
                    "booking_id": booking.id,
                    "user_id": booking.tenant.id,
                    "user_email": booking.tenant.email,
                    "prepayment_percent": str(PREPAYMENT_PERCENT),
                    "space_title": booking.space.title[:64]
                },
                "receipt": {
                    "customer": {
                        "email": booking.tenant.email
                    },
                    "items": [
                        {
                            "description": f"Предоплата за аренду: {booking.space.title[:64]}",
                            "quantity": "1.00",
                            "amount": {
                                "value": str(prepayment_amount),
                                "currency": "RUB"
                            },
                            "vat_code": 1,  # НДС не облагается
                            "payment_mode": "full_prepayment",
                            "payment_subject": "service"
                        }
                    ]
                }
            }, idempotence_key)

            logger.info(f"Payment created: {payment.id} for booking #{booking.id}, capture={capture}")

            return {
                'success': True,
                'payment_id': payment.id,
                'confirmation_url': payment.confirmation.confirmation_url,
                'amount': prepayment_amount
            }

        except Exception as e:
            logger.error(f"Failed to create payment for booking #{booking.id}: {e}")
            return {
                'success': False,
                'error': f'Ошибка создания платежа: {str(e)}'
            }

    @classmethod
    def capture_payment(cls, payment_id: str, amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Подтвердить холдированный платеж (списать средства).

        Используется когда платеж в статусе waiting_for_capture.

        Args:
            payment_id: ID платежа в ЮKassa
            amount: Сумма для списания (если None - списывается вся сумма)

        Returns:
            dict: Результат операции
        """
        if not cls._initialize():
            return {'success': False, 'error': 'Платежная система не настроена'}

        try:
            from yookassa import Payment

            idempotence_key = str(uuid.uuid4())

            capture_data = {}
            if amount is not None:
                capture_data["amount"] = {
                    "value": str(amount),
                    "currency": "RUB"
                }

            payment = Payment.capture(payment_id, capture_data, idempotence_key)

            logger.info(f"Payment captured: {payment_id}, status: {payment.status}")

            return {
                'success': True,
                'status': payment.status,
                'amount': Decimal(payment.amount.value)
            }

        except Exception as e:
            logger.error(f"Failed to capture payment {payment_id}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def cancel_payment(cls, payment_id: str) -> Dict[str, Any]:
        """
        Отменить холдированный платеж.

        Используется когда платеж в статусе waiting_for_capture и нужно его отменить.

        Args:
            payment_id: ID платежа в ЮKassa

        Returns:
            dict: Результат операции
        """
        if not cls._initialize():
            return {'success': False, 'error': 'Платежная система не настроена'}

        try:
            from yookassa import Payment

            idempotence_key = str(uuid.uuid4())
            payment = Payment.cancel(payment_id, idempotence_key)

            logger.info(f"Payment canceled: {payment_id}, status: {payment.status}")

            return {
                'success': True,
                'status': payment.status
            }

        except Exception as e:
            logger.error(f"Failed to cancel payment {payment_id}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def create_refund(
        cls,
        payment_id: str,
        amount: Decimal,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать возврат средств.

        Args:
            payment_id: ID оригинального платежа
            amount: Сумма возврата
            description: Описание причины возврата

        Returns:
            dict: Результат операции с refund_id
        """
        if not cls._initialize():
            return {'success': False, 'error': 'Платежная система не настроена'}

        try:
            from yookassa import Refund

            idempotence_key = str(uuid.uuid4())

            refund_data = {
                "payment_id": payment_id,
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                }
            }

            if description:
                refund_data["description"] = description[:250]

            refund = Refund.create(refund_data, idempotence_key)

            logger.info(f"Refund created: {refund.id} for payment {payment_id}, amount: {amount}")

            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': Decimal(refund.amount.value)
            }

        except Exception as e:
            logger.error(f"Failed to create refund for payment {payment_id}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def check_payment_status(cls, payment_id: str) -> Dict[str, Any]:
        """
        Проверить статус платежа.

        Args:
            payment_id: ID платежа в ЮKassa

        Returns:
            dict: Статус платежа с ключами:
                - success: bool
                - status: str (статус платежа)
                - paid: bool (оплачен ли)
                - amount: Decimal (сумма)
                - error: str (при ошибке)
        """
        if not cls._initialize():
            return {'success': False, 'error': 'Платежная система не настроена'}

        try:
            from yookassa import Payment

            payment = Payment.find_one(payment_id)

            return {
                'success': True,
                'status': payment.status,
                'paid': payment.paid,
                'amount': Decimal(payment.amount.value),
                'metadata': payment.metadata,
                'captured_at': payment.captured_at,
                'created_at': payment.created_at
            }

        except Exception as e:
            logger.error(f"Failed to check payment status {payment_id}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def process_webhook(cls, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать webhook уведомление от ЮKassa.

        Поддерживаемые события:
        - payment.waiting_for_capture - Платеж требует подтверждения
        - payment.succeeded - Успешный платёж
        - payment.canceled - Отмена платежа
        - refund.succeeded - Успешный возврат

        Args:
            event_data: Данные события от ЮKassa

        Returns:
            dict: Результат обработки
        """
        try:
            event_type = event_data.get('event')
            payment_object = event_data.get('object', {})

            logger.info(f"Processing webhook event: {event_type}")

            # Роутинг по типу события
            if event_type == WebhookEvent.PAYMENT_WAITING_FOR_CAPTURE:
                return cls._handle_payment_waiting_for_capture(payment_object)

            elif event_type == WebhookEvent.PAYMENT_SUCCEEDED:
                return cls._handle_payment_succeeded(payment_object)

            elif event_type == WebhookEvent.PAYMENT_CANCELED:
                return cls._handle_payment_canceled(payment_object)

            elif event_type == WebhookEvent.REFUND_SUCCEEDED:
                return cls._handle_refund_succeeded(payment_object)

            else:
                logger.warning(f"Unknown webhook event type: {event_type}")
                return {'success': True, 'action': 'unknown_event_ignored'}

        except Exception as e:
            logger.error(f"Webhook processing error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @classmethod
    def _handle_payment_waiting_for_capture(cls, payment_object: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать событие payment.waiting_for_capture.

        Платеж поступил и ожидает подтверждения (capture).
        В нашем случае мы автоматически подтверждаем платеж.

        Args:
            payment_object: Объект платежа из webhook

        Returns:
            dict: Результат обработки
        """
        payment_id = payment_object.get('id')
        metadata = payment_object.get('metadata', {})
        booking_id = metadata.get('booking_id')
        amount = Decimal(payment_object.get('amount', {}).get('value', '0'))

        logger.info(f"Payment waiting for capture: {payment_id}, booking #{booking_id}, amount: {amount}")

        if not booking_id:
            logger.warning(f"Payment {payment_id} has no booking_id in metadata")
            return {'success': False, 'error': 'No booking_id in metadata'}

        from ..models import Booking

        try:
            booking = Booking.objects.select_related('tenant', 'space', 'status').get(id=booking_id)
        except Booking.DoesNotExist:
            logger.error(f"Booking not found: {booking_id}")
            return {'success': False, 'error': 'Booking not found'}

        # Автоматически подтверждаем платеж
        capture_result = cls.capture_payment(payment_id)

        if capture_result['success']:
            logger.info(f"Payment {payment_id} captured automatically for booking #{booking_id}")

            # Отправляем уведомление модератору о поступившем платеже
            cls._send_moderator_notification(
                booking,
                'Поступил платеж',
                f'Платеж на сумму {amount} ₽ был подтвержден автоматически.'
            )

            return {'success': True, 'action': 'payment_captured'}
        else:
            logger.error(f"Failed to capture payment {payment_id}: {capture_result.get('error')}")
            return {'success': False, 'error': capture_result.get('error')}

    @classmethod
    def _handle_payment_succeeded(cls, payment_object: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать событие payment.succeeded (успешный платёж).

        Args:
            payment_object: Объект платежа из webhook

        Returns:
            dict: Результат обработки
        """
        payment_id = payment_object.get('id')
        status = payment_object.get('status')
        metadata = payment_object.get('metadata', {})
        booking_id = metadata.get('booking_id')
        amount = Decimal(payment_object.get('amount', {}).get('value', '0'))

        logger.info(f"Payment succeeded: {payment_id}, booking #{booking_id}, amount: {amount}")

        if not booking_id:
            logger.warning(f"Payment {payment_id} succeeded but has no booking_id")
            return {'success': False, 'error': 'No booking_id in metadata'}

        from ..models import Booking, Transaction, TransactionStatus

        try:
            booking = Booking.objects.select_related('tenant', 'space', 'status').get(id=booking_id)
        except Booking.DoesNotExist:
            logger.error(f"Booking not found: {booking_id}")
            return {'success': False, 'error': 'Booking not found'}

        # Получаем или создаем статус транзакции
        success_status, _ = TransactionStatus.objects.get_or_create(
            code='success',
            defaults={'name': 'Успешно'}
        )

        # Создаем транзакцию (если еще не существует)
        transaction, created = Transaction.objects.get_or_create(
            external_id=payment_id,
            defaults={
                'booking': booking,
                'status': success_status,
                'amount': amount,
                'payment_method': 'yookassa'
            }
        )

        if created:
            # Обновляем бронирование
            booking.prepayment_paid = True
            booking.prepayment_amount = amount
            booking.payment_id = payment_id
            booking.prepayment_paid_at = timezone.now()
            booking.save(update_fields=[
                'prepayment_paid', 'prepayment_amount',
                'payment_id', 'prepayment_paid_at'
            ])

            # Отправляем квитанцию на email
            cls.send_payment_receipt(booking, amount)

            # Отправляем уведомление модератору
            cls._send_moderator_notification(
                booking,
                'Предоплата получена',
                f'Пользователь {booking.tenant.get_full_name_or_username} '
                f'оплатил предоплату {amount} ₽ за бронирование #{booking.id}.'
            )

            logger.info(f"Payment succeeded, booking #{booking_id} updated, receipt sent")
        else:
            logger.info(f"Payment {payment_id} already processed (transaction exists)")

        return {'success': True, 'action': 'payment_confirmed', 'created': created}

    @classmethod
    def _handle_payment_canceled(cls, payment_object: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать событие payment.canceled (отмена платежа).

        Args:
            payment_object: Объект платежа из webhook

        Returns:
            dict: Результат обработки
        """
        payment_id = payment_object.get('id')
        metadata = payment_object.get('metadata', {})
        booking_id = metadata.get('booking_id')
        cancellation_details = payment_object.get('cancellation_details', {})
        reason = cancellation_details.get('reason', 'unknown')
        party = cancellation_details.get('party', 'unknown')

        logger.info(f"Payment canceled: {payment_id}, booking #{booking_id}, reason: {reason}, party: {party}")

        if not booking_id:
            return {'success': True, 'action': 'payment_canceled_no_booking'}

        from ..models import Booking, Transaction, TransactionStatus

        try:
            booking = Booking.objects.select_related('tenant', 'space').get(id=booking_id)
        except Booking.DoesNotExist:
            logger.warning(f"Booking not found for canceled payment: {booking_id}")
            return {'success': True, 'action': 'payment_canceled_booking_not_found'}

        # Создаем транзакцию с отменой
        canceled_status, _ = TransactionStatus.objects.get_or_create(
            code='canceled',
            defaults={'name': 'Отменен'}
        )

        Transaction.objects.get_or_create(
            external_id=payment_id,
            defaults={
                'booking': booking,
                'status': canceled_status,
                'amount': Decimal(payment_object.get('amount', {}).get('value', '0')),
                'payment_method': 'yookassa'
            }
        )

        # Очищаем payment_id если платеж отменен
        if booking.payment_id == payment_id and not booking.prepayment_paid:
            booking.payment_id = ''
            booking.save(update_fields=['payment_id'])

        # Отправляем уведомление пользователю
        cls._send_payment_canceled_notification(booking, reason)

        return {'success': True, 'action': 'payment_canceled', 'reason': reason}

    @classmethod
    def _handle_refund_succeeded(cls, refund_object: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать событие refund.succeeded (успешный возврат).

        Args:
            refund_object: Объект возврата из webhook

        Returns:
            dict: Результат обработки
        """
        refund_id = refund_object.get('id')
        payment_id = refund_object.get('payment_id')
        amount = Decimal(refund_object.get('amount', {}).get('value', '0'))

        logger.info(f"Refund succeeded: {refund_id}, payment: {payment_id}, amount: {amount}")

        from ..models import Booking, Transaction, TransactionStatus

        # Ищем бронирование по payment_id
        try:
            booking = Booking.objects.select_related('tenant', 'space').get(payment_id=payment_id)
        except Booking.DoesNotExist:
            logger.warning(f"Booking not found for refund payment: {payment_id}")
            return {'success': True, 'action': 'refund_succeeded_booking_not_found'}

        # Создаем транзакцию возврата
        refund_status, _ = TransactionStatus.objects.get_or_create(
            code='refunded',
            defaults={'name': 'Возвращен'}
        )

        transaction, created = Transaction.objects.get_or_create(
            external_id=refund_id,
            defaults={
                'booking': booking,
                'status': refund_status,
                'amount': -amount,  # Отрицательная сумма для возврата
                'payment_method': 'yookassa_refund'
            }
        )

        if created:
            # Обновляем статус предоплаты в бронировании
            booking.prepayment_paid = False
            booking.prepayment_amount = Decimal('0')
            booking.save(update_fields=['prepayment_paid', 'prepayment_amount'])

            # Отправляем уведомление пользователю о возврате
            cls.send_refund_receipt(booking, amount)

            logger.info(f"Refund processed for booking #{booking.id}")

        return {'success': True, 'action': 'refund_processed', 'created': created}

    @classmethod
    def send_payment_receipt(cls, booking: 'Booking', amount: Decimal) -> bool:
        """
        Отправить квитанцию об оплате на email пользователя.

        Args:
            booking: Объект бронирования
            amount: Сумма оплаты

        Returns:
            bool: True если отправка успешна
        """
        try:
            subject = f'Квитанция об оплате - Бронирование #{booking.id} | INTERIOR'

            context = {
                'booking': booking,
                'amount': amount,
                'prepayment_percent': PREPAYMENT_PERCENT,
                'remaining_amount': booking.total_amount - amount,
                'site_name': 'INTERIOR',
                'year': timezone.now().year,
            }

            html_content = render_to_string('emails/payment_receipt.html', context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[booking.tenant.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Payment receipt sent to {booking.tenant.email} for booking #{booking.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send payment receipt: {e}")
            return False

    @classmethod
    def send_refund_receipt(cls, booking: 'Booking', amount: Decimal) -> bool:
        """
        Отправить уведомление о возврате средств на email пользователя.

        Args:
            booking: Объект бронирования
            amount: Сумма возврата

        Returns:
            bool: True если отправка успешна
        """
        try:
            subject = f'Возврат средств - Бронирование #{booking.id} | INTERIOR'

            context = {
                'booking': booking,
                'amount': amount,
                'site_name': 'INTERIOR',
                'year': timezone.now().year,
            }

            html_content = render_to_string('emails/refund_receipt.html', context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[booking.tenant.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Refund receipt sent to {booking.tenant.email} for booking #{booking.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send refund receipt: {e}")
            return False

    @classmethod
    def _send_payment_canceled_notification(cls, booking: 'Booking', reason: str) -> bool:
        """
        Отправить уведомление об отмене платежа.

        Args:
            booking: Объект бронирования
            reason: Причина отмены

        Returns:
            bool: True если отправка успешна
        """
        try:
            # Расшифровка причин отмены ЮKassa
            reason_messages = {
                '3d_secure_failed': 'Не пройдена аутентификация 3-D Secure',
                'call_issuer': 'Оплата отклонена банком',
                'canceled_by_merchant': 'Платеж отменен магазином',
                'card_expired': 'Истек срок действия карты',
                'country_forbidden': 'Оплата из данной страны запрещена',
                'expired_on_capture': 'Истек срок подтверждения платежа',
                'expired_on_confirmation': 'Истек срок оплаты',
                'fraud_suspected': 'Подозрение на мошенничество',
                'general_decline': 'Платеж отклонен',
                'identification_required': 'Требуется идентификация',
                'insufficient_funds': 'Недостаточно средств',
                'internal_timeout': 'Технический сбой',
                'invalid_card_number': 'Неверный номер карты',
                'invalid_csc': 'Неверный код CVV/CVC',
                'issuer_unavailable': 'Банк недоступен',
                'payment_method_limit_exceeded': 'Превышен лимит платежей',
                'payment_method_restricted': 'Способ оплаты заблокирован',
                'permission_revoked': 'Разрешение на оплату отозвано',
            }

            reason_text = reason_messages.get(reason, f'Причина: {reason}')

            subject = f'Платеж отменен - Бронирование #{booking.id} | INTERIOR'

            context = {
                'booking': booking,
                'reason': reason_text,
                'site_name': 'INTERIOR',
                'year': timezone.now().year,
            }

            html_content = render_to_string('emails/payment_canceled.html', context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[booking.tenant.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Payment canceled notification sent to {booking.tenant.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send payment canceled notification: {e}")
            return False

    @classmethod
    def _send_moderator_notification(cls, booking: 'Booking', subject_suffix: str, message: str) -> bool:
        """
        Отправить уведомление модераторам о событии оплаты.

        Args:
            booking: Объект бронирования
            subject_suffix: Дополнение к теме письма
            message: Текст сообщения

        Returns:
            bool: True если отправка успешна
        """
        try:
            from ..models import CustomUser

            # Получаем email всех модераторов и администраторов
            moderator_emails = list(
                CustomUser.objects.filter(
                    is_active=True,
                    role__in=['admin', 'moderator']
                ).values_list('email', flat=True)
            )

            if not moderator_emails:
                logger.warning("No moderators found to send notification")
                return False

            subject = f'{subject_suffix} - Бронирование #{booking.id} | INTERIOR'

            context = {
                'booking': booking,
                'message': message,
                'site_name': 'INTERIOR',
                'year': timezone.now().year,
            }

            html_content = render_to_string('emails/moderator_notification.html', context)
            text_content = strip_tags(html_content)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=moderator_emails
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)

            logger.info(f"Moderator notification sent to {len(moderator_emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send moderator notification: {e}")
            return False

    @classmethod
    def check_cancellation_penalty(cls, booking: 'Booking') -> Dict[str, Any]:
        """
        Проверить, будет ли удержана предоплата при отмене.

        Args:
            booking: Объект бронирования

        Returns:
            dict: Информация о штрафе
                - has_penalty: bool (будет ли штраф)
                - penalty_amount: Decimal (сумма штрафа)
                - hours_until_start: float (часов до начала)
                - message: str (сообщение для пользователя)
        """
        now = timezone.now()
        hours_until_start = (booking.start_datetime - now).total_seconds() / 3600

        if not booking.prepayment_paid:
            return {
                'has_penalty': False,
                'penalty_amount': Decimal('0'),
                'hours_until_start': hours_until_start,
                'message': 'Предоплата не была внесена.'
            }

        if hours_until_start < CANCELLATION_HOURS:
            return {
                'has_penalty': True,
                'penalty_amount': booking.prepayment_amount or Decimal('0'),
                'hours_until_start': hours_until_start,
                'message': f'При отмене менее чем за {CANCELLATION_HOURS} часов '
                          f'предоплата {booking.prepayment_amount} ₽ не возвращается.'
            }

        return {
            'has_penalty': False,
            'penalty_amount': Decimal('0'),
            'hours_until_start': hours_until_start,
            'message': f'При отмене более чем за {CANCELLATION_HOURS} часов '
                      f'предоплата будет возвращена.'
        }

    @classmethod
    def process_cancellation_refund(cls, booking: 'Booking') -> Dict[str, Any]:
        """
        Обработать возврат предоплаты при отмене бронирования.

        Возвращает предоплату если отмена более чем за 24 часа до начала.

        Args:
            booking: Объект бронирования

        Returns:
            dict: Результат операции
        """
        penalty_info = cls.check_cancellation_penalty(booking)

        if not booking.prepayment_paid:
            return {
                'success': True,
                'refunded': False,
                'message': 'Предоплата не была внесена'
            }

        if penalty_info['has_penalty']:
            return {
                'success': True,
                'refunded': False,
                'penalty_amount': penalty_info['penalty_amount'],
                'message': penalty_info['message']
            }

        # Создаем возврат
        refund_result = cls.create_refund(
            payment_id=booking.payment_id,
            amount=booking.prepayment_amount,
            description=f'Возврат предоплаты за отмену бронирования #{booking.id}'
        )

        if refund_result['success']:
            return {
                'success': True,
                'refunded': True,
                'refund_id': refund_result['refund_id'],
                'amount': refund_result['amount'],
                'message': f'Возврат {booking.prepayment_amount} ₽ оформлен'
            }
        else:
            return {
                'success': False,
                'refunded': False,
                'error': refund_result.get('error'),
                'message': 'Ошибка оформления возврата'
            }

    @classmethod
    def process_admin_refund(cls, booking: 'Booking') -> Dict[str, Any]:
        """
        Обработать возврат предоплаты при отклонении бронирования администратором.

        При отклонении администратором/модератором всегда возвращается полная сумма
        предоплаты без штрафных санкций, так как отмена происходит не по вине клиента.

        Args:
            booking: Бронирование с предоплатой

        Returns:
            dict: Результат операции с ключами:
                - refunded (bool): Успешен ли возврат
                - amount (Decimal): Сумма возврата
                - refund_id (str): ID возврата в ЮKassa
                - message (str): Сообщение о результате
                - error (str): Описание ошибки (при неудаче)
        """
        if not booking.prepayment_paid or not booking.prepayment_amount:
            return {
                'success': False,
                'refunded': False,
                'message': 'Предоплата не была внесена'
            }

        # payment_id хранится в booking.payment_id при успешной оплате
        payment_id = booking.payment_id

        # Если payment_id пустой, пробуем найти в транзакциях
        if not payment_id:
            # Ищем успешную транзакцию (статус 'success', не 'succeeded')
            successful_transaction = booking.transactions.filter(
                status__code='success'
            ).order_by('-created_at').first()

            if successful_transaction and successful_transaction.external_id:
                payment_id = successful_transaction.external_id

        if not payment_id:
            return {
                'success': False,
                'refunded': False,
                'error': 'Не найден платеж для возврата',
                'message': 'Ошибка: платеж не найден'
            }

        # Создаем возврат полной суммы предоплаты
        refund_result = cls.create_refund(
            payment_id=payment_id,
            amount=booking.prepayment_amount,
            description=f'Возврат предоплаты - бронирование #{booking.id} отклонено администратором'
        )

        if refund_result['success']:
            from ..models import Transaction, TransactionStatus
            refund_status, _ = TransactionStatus.objects.get_or_create(
                code='refunded',
                defaults={'name': 'Возврат'}
            )
            Transaction.objects.create(
                booking=booking,
                status=refund_status,
                amount=booking.prepayment_amount,
                payment_method='yookassa',
                external_id=refund_result.get('refund_id', '')
            )

            # Обновляем статус предоплаты в бронировании
            booking.prepayment_paid = False
            booking.save(update_fields=['prepayment_paid'])

            # Отправляем квитанцию о возврате
            cls.send_refund_receipt(booking, booking.prepayment_amount)

            return {
                'success': True,
                'refunded': True,
                'refund_id': refund_result['refund_id'],
                'amount': refund_result['amount'],
                'message': f'Возврат {booking.prepayment_amount} ₽ оформлен'
            }
        else:
            return {
                'success': False,
                'refunded': False,
                'error': refund_result.get('error'),
                'message': 'Ошибка оформления возврата'
            }

    @classmethod
    def is_configured(cls) -> bool:
        """Проверить, настроена ли платежная система."""
        shop_id = getattr(settings, 'YOOKASSA_SHOP_ID', None)
        secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', None)
        return bool(shop_id and secret_key)
