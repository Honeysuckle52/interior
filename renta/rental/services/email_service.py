"""
СЕРВИС EMAIL-УВЕДОМЛЕНИЙ
Отправка писем через Mail.ru SMTP
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
    """Генерация безопасного токена"""
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
