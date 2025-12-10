"""
====================================================================
ПРЕДСТАВЛЕНИЯ АУТЕНТИФИКАЦИИ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит представления Django для всей функциональности
аутентификации и авторизации на сайте, включая регистрацию, вход,
выход, подтверждение email и сброс пароля.

Основные представления:
- register_view: Регистрация нового пользователя
- CustomLoginView: Кастомная страница входа (наследуется от LoginView)
- verify_email_code: Ввод 6-значного кода подтверждения email
- resend_verification_code: Повторная отправка кода подтверждения
- logout_view: Выход из системы (только POST)
- verify_email: Подтверждение email по ссылке из письма
- resend_verification: Повторная отправка письма подтверждения
- password_reset_request: Запрос на сброс пароля
- password_reset_confirm: Установка нового пароля по токену

Основные особенности:
- Двойная верификация email (код и ссылка)
- Защита представлений декораторами
- Обработка ошибок с логированием и пользовательскими сообщениями
- Использование сессий для временного хранения кодов подтверждения
- Интеграция с сервисом email-уведомлений
====================================================================
"""

from __future__ import annotations

import logging
import random
import string

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone

from ..forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    PasswordResetRequestForm,
    PasswordResetConfirmForm,
    EmailVerificationCodeForm
)
from ..models import CustomUser, EmailVerificationToken, PasswordResetToken
from ..services.email_service import send_verification_email, send_password_reset_email, send_verification_code


logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    """
    Кастомная страница входа с поддержкой входа по email
    и проверкой подтверждения email.

    Наследует стандартный LoginView Django, добавляя:
    - Проверку подтверждения email перед входом
    - Генерацию и отправку кода подтверждения при необходимости
    - Перенаправление на страницу ввода кода для неподтвержденных пользователей
    - Кастомные сообщения об успехе/ошибке
    """

    form_class = CustomAuthenticationForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('home')

    def form_valid(self, form) -> HttpResponse:
        """
        Обработка успешной валидации формы с проверкой подтверждения email.

        Args:
            form: Валидная форма аутентификации

        Returns:
            HttpResponse: Редирект на dashboard или страницу подтверждения кода
        """
        user = form.get_user()

        # Администраторы и суперпользователи пропускают проверку email
        if user.is_staff or user.is_superuser:
            try:
                messages.success(
                    self.request,
                    f'Добро пожаловать, {user.username}!'
                )
                return super().form_valid(form)
            except Exception as e:
                logger.error(f"Error in admin login: {e}", exc_info=True)
                messages.error(self.request, 'Ошибка при входе')
                return super().form_invalid(form)

        # Обычные пользователи должны подтвердить email
        if not user.email_verified:
            # Генерируем и отправляем код подтверждения
            code = ''.join(random.choices(string.digits, k=6))

            # Сохраняем код в сессию
            self.request.session['verification_user_id'] = user.id
            self.request.session['verification_code'] = code
            self.request.session['verification_code_time'] = timezone.now().isoformat()

            # Отправляем код на почту
            try:
                send_verification_code(user, code, self.request)
                messages.warning(
                    self.request,
                    'Для входа необходимо подтвердить email. Код отправлен на вашу почту.'
                )
            except Exception as e:
                logger.error(f"Error sending verification code: {e}")
                messages.warning(
                    self.request,
                    f'Для входа необходимо подтвердить email. Код: {code}'
                )

            return redirect('verify_email_code')

        # Успешный вход для подтвержденных пользователей
        try:
            messages.success(
                self.request,
                f'Добро пожаловать, {user.username}!'
            )
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Error in login form_valid: {e}", exc_info=True)
            messages.error(self.request, 'Ошибка при входе')
            return super().form_invalid(form)

    def form_invalid(self, form) -> HttpResponse:
        """
        Обработка невалидной формы входа.

        Args:
            form: Невалидная форма аутентификации

        Returns:
            HttpResponse: Отрисовка формы с сообщением об ошибке
        """
        messages.error(
            self.request,
            'Неверное имя пользователя или пароль'
        )
        return super().form_invalid(form)

    def get_success_url(self) -> str:
        """
        Определение URL для перенаправления после успешного входа.

        Returns:
            str: URL для редиректа
        """
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return str(reverse_lazy('dashboard'))


