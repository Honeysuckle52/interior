"""
====================================================================
СЕРВИС ОПЛАТЫ ЧЕРЕЗ ЮKASSA ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Интеграция с платежной системой ЮKassa для обработки предоплаты
бронирований (10% от суммы).

Основные функции:
- Создание платежа через API ЮKassa
- Обработка webhook уведомлений
- Проверка статуса платежа
- Отправка квитанций на email

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
            description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать платеж в ЮKassa.

        Args:
            booking: Объект бронирования
            return_url: URL для возврата после оплаты
            description: Описание платежа

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
                "capture": True,  # Автоматическое списание
                "description": description[:128],  # Макс. 128 символов
                "metadata": {
                    "booking_id": booking.id,
                    "user_id": booking.tenant.id,
                    "prepayment_percent": str(PREPAYMENT_PERCENT)
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

            logger.info(f"Payment created: {payment.id} for booking #{booking.id}")

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
                'metadata': payment.metadata
            }

        except Exception as e:
            logger.error(f"Failed to check payment status {payment_id}: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def process_webhook(cls, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать webhook уведомление от ЮKassa.

        Args:
            event_data: Данные события от ЮKassa

        Returns:
            dict: Результат обработки
        """
        try:
            event_type = event_data.get('event')
            payment_object = event_data.get('object', {})
            payment_id = payment_object.get('id')
            status = payment_object.get('status')
            metadata = payment_object.get('metadata', {})

            booking_id = metadata.get('booking_id')

            if not booking_id:
                logger.warning(f"Webhook without booking_id: {payment_id}")
                return {'success': False, 'error': 'No booking_id in metadata'}

            from ..models import Booking, Transaction, TransactionStatus

            try:
                booking = Booking.objects.get(id=booking_id)
            except Booking.DoesNotExist:
                logger.error(f"Booking not found: {booking_id}")
                return {'success': False, 'error': 'Booking not found'}

            # Обработка успешного платежа
            if event_type == 'payment.succeeded' and status == PaymentStatus.SUCCEEDED:
                amount = Decimal(payment_object.get('amount', {}).get('value', '0'))

                # Создаем транзакцию
                success_status, _ = TransactionStatus.objects.get_or_create(
                    code='success',
                    defaults={'name': 'Успешно'}
                )

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
                    booking.save()

                    # Отправляем квитанцию
                    cls.send_payment_receipt(booking, amount)

                    logger.info(f"Payment succeeded for booking #{booking_id}")

                return {'success': True, 'action': 'payment_confirmed'}

            # Обработка отмены платежа
            elif event_type == 'payment.canceled':
                logger.info(f"Payment canceled for booking #{booking_id}")
                return {'success': True, 'action': 'payment_canceled'}

            return {'success': True, 'action': 'no_action_needed'}

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {'success': False, 'error': str(e)}

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
    def is_configured(cls) -> bool:
        """Проверить, настроена ли платежная система."""
        shop_id = getattr(settings, 'YOOKASSA_SHOP_ID', None)
        secret_key = getattr(settings, 'YOOKASSA_SECRET_KEY', None)
        return bool(shop_id and secret_key)
