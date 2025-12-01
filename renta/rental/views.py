"""
ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.db.models import Q, Avg, Count, Min
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta

from .models import (
    Space, City, SpaceCategory, SpacePrice, PricingPeriod,
    Booking, BookingStatus, Review, Favorite, CustomUser
)
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm,
    UserProfileForm, UserProfileExtendedForm,
    SpaceFilterForm, ReviewForm, BookingForm
)


# ============== ГЛАВНАЯ СТРАНИЦА ==============

def home(request):
    """
    Главная страница сайта
    """
    # Получаем города для формы поиска
    cities = City.objects.filter(is_active=True)

    # Получаем рекомендуемые помещения
    featured_spaces = Space.objects.filter(
        is_active=True,
        is_featured=True
    ).select_related('city', 'category').prefetch_related('images', 'prices')[:6]

    # Если рекомендуемых мало, добавляем последние
    if featured_spaces.count() < 6:
        featured_spaces = Space.objects.filter(
            is_active=True
        ).select_related('city', 'category').prefetch_related('images', 'prices')[:6]

    # Статистика
    stats = {
        'spaces_count': Space.objects.filter(is_active=True).count(),
        'cities_count': City.objects.filter(is_active=True, spaces__is_active=True).distinct().count(),
    }

    context = {
        'cities': cities,
        'featured_spaces': featured_spaces,
        'stats': stats,
    }
    return render(request, 'home.html', context)


# ============== СПИСОК ПОМЕЩЕНИЙ ==============

def spaces_list(request):
    """
    Страница со списком всех помещений и фильтрацией
    """
    # Базовый queryset
    spaces = Space.objects.filter(is_active=True).select_related(
        'city', 'category'
    ).prefetch_related('images', 'prices', 'prices__period')

    # Получаем данные для фильтров
    cities = City.objects.filter(is_active=True)
    categories = SpaceCategory.objects.filter(is_active=True)

    # Обработка фильтров
    search_query = request.GET.get('search', '')
    selected_city = request.GET.get('city', '')
    selected_category = request.GET.get('category', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    min_capacity = request.GET.get('min_capacity', '')
    sort_by = request.GET.get('sort', '')

    # Применяем фильтры
    if search_query:
        spaces = spaces.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query)
        )

    if selected_city:
        spaces = spaces.filter(city_id=selected_city)

    if selected_category:
        spaces = spaces.filter(category_id=selected_category)

    if min_area:
        spaces = spaces.filter(area_sqm__gte=min_area)

    if max_area:
        spaces = spaces.filter(area_sqm__lte=max_area)

    if min_capacity:
        spaces = spaces.filter(max_capacity__gte=min_capacity)

    # Фильтр по цене (через связанные цены)
    if min_price:
        spaces = spaces.filter(prices__price__gte=min_price, prices__is_active=True)

    if max_price:
        spaces = spaces.filter(prices__price__lte=max_price, prices__is_active=True)

    # Убираем дубликаты
    spaces = spaces.distinct()

    # Сортировка
    if sort_by == 'price_asc':
        spaces = spaces.annotate(min_price=Min('prices__price')).order_by('min_price')
    elif sort_by == 'price_desc':
        spaces = spaces.annotate(min_price=Min('prices__price')).order_by('-min_price')
    elif sort_by == 'area_asc':
        spaces = spaces.order_by('area_sqm')
    elif sort_by == 'area_desc':
        spaces = spaces.order_by('-area_sqm')
    elif sort_by == 'newest':
        spaces = spaces.order_by('-created_at')

    # Пагинация
    paginator = Paginator(spaces, 12)
    page_number = request.GET.get('page', 1)
    spaces_page = paginator.get_page(page_number)

    context = {
        'spaces': spaces_page,
        'cities': cities,
        'categories': categories,
        'search_query': search_query,
        'selected_city': selected_city,
        'selected_category': selected_category,
    }
    return render(request, 'spaces/list.html', context)


# ============== ДЕТАЛИ ПОМЕЩЕНИЯ ==============

def space_detail(request, pk):
    """
    Страница с детальной информацией о помещении
    """
    space = get_object_or_404(
        Space.objects.select_related('city', 'category', 'owner')
        .prefetch_related('images', 'prices', 'prices__period', 'reviews'),
        pk=pk,
        is_active=True
    )

    # Увеличиваем счетчик просмотров
    Space.objects.filter(pk=pk).update(views_count=space.views_count + 1)

    # Получаем цены
    space_prices = space.prices.filter(is_active=True).select_related('period')

    # Похожие помещения (та же категория или город)
    related_spaces = Space.objects.filter(
        is_active=True
    ).filter(
        Q(category=space.category) | Q(city=space.city)
    ).exclude(pk=pk).select_related('city', 'category').prefetch_related('images')[:3]

    # Отзывы
    reviews = space.reviews.filter(is_approved=True).select_related('author')[:10]
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    # Проверяем, в избранном ли
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = Favorite.objects.filter(user=request.user, space=space).exists()

    context = {
        'space': space,
        'space_prices': space_prices,
        'related_spaces': related_spaces,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'is_favorite': is_favorite,
    }
    return render(request, 'spaces/detail.html', context)


# ============== АУТЕНТИФИКАЦИЯ ==============

class CustomLoginView(LoginView):
    """
    Страница входа
    """
    form_class = CustomAuthenticationForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f'Добро пожаловать, {form.get_user().username}!')
        return super().form_valid(form)


def register_view(request):
    """
    Страница регистрации
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('home')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


