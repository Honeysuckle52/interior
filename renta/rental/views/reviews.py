"""
ПРЕДСТАВЛЕНИЯ ДЛЯ ОТЗЫВОВ

Handles review creation, listing, and deletion.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404, render
from django.views.decorators.http import require_POST

from ..forms import ReviewForm
from ..models import Space, Review, Booking


logger = logging.getLogger(__name__)


@login_required
@require_POST
def create_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Create a review for a space.

    Args:
        request: HTTP request
        pk: Space primary key

    Returns:
        Redirect to space detail page
    """
    try:
        space = get_object_or_404(Space, pk=pk, is_active=True)

        # Check if user already reviewed this space
        if Review.objects.filter(space=space, author=request.user).exists():
            messages.error(request, 'Вы уже оставили отзыв на это помещение')
            return redirect('space_detail', pk=pk)

        form = ReviewForm(request.POST)
        if form.is_valid():
            try:
                review = form.save(commit=False)
                review.space = space
                review.author = request.user

                # Link to completed booking if exists
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
            except DatabaseError as e:
                logger.error(f"Database error creating review: {e}", exc_info=True)
                messages.error(request, 'Ошибка при сохранении отзыва. Попробуйте снова.')
        else:
            messages.error(request, 'Ошибка при отправке отзыва')

        return redirect('space_detail', pk=pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in create_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Произошла ошибка при создании отзыва')
        return redirect('spaces_list')


@login_required
def my_reviews(request: HttpRequest) -> HttpResponse:
    """
    Display all reviews by the current user.

    Args:
        request: HTTP request

    Returns:
        Rendered reviews list template
    """
    try:
        reviews = Review.objects.filter(
            author=request.user
        ).select_related(
            'space', 'space__city', 'space__category'
        ).prefetch_related(
            'space__images'
        ).order_by('-created_at')

        paginator = Paginator(reviews, 10)
        page_number = request.GET.get('page', 1)

        try:
            reviews_page: Page = paginator.get_page(page_number)
        except (EmptyPage, PageNotAnInteger):
            reviews_page = paginator.get_page(1)

        return render(request, 'account/reviews.html', {'reviews': reviews_page})

    except Exception as e:
        logger.error(f"Error in my_reviews view: {e}", exc_info=True)
        return render(request, 'account/reviews.html', {
            'reviews': [],
            'error': 'Ошибка при загрузке отзывов'
        })


@login_required
@require_POST
def delete_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Delete a user's own review.

    Args:
        request: HTTP request
        pk: Review primary key

    Returns:
        Redirect to space detail page
    """
    try:
        review = get_object_or_404(Review, pk=pk, author=request.user)
        space_pk = review.space.pk
        review.delete()
        messages.success(request, 'Отзыв удалён')
        return redirect('space_detail', pk=space_pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in delete_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при удалении отзыва')
        return redirect('my_reviews')
