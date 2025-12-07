"""
ПРЕДСТАВЛЕНИЯ АУТЕНТИФИКАЦИИ

Handles user login, registration, and logout.
"""

from __future__ import annotations

import logging
import traceback
import re

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from ..forms import CustomUserCreationForm, CustomAuthenticationForm
from ..models import UserProfile


logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    """Custom login view with styled form."""

    form_class = CustomAuthenticationForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('home')

    def form_valid(self, form) -> HttpResponse:
        """Show success message on login."""
        try:
            messages.success(
                self.request,
                f'Добро пожаловать, {form.get_user().username}!'
            )
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Error in login form_valid: {e}", exc_info=True)
            messages.error(self.request, 'Ошибка при входе')
            return super().form_invalid(form)

    def form_invalid(self, form) -> HttpResponse:
        """Show error message on failed login."""
        messages.error(
            self.request,
            'Неверное имя пользователя или пароль'
        )
        return super().form_invalid(form)

    def get_success_url(self) -> str:
        """Get redirect URL after login."""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return str(reverse_lazy('dashboard'))


def register_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user registration.

    Args:
        request: HTTP request

    Returns:
        Rendered registration form or redirect on success
    """
    if request.user.is_authenticated:
        return redirect('home')

    form = CustomUserCreationForm()

    try:
        if request.method == 'POST':
            logger.info(f"Registration attempt with data: {request.POST.keys()}")

            try:
                form = CustomUserCreationForm(request.POST)
            except Exception as form_init_error:
                logger.error(f"Form initialization error: {form_init_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                messages.error(request, f'Ошибка инициализации формы: {str(form_init_error)}')
                return render(request, 'auth/register.html', {'form': CustomUserCreationForm()})

            try:
                if form.is_valid():
                    try:
                        user = form.save()

                        # Create profile if not created in form
                        if not hasattr(user, 'profile'):
                            UserProfile.objects.create(user=user)

                        # Auto-login after registration
                        login(request, user)
                        messages.success(
                            request,
                            f'Добро пожаловать, {user.username}! Регистрация прошла успешно.'
                        )
                        return redirect('dashboard')
                    except DatabaseError as e:
                        logger.error(f"Database error during registration: {e}", exc_info=True)
                        messages.error(request, 'Ошибка базы данных при регистрации. Попробуйте снова.')
                else:
                    logger.warning(f"Form validation errors: {form.errors}")
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
            except re.error as regex_error:
                logger.error(f"Regex error during validation: {regex_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                messages.error(request, f'Ошибка регулярного выражения: {str(regex_error)}')
            except Exception as validation_error:
                logger.error(f"Validation error: {validation_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                messages.error(request, f'Ошибка валидации: {str(validation_error)}')

        return render(request, 'auth/register.html', {'form': form})

    except Exception as e:
        logger.error(f"Unexpected error in register_view: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        messages.error(request, f'Произошла ошибка: {str(e)}')
        return render(request, 'auth/register.html', {'form': CustomUserCreationForm()})


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Handle user logout (POST only for security).

    Args:
        request: HTTP request

    Returns:
        Redirect to home or confirmation page
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
