"""
====================================================================
ФОРМЫ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит формы для редактирования пользователей
модераторами и администраторами.
====================================================================
"""

from __future__ import annotations

from typing import Any
from django import forms
from django.core.validators import RegexValidator

from ..models import CustomUser


class UserEditForm(forms.ModelForm):
    """
    Форма редактирования пользователя модератором/администратором.

    Позволяет изменить:
    - Имя, фамилию, email, телефон
    - Компанию
    - Тип пользователя (только для админов)
    - Статус активности и блокировки
    """

    phone = forms.CharField(
        required=False,
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9\s\-$$$$]+$',
                message='Введите корректный номер телефона'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        }),
        label='Телефон'
    )

    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'company', 'bio', 'social_vk',
            'user_type', 'is_active', 'is_blocked', 'email_verified'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Фамилия'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название компании'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'О себе...'
            }),
            'social_vk': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://vk.com/username'
            }),
            'user_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_blocked': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'email_verified': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'company': 'Компания',
            'bio': 'О себе',
            'social_vk': 'ВКонтакте',
            'user_type': 'Тип пользователя',
            'is_active': 'Активен',
            'is_blocked': 'Заблокирован',
            'email_verified': 'Email подтверждён',
        }

    def __init__(self, *args: Any, current_user: CustomUser = None, **kwargs: Any) -> None:
        """
        Инициализация формы.

        Args:
            current_user: Текущий пользователь (модератор/админ)
        """
        super().__init__(*args, **kwargs)
        self.current_user = current_user

        # Только администраторы могут менять тип пользователя
        if current_user and not current_user.is_superuser:
            if 'user_type' in self.fields:
                self.fields['user_type'].disabled = True
                self.fields['user_type'].help_text = 'Только администратор может изменить тип'

    def clean_email(self) -> str:
        """Проверка уникальности email."""
        email = self.cleaned_data.get('email')
        if email:
            existing = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('Пользователь с таким email уже существует')
        return email

    def clean(self) -> dict:
        """Дополнительная валидация."""
        cleaned_data = super().clean()

        # Нельзя заблокировать и деактивировать одновременно модератора
        user_type = cleaned_data.get('user_type')
        is_blocked = cleaned_data.get('is_blocked')

        if user_type in ['moderator', 'admin'] and is_blocked:
            if not self.current_user or not self.current_user.is_superuser:
                raise forms.ValidationError(
                    'Только администратор может заблокировать модератора'
                )

        return cleaned_data