@login_required
def logout_view(request):
    """
    Выход из системы
    """
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'Вы вышли из системы')
        return redirect('home')
    return redirect('home')


# ============== ЛИЧНЫЙ КАБИНЕТ ==============

@login_required
def dashboard(request):
    """
    Личный кабинет пользователя
    """
    user = request.user

    # Получаем бронирования пользователя
    bookings = Booking.objects.filter(tenant=user).select_related(
        'space', 'status', 'period'
    ).order_by('-created_at')[:5]

    # Избранные помещения
    favorites = Favorite.objects.filter(user=user).select_related('space')[:4]

    # Статистика
    stats = {
        'bookings_count': Booking.objects.filter(tenant=user).count(),
        'favorites_count': Favorite.objects.filter(user=user).count(),
        'reviews_count': Review.objects.filter(author=user).count(),
    }

    context = {
        'bookings': bookings,
        'favorites': favorites,
        'stats': stats,
    }
    return render(request, 'account/dashboard.html', context)


@login_required
def profile(request):
    """
    Страница профиля пользователя
    """
    user = request.user

    # Получаем или создаем профиль
    profile, created = user.profile if hasattr(user, 'profile') else (None, True)
    if not hasattr(user, 'profile'):
        from .models import UserProfile
        profile = UserProfile.objects.create(user=user)
    else:
        profile = user.profile

    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        profile_form = UserProfileExtendedForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        user_form = UserProfileForm(instance=user)
        profile_form = UserProfileExtendedForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'account/profile.html', context)


@login_required
def my_bookings(request):
    """
    Все бронирования пользователя
    """
    bookings = Booking.objects.filter(tenant=request.user).select_related(
        'space', 'status', 'period'
    ).order_by('-created_at')

    # Пагинация
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page', 1)
    bookings_page = paginator.get_page(page_number)

    return render(request, 'account/bookings.html', {'bookings': bookings_page})


@login_required
def my_favorites(request):
    """
    Избранные помещения пользователя
    """
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'space', 'space__city', 'space__category'
    ).prefetch_related('space__images')

    return render(request, 'account/favorites.html', {'favorites': favorites})


# ============== ИЗБРАННОЕ ==============

@login_required
@require_POST
def toggle_favorite(request, pk):
    """
    Добавить/удалить из избранного (AJAX)
    """
    space = get_object_or_404(Space, pk=pk, is_active=True)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user,
        space=space
    )

    if not created:
        favorite.delete()
        return JsonResponse({'status': 'removed', 'message': 'Удалено из избранного'})

    return JsonResponse({'status': 'added', 'message': 'Добавлено в избранное'})


# ============== БРОНИРОВАНИЕ ==============

@login_required
def create_booking(request, pk):
    """
    Создание бронирования
    """
    space = get_object_or_404(Space, pk=pk, is_active=True)
    prices = space.prices.filter(is_active=True).select_related('period')

    if request.method == 'POST':
        form = BookingForm(request.POST)
        form.fields['period'].queryset = PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()

        if form.is_valid():
            booking = form.save(commit=False)
            booking.space = space
            booking.tenant = request.user

            # Получаем цену за период
            price = SpacePrice.objects.get(
                space=space,
                period=booking.period,
                is_active=True
            )
            booking.price_per_period = price.price
            booking.total_amount = price.price * booking.periods_count

            # Устанавливаем даты
            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            booking.start_datetime = datetime.combine(start_date, start_time)

            # Рассчитываем время окончания
            hours = booking.period.hours_count * booking.periods_count
            booking.end_datetime = booking.start_datetime + timedelta(hours=hours)

            # Устанавливаем статус "Ожидание"
            booking.status = BookingStatus.objects.get(code='pending')

            booking.save()
            messages.success(request, 'Бронирование успешно создано!')
            return redirect('booking_detail', pk=booking.pk)
    else:
        form = BookingForm()
        form.fields['period'].queryset = PricingPeriod.objects.filter(
            space_prices__space=space,
            space_prices__is_active=True
        ).distinct()

    context = {
        'space': space,
        'prices': prices,
        'form': form,
    }
    return render(request, 'bookings/create.html', context)


@login_required
def booking_detail(request, pk):
    """
    Детали бронирования
    """
    booking = get_object_or_404(
        Booking.objects.select_related('space', 'status', 'period'),
        pk=pk,
        tenant=request.user
    )
    return render(request, 'bookings/detail.html', {'booking': booking})


@login_required
@require_POST
def cancel_booking(request, pk):
    """
    Отмена бронирования
    """
    booking = get_object_or_404(Booking, pk=pk, tenant=request.user)

    # Проверяем, можно ли отменить
    if booking.status.code in ['pending', 'confirmed']:
        cancelled_status = BookingStatus.objects.get(code='cancelled')
        booking.status = cancelled_status
        booking.save()
        messages.success(request, 'Бронирование отменено')
    else:
        messages.error(request, 'Это бронирование нельзя отменить')

    return redirect('my_bookings')


# ============== ОТЗЫВЫ ==============

@login_required
@require_POST
def create_review(request, pk):
    """
    Создание отзыва
    """
    space = get_object_or_404(Space, pk=pk, is_active=True)

    # Проверяем, не оставлял ли уже отзыв
    if Review.objects.filter(space=space, author=request.user).exists():
        messages.error(request, 'Вы уже оставили отзыв на это помещение')
        return redirect('space_detail', pk=pk)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.space = space
        review.author = request.user
        review.save()
        messages.success(request, 'Спасибо за отзыв! Он появится после модерации.')

    return redirect('space_detail', pk=pk)