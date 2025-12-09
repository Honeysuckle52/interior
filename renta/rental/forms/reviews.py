"""
====================================================================
ФОРМЫ ОТЗЫВОВ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит все Django формы, связанные с отзывами на сайте,
включая создание новых отзывов пользователями и их редактирование
администраторами.

Основные формы:
- ReviewCreateForm: Упрощенная форма для создания отзывов пользователями
- ReviewForm: Полная форма для редактирования отзывов администраторами

Функционал:
- Создание отзывов с оценкой и комментарием
- Редактирование отзывов с одобрением/отклонением
- Валидация минимальной длины комментария
- Контроль рейтинга (1-5 звезд)
====================================================================
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.core.validators import MinLengthValidator

from ..models import Review


class ReviewCreateForm(forms.Form):
    """
    Упрощенная форма для создания отзывов пользователями.

    Используется клиентами для оставления отзывов о помещении
    после завершения аренды. Содержит минимальный набор полей.

    Поля формы:
    - rating: Оценка от 1 до 5 (скрытое поле для JS-виджета)
    - comment: Текст отзыва (минимум 10 символов)
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
    Полная форма для редактирования отзывов администраторами.

    Используется администраторами и модераторами для управления
    отзывами: редактирования, одобрения и модерации.

    Поля формы:
    - rating: Оценка от 1 до 5 с человекочитаемыми подписями
    - comment: Текст отзыва с валидацией минимальной длины
    - is_approved: Флаг одобрения отзыва для публикации
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
        """
        Конвертация рейтинга в целое число.

        Args:
            rating: Рейтинг в формате строки

        Returns:
            int: Рейтинг в формате целого числа
        """
        rating = self.cleaned_data.get('rating')
        return int(rating)