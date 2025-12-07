"""
ФОРМЫ ОТЗЫВОВ
"""
from __future__ import annotations

from typing import Any

from django import forms
from django.core.validators import MinLengthValidator

from ..models import Review


class ReviewCreateForm(forms.Form):
    """
    Simple form for users to create reviews.
    """
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput()
    )

    comment = forms.CharField(
        label='Ваш комментарий',
        min_length=10,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Расскажите о вашем опыте аренды...',
            'minlength': 10
        })
    )


class ReviewForm(forms.ModelForm):
    """
    Full form for admin/moderator editing.
    """
    RATING_CHOICES = [
        (5, '5 - Отлично'),
        (4, '4 - Хорошо'),
        (3, '3 - Нормально'),
        (2, '2 - Плохо'),
        (1, '1 - Ужасно'),
    ]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        label='Оценка',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    comment = forms.CharField(
        label='Комментарий',
        validators=[MinLengthValidator(10, 'Отзыв должен содержать минимум 10 символов')],
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Текст отзыва...',
            'minlength': 10
        })
    )

    is_approved = forms.BooleanField(
        label='Отзыв одобрен',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment', 'is_approved']

    def clean_rating(self) -> int:
        """Convert rating to int"""
        rating = self.cleaned_data.get('rating')
        return int(rating)
