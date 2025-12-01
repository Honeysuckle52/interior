"""
ФОРМЫ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.validators import RegexValidator
from .models import CustomUser, UserProfile, Review, Booking


class CustomUserCreationForm(UserCreationForm):
    """
    Форма регистрации пользователя
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email'
        })
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9]{10,15}$',
                message='Введите корректный номер телефона'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Телефон (необязательно)'
        })
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Имя пользователя'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Подтверждение пароля'
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
            # Создаем профиль пользователя
            UserProfile.objects.create(user=user)
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Имя пользователя или Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
    )


class UserProfileForm(forms.ModelForm):
    """
    Форма редактирования профиля
    """
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'company', 'avatar']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


class UserProfileExtendedForm(forms.ModelForm):
    """
    Форма дополнительных данных профиля
    """
    class Meta:
        model = UserProfile
        fields = ['bio', 'website', 'social_vk', 'social_telegram']
        widgets = {
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'social_vk': forms.URLInput(attrs={'class': 'form-control'}),
            'social_telegram': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SpaceFilterForm(forms.Form):
    """
    Форма фильтрации помещений
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Название, описание, адрес...'
        })
    )
    city = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    min_area = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'От м²'
        })
    )
    max_area = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'До м²'
        })
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'От ₽'
        })
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'До ₽'
        })
    )
    min_capacity = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Мин. вместимость'
        })
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'По умолчанию'),
            ('price_asc', 'Цена: по возрастанию'),
            ('price_desc', 'Цена: по убыванию'),
            ('area_asc', 'Площадь: по возрастанию'),
            ('area_desc', 'Площадь: по убыванию'),
            ('newest', 'Сначала новые'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, cities=None, categories=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cities:
            self.fields['city'].choices = [('', 'Все города')] + [
                (c.id, c.name) for c in cities
            ]
        if categories:
            self.fields['category'].choices = [('', 'Все категории')] + [
                (c.id, c.name) for c in categories
            ]


class ReviewForm(forms.ModelForm):
    """
    Форма отзыва
    """
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f'{i} ⭐') for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Напишите ваш отзыв...'
            }),
        }


class BookingForm(forms.ModelForm):
    """
    Форма бронирования
    """
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
    )

    class Meta:
        model = Booking
        fields = ['period', 'periods_count', 'comment']
        widgets = {
            'period': forms.Select(attrs={'class': 'form-select'}),
            'periods_count': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительные пожелания...'
            }),
        }