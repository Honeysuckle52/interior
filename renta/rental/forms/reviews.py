"""
====================================================================
ФОРМЫ ОТЗЫВОВ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.core.validators import MinLengthValidator

from ..models import Review
from ..services.profanity_filter import validate_comment, contains_profanity


class ReviewCreateForm(forms.Form):
    """
    Упрощенная форма для создания отзывов пользователями.
    """

    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput()
    )

    comment = forms.CharField(
        label='Ваш комментарий',
        min_length=10,
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Расскажите о вашем опыте аренды...',
            'minlength': 10,
            'maxlength': 2000
        })
    )

    def clean_comment(self) -> str:
        """Валидация комментария с проверкой на мат."""
        comment = self.cleaned_data.get('comment', '')

        is_valid, error_message = validate_comment(comment)
        if not is_valid:
            raise forms.ValidationError(error_message)

        return comment


class ReviewEditForm(forms.ModelForm):
    """
    Форма для редактирования отзывов пользователями.

    Позволяет пользователям редактировать только свои отзывы.
    Включает проверку на нецензурную лексику.
    """

    RATING_CHOICES = [
        (5, '5 звёзд - Отлично'),
        (4, '4 звезды - Хорошо'),
        (3, '3 звезды - Нормально'),
        (2, '2 звезды - Плохо'),
        (1, '1 звезда - Ужасно'),
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
        min_length=10,
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Расскажите о вашем опыте аренды...',
            'minlength': 10,
            'maxlength': 2000
        })
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def clean_comment(self) -> str:
        """Валидация комментария с проверкой на мат."""
        comment = self.cleaned_data.get('comment', '')

        is_valid, error_message = validate_comment(comment)
        if not is_valid:
            raise forms.ValidationError(error_message)

        return comment

    def clean_rating(self) -> int:
        """Конвертация рейтинга в целое число."""
        rating = self.cleaned_data.get('rating')
        return int(rating)


class ReviewForm(forms.ModelForm):
    """
    Полная форма для редактирования отзывов администраторами.
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
        """Конвертация рейтинга в целое число."""
        rating = self.cleaned_data.get('rating')
        return int(rating)
