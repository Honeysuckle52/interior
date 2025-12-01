"""
ПРЕДСТАВЛЕНИЯ ДЛЯ ОТЗЫВОВ
"""

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse

from ..models import Space, Review, Booking
from ..forms import ReviewForm


@login_required
@require_POST
def create_review(request, pk):
    """
    Создание отзыва о помещении
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
        
        # Связываем с бронированием, если есть завершённое
        completed_booking = Booking.objects.filter(
            space=space,
            tenant=request.user,
            status__code='completed'
        ).first()
        if completed_booking:
            review.booking = completed_booking
        
        review.save()
        messages.success(
            request, 
            'Спасибо за отзыв! Он появится на странице после модерации.'
        )
    else:
        messages.error(request, 'Ошибка при отправке отзыва')
    
    return redirect('space_detail', pk=pk)


@login_required
def my_reviews(request):
    """
    Все отзывы пользователя
    """
    from django.shortcuts import render
    from django.core.paginator import Paginator
    
    reviews = Review.objects.filter(
        author=request.user
    ).select_related(
        'space', 'space__city', 'space__category'
    ).prefetch_related(
        'space__images'
    ).order_by('-created_at')
    
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page', 1)
    reviews_page = paginator.get_page(page_number)
    
    return render(request, 'account/reviews.html', {'reviews': reviews_page})


@login_required
@require_POST
def delete_review(request, pk):
    """
    Удаление своего отзыва
    """
    review = get_object_or_404(Review, pk=pk, author=request.user)
    space_pk = review.space.pk
    review.delete()
    messages.success(request, 'Отзыв удалён')
    return redirect('space_detail', pk=space_pk)
