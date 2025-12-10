"""
====================================================================
ПРЕДСТАВЛЕНИЯ ДЛЯ ОТЗЫВОВ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.db.models import Q, Avg
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404, render
from django.views.decorators.http import require_POST

from ..forms.reviews import ReviewForm, ReviewCreateForm, ReviewEditForm
from ..models import Space, Review, Booking
from ..core.pagination import paginate
from ..services.status_service import StatusCodes
from ..services.profanity_filter import validate_comment


# Константы
REVIEWS_PER_PAGE: int = 10

logger = logging.getLogger(__name__)


@login_required
@require_POST
def create_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Создание нового отзыва на помещение.
    """
    try:
        space: Space = get_object_or_404(Space, pk=pk, is_active=True)

        if Review.objects.filter(space=space, author=request.user).exists():
            messages.error(request, 'Вы уже оставили отзыв на это помещение')
            return redirect('space_detail', pk=pk)

        form = ReviewCreateForm(request.POST)
        if form.is_valid():
            try:
                review = Review(
                    space=space,
                    author=request.user,
                    rating=form.cleaned_data['rating'],
                    comment=form.cleaned_data['comment'],
                    is_approved=False
                )

                completed_booking: Booking | None = Booking.objects.filter(
                    space=space,
                    tenant=request.user,
                    status__code=StatusCodes.COMPLETED
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
            logger.error(f"Form validation errors: {form.errors}")
            error_msg = '; '.join([f"{v[0]}" for k, v in form.errors.items()])
            messages.error(request, f'Ошибка: {error_msg}')

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
    Просмотр всех отзывов текущего пользователя.
    """
    try:
        reviews = Review.objects.filter(
            author=request.user
        ).select_related(
            'space', 'space__city', 'space__category'
        ).prefetch_related(
            'space__images'
        ).order_by('-created_at')

        reviews_page, _ = paginate(reviews, request, REVIEWS_PER_PAGE)

        context: dict[str, Any] = {'reviews': reviews_page}
        return render(request, 'account/reviews.html', context)

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
    Удаление собственного отзыва пользователя.
    """
    try:
        review: Review = get_object_or_404(Review, pk=pk, author=request.user)
        space_pk: int = review.space.pk
        review.delete()
        messages.success(request, 'Отзыв удалён')
        return redirect('space_detail', pk=space_pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in delete_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при удалении отзыва')
        return redirect('my_reviews')


@login_required
def user_edit_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование собственного отзыва пользователем.

    После редактирования отзыв отправляется на повторную модерацию.
    """
    try:
        # Получаем отзыв, проверяя что пользователь - автор
        review: Review = get_object_or_404(
            Review.objects.select_related('space', 'space__city'),
            pk=pk,
            author=request.user
        )

        if request.method == 'POST':
            form = ReviewEditForm(request.POST, instance=review)
            if form.is_valid():
                try:
                    edited_review = form.save(commit=False)
                    # После редактирования отзыв снова отправляется на модерацию
                    edited_review.is_approved = False
                    edited_review.save()

                    messages.success(
                        request,
                        'Отзыв обновлён и отправлен на повторную модерацию.'
                    )
                    return redirect('my_reviews')
                except DatabaseError as e:
                    logger.error(f"Database error editing review: {e}", exc_info=True)
                    messages.error(request, 'Ошибка при сохранении отзыва.')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
        else:
            form = ReviewEditForm(instance=review)

        context: dict[str, Any] = {
            'form': form,
            'review': review,
        }
        return render(request, 'account/edit_review.html', context)

    except Http404:
        messages.error(request, 'Отзыв не найден или вы не являетесь его автором')
        return redirect('my_reviews')
    except Exception as e:
        logger.error(f"Error in user_edit_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при редактировании отзыва')
        return redirect('my_reviews')


@login_required
def edit_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование отзыва (только для администраторов и модераторов).
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для редактирования отзывов')
            return redirect('home')

        review: Review = get_object_or_404(
            Review.objects.select_related('space', 'author'),
            pk=pk
        )

        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=review)
            if form.is_valid():
                form.save()
                messages.success(request, 'Отзыв успешно обновлён')
                return redirect('space_detail', pk=review.space.pk)
        else:
            form = ReviewForm(instance=review)

        context: dict[str, Any] = {
            'form': form,
            'review': review,
        }
        return render(request, 'reviews/edit.html', context)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in edit_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при редактировании отзыва')
        return redirect('home')


@login_required
@require_POST
def admin_delete_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Удаление любого отзыва (только для администраторов и модераторов).
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для удаления отзывов')
            return redirect('home')

        review: Review = get_object_or_404(Review, pk=pk)
        space_pk: int = review.space.pk
        review.delete()
        messages.success(request, 'Отзыв удалён модератором')
        return redirect('space_detail', pk=space_pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in admin_delete_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при удалении отзыва')
        return redirect('home')


@login_required
@require_POST
def approve_review(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Одобрение отзыва для публикации (только для администраторов и модераторов).
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для одобрения отзывов')
            return redirect('home')

        review: Review = get_object_or_404(Review, pk=pk)
        review.is_approved = True
        review.save()
        messages.success(request, 'Отзыв одобрен и опубликован')

        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('space_detail', pk=review.space.pk)

    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in approve_review view for pk={pk}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при одобрении отзыва')
        return redirect('home')


@login_required
def manage_reviews(request: HttpRequest) -> HttpResponse:
    """
    Панель управления отзывами для модерации (администраторы и модераторы).
    """
    try:
        user = request.user

        if not user.can_moderate:
            messages.error(request, 'У вас нет прав для управления отзывами')
            return redirect('home')

        reviews = Review.objects.select_related(
            'space', 'space__city', 'author', 'author__profile'
        ).order_by('-created_at')

        selected_status = request.GET.get('status', '')
        selected_rating = request.GET.get('rating', '')
        search_query = request.GET.get('search', '')

        if selected_status == 'pending':
            reviews = reviews.filter(is_approved=False)
        elif selected_status == 'approved':
            reviews = reviews.filter(is_approved=True)

        if selected_rating:
            try:
                reviews = reviews.filter(rating=int(selected_rating))
            except ValueError:
                pass

        if search_query:
            reviews = reviews.filter(
                Q(author__username__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query) |
                Q(space__title__icontains=search_query) |
                Q(comment__icontains=search_query)
            )

        all_reviews = Review.objects.all()
        pending_count = all_reviews.filter(is_approved=False).count()
        approved_count = all_reviews.filter(is_approved=True).count()
        total_count = all_reviews.count()
        avg_rating = all_reviews.aggregate(avg=Avg('rating'))['avg'] or 0

        reviews_page, _ = paginate(reviews, request, REVIEWS_PER_PAGE)

        context: dict[str, Any] = {
            'reviews': reviews_page,
            'selected_status': selected_status,
            'selected_rating': selected_rating,
            'search_query': search_query,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'total_count': total_count,
            'avg_rating': avg_rating,
        }
        return render(request, 'reviews/manage.html', context)

    except Exception as e:
        logger.error(f"Error in manage_reviews view: {e}", exc_info=True)
        messages.error(request, 'Ошибка при загрузке отзывов')
        return redirect('dashboard')
