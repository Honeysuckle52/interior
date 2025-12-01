"""
ФОРМЫ АУТЕНТИФИКАЦИИ
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.validators import RegexValidator

from ..models import CustomUser, UserProfile


class CustomUserCreationForm(UserCreationForm):
    """
    Расширенная форма регистрации пользователя
    """
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
        validators=[
            RegexValidator(
                regex=r'^\+?[78]?[\s\-]?$$?\d{3}$$?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$',
                message='Введите корректный номер телефона (например: +7 999 123-45-67)'
            )
        ],
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
    
    user_type = forms.ChoiceField(
        choices=[
            ('client', 'Арендатор (ищу помещение)'),
            ('owner', 'Владелец (сдаю помещение)'),
        ],
        initial='client',
        label='Тип аккаунта',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
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
        fields = (
            'username', 'email', 'first_name', 'last_name', 
            'phone', 'user_type', 'password1', 'password2'
        )
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Логин для входа',
                'autocomplete': 'username'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Стилизация полей паролей
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Придумайте пароль',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Повторите пароль',
            'autocomplete': 'new-password'
        })
        
        # Кастомные лейблы
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Подтверждение пароля'
        self.fields['username'].label = 'Логин'

    def clean_email(self):
        """Проверка уникальности email"""
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован')
        return email

    def clean_phone(self):
        """Нормализация номера телефона"""
        phone = self.cleaned_data.get('phone', '')
        if phone:
            # Удаляем все кроме цифр и +
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.user_type = self.cleaned_data.get('user_type', 'client')
        
        if commit:
            user.save()
            # Создаем профиль пользователя
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

    def clean(self):
        """Позволяет входить по email или username"""
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Проверяем, не email ли это
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