def verify_email_code(request: HttpRequest) -> HttpResponse:
    """
    Страница ввода 6-значного кода подтверждения email.

    Проверяет код, сохраненный в сессии, и подтверждает email пользователя
    при успешной проверке.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка страницы ввода кода или редирект на dashboard

    Template:
        auth/verify_code.html

    Context:
        - form: Форма для ввода кода подтверждения
        - email: Email пользователя для отображения
    """
    user_id = request.session.get('verification_user_id')

    if not user_id:
        messages.error(request, 'Сессия истекла. Попробуйте войти снова.')
        return redirect('login')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('login')

    form = EmailVerificationCodeForm()

    if request.method == 'POST':
        form = EmailVerificationCodeForm(request.POST)

        if form.is_valid():
            entered_code = form.cleaned_data['code']
            stored_code = request.session.get('verification_code')

            if entered_code == stored_code:
                # Подтверждаем email
                user.email_verified = True
                user.save()

                # Очищаем сессию
                del request.session['verification_user_id']
                del request.session['verification_code']
                del request.session['verification_code_time']

                # Авторизуем пользователя
                login(request, user)

                messages.success(request, f'Email подтверждён! Добро пожаловать, {user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Неверный код подтверждения')

    return render(request, 'auth/verify_code.html', {
        'form': form,
        'email': user.email
    })


def resend_verification_code(request: HttpRequest) -> HttpResponse:
    """
    Повторная отправка кода подтверждения email.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Редирект на страницу ввода кода с сообщением
    """
    user_id = request.session.get('verification_user_id')

    if not user_id:
        messages.error(request, 'Сессия истекла')
        return redirect('login')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('login')

    # Генерируем новый код
    code = ''.join(random.choices(string.digits, k=6))
    request.session['verification_code'] = code
    request.session['verification_code_time'] = timezone.now().isoformat()

    try:
        send_verification_code(user, code, request)
        messages.success(request, 'Новый код отправлен на вашу почту')
    except Exception as e:
        logger.error(f"Error resending code: {e}")
        messages.info(request, f'Код подтверждения: {code}')

    return redirect('verify_email_code')


