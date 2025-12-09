"""
====================================================================
СЕРВИС EMAIL-УВЕДОМЛЕНИЙ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит функционал для отправки email-уведомлений
через SMTP Mail.ru. Включает отправку писем подтверждения email,
кодов верификации, сброса пароля и других уведомлений.

Основные функции:
- send_email: Базовая функция отправки email с HTML и текстовой версией
- generate_token: Генерация безопасных токенов для ссылок
- send_verification_code: Отправка 6-значного кода подтверждения
- send_verification_email: Отправка письма с ссылкой подтверждения email
- send_password_reset_email: Отправка письма для сброса пароля

Особенности:
- Использование Django шаблонов для HTML-писем
- Автоматическое создание текстовой версии из HTML
- Отладочный вывод в консоль для тестирования
- Поддержка истечения сроков действия токенов
====================================================================
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def generate_token() -> str:
    """
    Генерация безопасного случайного токена.

    Используется для создания уникальных токенов подтверждения
    email и сброса пароля. Токены имеют длину 32 символа
    и используют URL-безопасную кодировку.

    Returns:
        str: Случайный токен длиной 32 символа
    """
    return secrets.token_urlsafe(32)


def send_email(
    subject: str,
    to_email: str,
    template_name: str,
    context: dict,
    from_email: Optional[str] = None
) -> bool:
    """
    Отправка email с HTML и текстовой версией.

    Рендерит HTML-шаблон письма, создает текстовую версию
    и отправляет через SMTP. Логирует результат отправки.

    Args:
        subject (str): Тема письма
        to_email (str): Email получателя
        template_name (str): Имя шаблона без расширения (ищется в templates/emails/)
        context (dict): Контекстные данные для шаблона
        from_email (Optional[str]): Email отправителя (по умолчанию из settings)

    Returns:
        bool: True если отправка успешна, False при ошибке
    """
    try:
        from_email = from_email or settings.DEFAULT_FROM_EMAIL

        # Рендерим HTML версию
        html_content = render_to_string(f'emails/{template_name}.html', context)
        # Создаём текстовую версию
        text_content = strip_tags(html_content)

        # Создаём письмо
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[to_email]
        )
        email.attach_alternative(html_content, 'text/html')

        # Отправляем
        email.send(fail_silently=False)

        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
        return False


def send_verification_code(user, code: str, request) -> bool:
    """
    Отправка кода подтверждения email (6-значный код).

    Используется для быстрой верификации email при регистрации
    или смене email. Код действителен 15 минут.

    Args:
        user: Объект пользователя (CustomUser)
        code (str): 6-значный код подтверждения
        request: Объект HTTP запроса для получения контекста

    Returns:
        bool: True если отправка успешна, False при ошибке
    """
    context = {
        'user': user,
        'code': code,
        'site_name': 'INTERIOR',
        'expires_minutes': 15
    }

    # Отладочный вывод в консоль
    print(f"\n{'='*60}")
    print(f"[EMAIL DEBUG] Verification code for: {user.email}")
    print(f"[EMAIL DEBUG] Code: {code}")
    print(f"{'='*60}\n")

    return send_email(
        subject=f'Код подтверждения: {code} - INTERIOR',
        to_email=user.email,
        template_name='verification_code',
        context=context
    )


def send_verification_email(user, request) -> bool:
    """
    Отправка письма подтверждения email (ссылка).

    Создает уникальный токен подтверждения, действительный 24 часа,
    и отправляет письмо со ссылкой для подтверждения email.

    Args:
        user: Объект пользователя (CustomUser)
        request: Объект HTTP запроса для построения абсолютного URL

    Returns:
        bool: True если отправка успешна, False при ошибке
    """
    from ..models import EmailVerificationToken

    EmailVerificationToken.objects.filter(user=user).delete()

    # Создаём новый токен
    token = generate_token()
    token_obj = EmailVerificationToken.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timedelta(hours=24)
    )

    # Формируем ссылку
    verify_url = request.build_absolute_uri(f'/verify-email/{token_obj.token}/')

    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'INTERIOR',
        'expires_hours': 24
    }

    print(f"\n{'='*60}")
    print(f"[EMAIL DEBUG] Verification email for: {user.email}")
    print(f"[EMAIL DEBUG] Link: {verify_url}")
    print(f"{'='*60}\n")

    return send_email(
        subject='Подтверждение email - INTERIOR',
        to_email=user.email,
        template_name='verify_email',
        context=context
    )


def send_password_reset_email(user, request) -> bool:
    """
    Отправка письма для сброса пароля.

    Создает уникальный токен сброса пароля, действительный 1 час,
    и отправляет письмо со ссылкой для установки нового пароля.

    Args:
        user: Объект пользователя (CustomUser)
        request: Объект HTTP запроса для построения абсолютного URL

    Returns:
        bool: True если отправка успешна, False при ошибке
    """
    from ..models import PasswordResetToken

    PasswordResetToken.objects.filter(user=user).delete()

    # Создаём новый токен
    token = generate_token()
    token_obj = PasswordResetToken.objects.create(
        user=user,
        token=token,
        expires_at=timezone.now() + timedelta(hours=1)
    )

    # Формируем ссылку
    reset_url = request.build_absolute_uri(f'/reset-password/{token_obj.token}/')

    context = {
        'user': user,
        'reset_url': reset_url,
        'site_name': 'INTERIOR',
        'expires_hours': 1
    }

    print(f"\n{'='*60}")
    print(f"[EMAIL DEBUG] Password reset for: {user.email}")
    print(f"[EMAIL DEBUG] Link: {reset_url}")
    print(f"{'='*60}\n")

    return send_email(
        subject='Сброс пароля - INTERIOR',
        to_email=user.email,
        template_name='reset_password',
        context=context
    )