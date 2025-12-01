"""
ПРЕДСТАВЛЕНИЯ ЛИЧНОГО КАБИНЕТА
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count

from ..models import Booking, Favorite, Review, UserProfile
from ..forms import UserProfileForm, UserProfileExtendedForm


@login_required
def dashboard(request):
    """
    Главная страница личного кабинета
    """
    user = request.user
    
    # Последние бронирования
    recent_bookings = Booking.objects.filter(
        tenant=user
    ).select_related(
        'space', 'space__city', 'status', 'period'
    ).prefetch_related(
        'space__images'
    ).order_by('-created_at')[:5]
    
    # Избранные помещения
    recent_favorites = Favorite.objects.filter(
        user=user
    ).select_related(
        'space', 'space__city', 'space__category'
    ).prefetch_related(
        'space__images', 'space__prices'
    ).order_by('-created_at')[:4]
    
    # Статистика пользователя
    stats = {
        'bookings_total': Booking.objects.filter(tenant=user).count(),
        'bookings_active': Booking.objects.filter(
            tenant=user, 
            status__code__in=['pending', 'confirmed']
        ).count(),
        'favorites_count': Favorite.objects.filter(user=user).count(),
        'reviews_count': Review.objects.filter(author=user).count(),
        'total_spent': Booking.objects.filter(
            tenant=user,
            status__code__in=['confirmed', 'completed']
        ).aggregate(total=Sum('total_amount'))['total'] or 0,
    }
    
    context = {
        'recent_bookings': recent_bookings,
        'recent_favorites': recent_favorites,
        'stats': stats,
    }
    return render(request, 'account/dashboard.html', context)


@login_required
def profile(request):
    """
    Страница редактирования профиля
    """
    user = request.user
    
    # Получаем или создаем профиль
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        user_form = UserProfileForm(
            request.POST, 
            request.FILES, 
            instance=user
        )
        profile_form = UserProfileExtendedForm(
            request.POST, 
            instance=profile
        )
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
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
    Все бронирования пользователя с фильтрацией
    """
    user = request.user
    
    bookings = Booking.objects.filter(
        tenant=user
    ).select_related(
        'space', 'space__city', 'space__category', 'status', 'period'
    ).prefetch_related(
        'space__images'
    ).order_by('-created_at')
    
    # Фильтр по статусу
    status_filter = request.GET.get('status', '')
    if status_filter:
        bookings = bookings.filter(status__code=status_filter)
    
    # Статистика по статусам
    status_stats = Booking.objects.filter(tenant=user).values(
        'status__code', 'status__name', 'status__color'
    ).annotate(count=Count('id'))
    
    from django.core.paginator import Paginator
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page', 1)
    bookings_page = paginator.get_page(page_number)
    
    context = {
        'bookings': bookings_page,
        'status_filter': status_filter,
        'status_stats': status_stats,
    }
    return render(request, 'account/bookings.html', context)


@login_required
def my_favorites(request):
    """
    Избранные помещения пользователя
    """
    favorites = Favorite.objects.filter(
        user=request.user
    ).select_related(
        'space', 'space__city', 'space__city__region', 'space__category'
    ).prefetch_related(
        'space__images', 'space__prices', 'space__prices__period'
    ).order_by('-created_at')
    
    from django.core.paginator import Paginator
    paginator = Paginator(favorites, 12)
    page_number = request.GET.get('page', 1)
    favorites_page = paginator.get_page(page_number)
    
    return render(request, 'account/favorites.html', {'favorites': favorites_page})
