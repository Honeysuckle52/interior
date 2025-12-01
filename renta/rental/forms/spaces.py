"""
ФОРМЫ ДЛЯ ПОМЕЩЕНИЙ
"""

from django import forms
from django.utils.text import slugify
from unidecode import unidecode

from ..models import Space, SpaceImage, City, SpaceCategory


class SpaceFilterForm(forms.Form):
    """
    Форма фильтрации помещений на странице списка
    """
    search = forms.CharField(
        required=False,
        label='Поиск',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Название, адрес, описание...'
        })
    )
    
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        required=False,
        empty_label='Все города',
        label='Город',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        queryset=SpaceCategory.objects.none(),
        required=False,
        empty_label='Все категории',
        label='Категория',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    min_area = forms.DecimalField(
        required=False,
        min_value=0,
        label='Площадь от',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'от м²'
        })
    )
    
    max_area = forms.DecimalField(
        required=False,
        min_value=0,
        label='Площадь до',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'до м²'
        })
    )
    
    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        label='Цена от',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'от ₽'
        })
    )
    
    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        label='Цена до',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'до ₽'
        })
    )
    
    min_capacity = forms.IntegerField(
        required=False,
        min_value=1,
        label='Вместимость от',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'чел.'
        })
    )
    
    SORT_CHOICES = [
        ('newest', 'Сначала новые'),
        ('price_asc', 'Цена: по возрастанию'),
        ('price_desc', 'Цена: по убыванию'),
        ('area_asc', 'Площадь: по возрастанию'),
        ('area_desc', 'Площадь: по убыванию'),
        ('popular', 'По популярности'),
        ('rating', 'По рейтингу'),
    ]
    
    sort = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        initial='newest',
        label='Сортировка',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Загружаем актуальные данные для select'ов
        self.fields['city'].queryset = City.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['category'].queryset = SpaceCategory.objects.filter(
            is_active=True
        ).order_by('name')


class SpaceForm(forms.ModelForm):
    """
    Форма создания/редактирования помещения (для владельцев)
    """
    class Meta:
        model = Space
        fields = [
            'title', 'category', 'city', 'address',
            'area_sqm', 'max_capacity', 'description',
            'is_active', 'is_featured'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название помещения'
            }),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Полный адрес'
            }),
            'area_sqm': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Площадь в м²',
                'min': 1,
                'step': '0.1'
            }),
            'max_capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Максимум человек',
                'min': 1
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Подробное описание помещения, удобства, условия...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'title': 'Название',
            'category': 'Категория',
            'city': 'Город',
            'address': 'Адрес',
            'area_sqm': 'Площадь (м²)',
            'max_capacity': 'Вместимость (чел.)',
            'description': 'Описание',
            'is_active': 'Активно (видно в каталоге)',
            'is_featured': 'Рекомендуемое',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].queryset = City.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['category'].queryset = SpaceCategory.objects.filter(
            is_active=True
        ).order_by('name')

    def save(self, commit=True):
        space = super().save(commit=False)
        # Генерируем slug из названия
        if not space.slug:
            base_slug = slugify(unidecode(space.title))
            slug = base_slug
            counter = 1
            while Space.objects.filter(slug=slug).exclude(pk=space.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            space.slug = slug
        
        if commit:
            space.save()
        return space


class SpaceImageForm(forms.ModelForm):
    """
    Форма загрузки изображения помещения
    """
    class Meta:
        model = SpaceImage
        fields = ['image', 'alt_text', 'is_primary']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'alt_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Описание изображения'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'image': 'Изображение',
            'alt_text': 'Alt текст',
            'is_primary': 'Главное фото',
        }
