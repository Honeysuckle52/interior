"""
ФОРМЫ ОТЗЫВОВ
"""

from django import forms
from django.core.validators import MinLengthValidator

from ..models import Review


class ReviewForm(forms.ModelForm):
    """
    Форма создания отзыва
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
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input rating-input'
        })
    )
    
    comment = forms.CharField(
        label='Ваш отзыв',
        validators=[MinLengthValidator(10, 'Отзыв должен содержать минимум 10 символов')],
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Расскажите о своём опыте аренды этого помещения...',
            'minlength': 10
        })
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def clean_rating(self):
        """Преобразование рейтинга в int"""
        rating = self.cleaned_data.get('rating')
        return int(rating)
