"""
====================================================================
ФОРМЫ АУТЕНТИФИКАЦИИ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит все Django формы, связанные с аутентификацией 
и управлением пользователями, включая регистрацию, вход, сброс пароля
и админ-формы.

Основные формы:
- CustomUserCreationForm: Регистрация новых пользователей
- CustomAuthenticationForm: Вход в систему
- PasswordResetRequestForm: Запрос сброса пароля
- PasswordResetConfirmForm: Установка нового пароля
- EmailVerificationCodeForm: Подтверждение email
- AdminUserCreationForm: Создание пользователей в админке
- AdminUserChangeForm: Редактирование пользователей в админке
====================================================================
"""

from __future__ import annotations

from typing import Any, Optional

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from ..models import CustomUser
from ..core.validators import validate_russian_phone, normalize_phone


def validate_username(value: str) -> None:
    """
    Валидация имени пользователя без использования regex

    Args:
        value (str): Имя пользователя для валидации

    Raises:
        forms.ValidationError: Если имя пользователя не соответствует требованиям

    Требования к имени пользователя:
    - Обязательное поле
    - Минимум 3 символа
    - Максимум 150 символов
    - Разрешены только буквы, цифры и подчеркивание
    """
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

    Содержит все поля для создания нового пользователя, включая валидацию
    уникальности, проверку паролей и согласие с условиями использования.

    Поля формы:
    - username: Логин пользователя
    - email: Email пользователя
    - phone: Номер телефона (необязательно)
    - first_name: Имя пользователя (необязательно)
    - last_name: Фамилия пользователя (необязательно)
    - password1: Основной пароль
    - password2: Подтверждение пароля
    - agree_terms: Согласие с условиями использования
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
        """
        Проверка уникальности email

        Returns:
            str: Валидный и уникальный email

        Raises:
            forms.ValidationError: Если email уже зарегистрирован
        """
        email: str = self.cleaned_data.get('email', '')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован')
        return email

    def clean_username(self) -> str:
        """
        Проверка уникальности username

        Returns:
            str: Валидное и уникальное имя пользователя

        Raises:
            forms.ValidationError: Если имя пользователя уже занято
        """
        username: str = self.cleaned_data.get('username', '')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Это имя пользователя уже занято')
        return username

    def clean_phone(self) -> str:
        """
        Валидация и нормализация номера телефона

        Returns:
            str: Нормализованный номер телефона

        Raises:
            forms.ValidationError: Если номер телефона некорректен
        """
        phone: str = self.cleaned_data.get('phone', '')
        if phone:
            # Валидируем
            try:
                validate_russian_phone(phone)
            except forms.ValidationError:
                raise forms.ValidationError(
                    'Введите корректный номер телефона. Пример: +7 (999) 123-45-67'
                )
            # Нормализуем
            phone = normalize_phone(phone)
        return phone

    def clean_password1(self) -> str:
        """
        Валидация пароля с использованием стандартных валидаторов Django

        Returns:
            str: Валидный пароль

        Raises:
            forms.ValidationError: Если пароль не проходит валидацию
        """
        password1 = self.cleaned_data.get('password1', '')
        if password1:
            validate_password(password1)
        return password1

    def clean_password2(self) -> str:
        """
        Проверка совпадения паролей

        Returns:
            str: Подтвержденный пароль

        Raises:
            forms.ValidationError: Если пароли не совпадают
        """
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return password2

    def save(self, commit: bool = True) -> CustomUser:
        """
        Сохранение пользователя в базу данных

        Args:
            commit (bool): Флаг сохранения в базу данных

        Returns:
            CustomUser: Созданный пользователь
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.user_type = 'user'

        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа с возможностью входа по email

    Расширяет стандартную форму аутентификации Django, добавляя
    возможность входа по email и чекбокс "Запомнить меня"

    Поля формы:
    - username: Логин или Email
    - password: Пароль
    - remember_me: Запомнить меня
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
        """
        Кастомная аутентификация с возможностью входа по email

        Returns:
            dict[str, Any]: Очищенные данные формы

        Raises:
            forms.ValidationError: Если аутентификация не удалась
        """
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


class PasswordResetRequestForm(forms.Form):
    """
    Форма запроса сброса пароля

    Позволяет пользователю запросить сброс пароля по email
    с проверкой существования пользователя с таким email

    Поля формы:
    - email: Email для сброса пароля
    """
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите email вашего аккаунта',
            'autocomplete': 'email'
        })
    )

    def clean_email(self) -> str:
        """
        Проверка существования пользователя с указанным email

        Returns:
            str: Валидный email существующего пользователя

        Raises:
            forms.ValidationError: Если пользователь не найден
        """
        email = self.cleaned_data.get('email', '')
        if not CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email не найден')
        return email


class PasswordResetConfirmForm(forms.Form):
    """
    Форма установки нового пароля

    Используется после подтверждения сброса пароля
    для установки нового пароля

    Поля формы:
    - new_password1: Новый пароль
    - new_password2: Подтверждение нового пароля
    """
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый пароль',
            'autocomplete': 'new-password'
        })
    )
    new_password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите новый пароль',
            'autocomplete': 'new-password'
        })
    )

    def clean_new_password1(self) -> str:
        """
        Валидация нового пароля

        Returns:
            str: Валидный пароль

        Raises:
            forms.ValidationError: Если пароль не проходит валидацию
        """
        password = self.cleaned_data.get('new_password1', '')
        if password:
            validate_password(password)
        return password

    def clean(self) -> dict[str, Any]:
        """
        Проверка совпадения паролей

        Returns:
            dict[str, Any]: Очищенные данные формы

        Raises:
            forms.ValidationError: Если пароли не совпадают
        """
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return cleaned_data


class EmailVerificationCodeForm(forms.Form):
    """
    Форма ввода кода подтверждения email

    Используется для подтверждения email при регистрации
    или смене email

    Поля формы:
    - code: 6-значный код подтверждения
    """
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label='Код подтверждения',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'maxlength': '6',
            'style': 'font-size: 24px; letter-spacing: 8px; font-weight: bold;'
        })
    )

    def clean_code(self) -> str:
        """
        Валидация кода подтверждения

        Returns:
            str: Валидный 6-значный цифровой код

        Raises:
            forms.ValidationError: Если код содержит не только цифры
        """
        code = self.cleaned_data.get('code', '')
        # Проверяем что код состоит только из цифр
        if not code.isdigit():
            raise forms.ValidationError('Код должен содержать только цифры')
        return code


class AdminUserCreationForm(forms.ModelForm):
    """
    Форма создания пользователя в админке

    Упрощенная форма для администраторов сайта

    Поля формы:
    - username: Имя пользователя
    - password1: Пароль
    - password2: Подтверждение пароля
    """
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
        """
        Проверка совпадения паролей для админ-формы

        Returns:
            str: Подтвержденный пароль

        Raises:
            forms.ValidationError: Если пароли не совпадают
        """
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return password2

    def save(self, commit: bool = True) -> CustomUser:
        """
        Сохранение пользователя в админке

        Args:
            commit (bool): Флаг сохранения в базу данных

        Returns:
            CustomUser: Созданный пользователь
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class AdminUserChangeForm(UserChangeForm):
    """
    Форма редактирования пользователя в админке

    Расширяет стандартную форму UserChangeForm Django
    для редактирования пользователей через админ-панель
    """

    class Meta:
        model = CustomUser
        fields = '__all__'
