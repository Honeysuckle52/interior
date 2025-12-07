"""
ФОРМЫ АУТЕНТИФИКАЦИИ
"""
from __future__ import annotations

from typing import Any, Optional

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from ..models import CustomUser, UserProfile
from ..services.validators import validate_russian_phone, normalize_phone


def validate_username(value: str) -> None:
    """Валидация имени пользователя без использования regex"""
    if not value:
        raise forms.ValidationError('Имя пользователя обязательно')
    if len(value) < 3:
        raise forms.ValidationError('Имя пользователя должно содержать минимум 3 символа')
    if len(value) > 150:
        raise forms.ValidationError('Имя пользователя не должно превышать 150 символов')
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
    if not all(c in allowed_chars for c in value):
        raise forms.ValidationError('Имя пользователя может содержать только буквы, цифры и подчеркивание')


class CustomUserCreationForm(forms.ModelForm):
    """
    Форма регистрации пользователя.
    Все пользователи регистрируются как обычные пользователи (user).
    Роли moderator и admin назначаются только через админ-панель.
    """
    username = forms.CharField(
        max_length=150,
        label='Логин',
        validators=[validate_username],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Логин для входа',
            'autocomplete': 'username'
        })
    )

    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@mail.ru',
            'autocomplete': 'email'
        })
    )

    phone = forms.CharField(
        required=False,
        max_length=20,
        label='Телефон',
        validators=[validate_russian_phone],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67',
            'autocomplete': 'tel'
        })
    )

    first_name = forms.CharField(
        required=False,
        max_length=150,
        label='Имя',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Иван',
            'autocomplete': 'given-name'
        })
    )

    last_name = forms.CharField(
        required=False,
        max_length=150,
        label='Фамилия',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Иванов',
            'autocomplete': 'family-name'
        })
    )

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Придумайте пароль',
            'autocomplete': 'new-password'
        })
    )

    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
    )

    agree_terms = forms.BooleanField(
        required=True,
        label='Я согласен с условиями использования',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone')
        exclude = ('user_type',)

    def clean_email(self) -> str:
        """Проверка уникальности email"""
        email: str = self.cleaned_data.get('email', '')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован')
        return email

    def clean_username(self) -> str:
        """Проверка уникальности username"""
        username: str = self.cleaned_data.get('username', '')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Это имя пользователя уже занято')
        return username

    def clean_phone(self) -> str:
        """Нормализация номера телефона"""
        phone: str = self.cleaned_data.get('phone', '')
        if phone:
            phone = normalize_phone(phone)
        return phone

    def clean_password1(self) -> str:
        """Валидация пароля"""
        password1 = self.cleaned_data.get('password1', '')
        if password1:
            validate_password(password1)
        return password1

    def clean_password2(self) -> str:
        """Проверка совпадения паролей"""
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return password2

    def save(self, commit: bool = True) -> CustomUser:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.user_type = 'user'

        if commit:
            user.save()
            UserProfile.objects.get_or_create(user=user)
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа с возможностью входа по email
    """
    username = forms.CharField(
        label='Логин или Email',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите логин или email',
            'autocomplete': 'username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите пароль',
            'autocomplete': 'current-password'
        })
    )

    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        label='Запомнить меня',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    def clean(self) -> dict[str, Any]:
        """Позволяет входить по email или username"""
        username: Optional[str] = self.cleaned_data.get('username')
        password: Optional[str] = self.cleaned_data.get('password')

        if username and password:
            if '@' in username:
                try:
                    user = CustomUser.objects.get(email=username)
                    username = user.username
                except CustomUser.DoesNotExist:
                    pass

            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password
            )

            if self.user_cache is None:
                raise forms.ValidationError(
                    'Неверный логин/email или пароль',
                    code='invalid_login'
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    'Этот аккаунт деактивирован',
                    code='inactive'
                )

        return self.cleaned_data


class AdminUserCreationForm(forms.ModelForm):
    """Форма создания пользователя в админке (без проблемных regex)"""
    username = forms.CharField(
        max_length=150,
        label='Имя пользователя',
        validators=[validate_username],
        widget=forms.TextInput(attrs={'class': 'vTextField'})
    )

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'vTextField'})
    )

    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'vTextField'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 'user_type')

    def clean_password2(self) -> str:
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return password2

    def save(self, commit: bool = True) -> CustomUser:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AdminUserChangeForm(UserChangeForm):
    """Форма редактирования пользователя в админке"""

    class Meta:
        model = CustomUser
        fields = '__all__'