def register_view(request: HttpRequest) -> HttpResponse:
    """
    Регистрация нового пользователя.

    Создает нового пользователя, генерирует код подтверждения
    и перенаправляет на страницу его ввода.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка формы регистрации или редирект на ввод кода

    Template:
        auth/register.html

    Context:
        - form: Форма регистрации пользователя
    """
    if request.user.is_authenticated:
        return redirect('home')

    form = CustomUserCreationForm()

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            try:
                user = form.save()

                # Генерируем код подтверждения
                code = ''.join(random.choices(string.digits, k=6))

                # Сохраняем в сессию
                request.session['verification_user_id'] = user.id
                request.session['verification_code'] = code
                request.session['verification_code_time'] = timezone.now().isoformat()

                # Отправляем код
                try:
                    send_verification_code(user, code, request)
                    messages.info(
                        request,
                        'Регистрация почти завершена! Введите код, отправленный на вашу почту.'
                    )
                except Exception as e:
                    logger.warning(f"Could not send verification code: {e}")
                    messages.info(request, f'Код подтверждения: {code}')

                return redirect('verify_email_code')

            except DatabaseError as e:
                logger.error(f"Database error during registration: {e}", exc_info=True)
                messages.error(request, 'Ошибка базы данных при регистрации')
        else:
            # Отображение ошибок валидации формы
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, f'{error}')

    return render(request, 'auth/register.html', {'form': form})


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Выход из системы (только POST метод).

    Предоставляет страницу подтверждения выхода и обрабатывает
    POST запрос для завершения сеанса пользователя.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка страницы подтверждения или редирект на главную

    Template:
        auth/logout_confirm.html (для GET запроса)
    """
    try:
        if request.method == 'POST':
            username = request.user.username
            logout(request)
            messages.info(request, f'До свидания, {username}!')
            return redirect('home')

        return render(request, 'auth/logout_confirm.html')

    except Exception as e:
        logger.error(f"Error in logout_view: {e}", exc_info=True)
        logout(request)
        return redirect('home')


def verify_email(request: HttpRequest, token: str) -> HttpResponse:
    """
    Подтверждение email по ссылке из письма (альтернативный метод).

    Используется для подтверждения email через ссылку, отправленную
    в письме, а не через 6-значный код.

    Args:
        request (HttpRequest): Объект HTTP запроса
        token (str): Уникальный токен подтверждения из URL

    Returns:
        HttpResponse: Редирект на dashboard или login с соответствующим сообщением
    """
    try:
        try:
            token_obj = EmailVerificationToken.objects.get(token=token)
        except EmailVerificationToken.DoesNotExist:
            messages.error(request, 'Недействительная ссылка для подтверждения')
            return redirect('login')

        if not token_obj.is_valid():
            token_obj.delete()
            messages.error(request, 'Ссылка для подтверждения истекла. Запросите новую.')
            return redirect('login')

        user = token_obj.user
        user.email_verified = True
        user.save()

        # Удаляем использованный токен
        token_obj.delete()

        messages.success(request, 'Email успешно подтверждён!')

        if request.user.is_authenticated:
            return redirect('dashboard')
        return redirect('login')

    except Exception as e:
        logger.error(f"Error verifying email: {e}", exc_info=True)
        messages.error(request, 'Ошибка при подтверждении email')
        return redirect('home')


def resend_verification(request: HttpRequest) -> HttpResponse:
    """
    Повторная отправка письма подтверждения email.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Редирект на dashboard с сообщением
    """
    if not request.user.is_authenticated:
        messages.error(request, 'Войдите в систему')
        return redirect('login')

    if request.user.email_verified:
        messages.info(request, 'Email уже подтверждён')
        return redirect('dashboard')

    try:
        send_verification_email(request.user, request)
        messages.success(request, 'Письмо отправлено повторно. Проверьте почту.')
    except Exception as e:
        logger.error(f"Error resending verification: {e}", exc_info=True)
        messages.error(request, 'Ошибка при отправке письма')

    return redirect('dashboard')


def password_reset_request(request: HttpRequest) -> HttpResponse:
    """
    Запрос на сброс пароля по email.

    Args:
        request (HttpRequest): Объект HTTP запроса

    Returns:
        HttpResponse: Отрисовка формы запроса сброса или редирект на login

    Template:
        auth/password_reset.html

    Context:
        - form: Форма запроса сброса пароля
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = PasswordResetRequestForm()

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)
                send_password_reset_email(user, request)
                messages.success(
                    request,
                    'Инструкции по сбросу пароля отправлены на вашу почту.'
                )
                return redirect('login')
            except CustomUser.DoesNotExist:
                # Всегда показываем успешное сообщение для безопасности
                messages.success(
                    request,
                    'Если email зарегистрирован, вы получите инструкции по сбросу пароля'
                )
                return redirect('login')
            except Exception as e:
                logger.error(f"Error sending password reset: {e}", exc_info=True)
                messages.error(request, 'Ошибка при отправке письма')

    return render(request, 'auth/password_reset.html', {'form': form})


def password_reset_confirm(request: HttpRequest, token: str) -> HttpResponse:
    """
    Установка нового пароля по ссылке из письма.

    Args:
        request (HttpRequest): Объект HTTP запроса
        token (str): Уникальный токен сброса пароля из URL

    Returns:
        HttpResponse: Отрисовка формы установки нового пароля или редирект

    Template:
        auth/password_reset_confirm.html

    Context:
        - form: Форма установки нового пароля
        - token: Токен сброса пароля (для hidden поля)
    """
    try:
        try:
            token_obj = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            messages.error(request, 'Недействительная или истёкшая ссылка для сброса пароля')
            return redirect('password_reset')

        if not token_obj.is_valid():
            token_obj.delete()
            messages.error(request, 'Ссылка для сброса пароля истекла. Запросите новую.')
            return redirect('password_reset')

        form = PasswordResetConfirmForm()

        if request.method == 'POST':
            form = PasswordResetConfirmForm(request.POST)

            if form.is_valid():
                user = token_obj.user
                user.set_password(form.cleaned_data['new_password1'])
                user.save()

                # Удаляем использованный токен
                token_obj.delete()

                messages.success(request, 'Пароль успешно изменён! Теперь вы можете войти.')
                return redirect('login')

        return render(request, 'auth/password_reset_confirm.html', {
            'form': form,
            'token': token
        })

    except Exception as e:
        logger.error(f"Error in password reset confirm: {e}", exc_info=True)
        messages.error(request, 'Ошибка при сбросе пароля. Попробуйте запросить ссылку заново.')
        return redirect('password_reset')
