"""
ФОРМЫ БРОНИРОВАНИЯ
"""
from __future__ import annotations  # для поддержки forward references

from typing import Any, Optional  # добавлены type hints
from datetime import date, time

from django import forms
from django.utils import timezone

from ..models import Booking, PricingPeriod


class BookingForm(forms.ModelForm):
    """
    Форма создания бронирования
    """
    start_date = forms.DateField(
        label='Дата начала',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': date.today().isoformat()
        })
    )

    start_time = forms.TimeField(
        label='Время начала',
        initial=time(9, 0),
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        })
    )

    period = forms.ModelChoiceField(
        queryset=PricingPeriod.objects.all(),
        label='Период аренды',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'booking-period'
        })
    )

    periods_count = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=1,
        label='Количество периодов',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'max': 100,
            'id': 'booking-periods-count'
        })
    )

    class Meta:
        model = Booking
        fields = ['period', 'periods_count', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительные пожелания или вопросы (необязательно)...'
            }),
        }
        labels = {
            'comment': 'Комментарий',
        }

    def clean_start_date(self) -> date:  # type hints
        """Проверка даты начала"""
        start_date: Optional[date] = self.cleaned_data.get('start_date')
        if start_date and start_date < date.today():
            raise forms.ValidationError('Дата начала не может быть в прошлом')
        return start_date

    def clean_periods_count(self) -> int:  # type hints
        """Проверка количества периодов"""
        periods_count: Optional[int] = self.cleaned_data.get('periods_count')
        if periods_count and periods_count < 1:
            raise forms.ValidationError('Минимум 1 период')
        if periods_count and periods_count > 100:
            raise forms.ValidationError('Максимум 100 периодов')
        return periods_count


class BookingFilterForm(forms.Form):
    """
    Форма фильтрации бронирований (для админки)
    """
    STATUS_CHOICES = [
        ('', 'Все статусы'),
        ('pending', 'Ожидание'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по помещению или клиенту...'
        })
    )
