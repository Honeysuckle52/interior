"""
CONTEXT PROCESSORS
Глобальные данные, доступные во всех шаблонах
"""

from .models import City, SpaceCategory


def global_context(request):
    """
    Добавляет глобальные данные в контекст всех шаблонов
    """
    context = {
        # Города для выпадающего списка в хедере
        'header_cities': City.objects.filter(is_active=True).order_by('name')[:20],

        # Категории для навигации
        'header_categories': SpaceCategory.objects.filter(is_active=True).order_by('name'),

        # Название компании
        'company_name': 'ООО "ИНТЕРЬЕР"',
        'company_phone': '+7 (999) 123-45-67',
        'company_email': 'info@interior.ru',

        # Текущий год для футера
        'current_year': __import__('datetime').datetime.now().year,
    }

    # Количество избранного для авторизованных пользователей
    if request.user.is_authenticated:
        from .models import Favorite
        context['favorites_count'] = Favorite.objects.filter(user=request.user).count()

    return context
