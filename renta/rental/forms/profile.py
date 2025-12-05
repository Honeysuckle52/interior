"""
ФОРМЫ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
"""
from __future__ import annotations  # для поддержки forward references

from typing import Any  # добавлены type hints

from django import forms
from django.core.validators import RegexValidator

from ..models import CustomUser, UserProfile


class UserProfileForm(forms.ModelForm):
    """
    Форма редактирования основных данных профиля
    """
    phone = forms.CharField(
        required=False,
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?[78]?[\s\-]?$$?\d{3}$$?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$',
                message='Введите корректный номер телефона'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        })
    )

    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'email',
            'phone', 'company', 'avatar'
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
                'placeholder': 'Email'
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название компании (необязательно)'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'phone': 'Телефон',
            'company': 'Компания',
            'avatar': 'Фото профиля',
        }

    def clean_email(self) -> str:  # type hints
        """Проверка уникальности email при изменении"""
        email: str = self.cleaned_data.get('email', '')
        if CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Этот email уже используется')
        return email


class UserProfileExtendedForm(forms.ModelForm):
    """
    Форма дополнительных данных профиля (UserProfile)
    """
    class Meta:
        model = UserProfile
        fields = ['bio', 'website', 'social_vk', 'social_telegram']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Расскажите немного о себе или своей компании...'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'social_vk': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://vk.com/username'
            }),
            'social_telegram': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '@username или ссылка'
            }),
        }
        labels = {
            'bio': 'О себе',
            'website': 'Веб-сайт',
            'social_vk': 'ВКонтакте',
            'social_telegram': 'Telegram',
        }


class ChangePasswordForm(forms.Form):
    """
    Форма смены пароля
    """
    current_password = forms.CharField(
        label='Текущий пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите текущий пароль'
        })
    )
    new_password1 = forms.CharField(
        label='Новый пароль',
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый пароль'
        })
    )
    new_password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите новый пароль'
        })
    )

    def __init__(self, user: CustomUser, *args: Any, **kwargs: Any) -> None:  # type hints
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self) -> str:  # type hints
        current: str = self.cleaned_data.get('current_password', '')
        if not self.user.check_password(current):
            raise forms.ValidationError('Неверный текущий пароль')
        return current

    def clean(self) -> dict[str, Any]:  # type hints
        cleaned_data = super().clean()
        new1 = cleaned_data.get('new_password1')
        new2 = cleaned_data.get('new_password2')

        if new1 and new2 and new1 != new2:
            raise forms.ValidationError('Пароли не совпадают')
        return cleaned_data

    def save(self) -> CustomUser:  # type hints
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save()
        return self.user
