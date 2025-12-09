"""
ПРЕДСТАВЛЕНИЯ ДЛЯ УПРАВЛЕНИЯ КАТЕГОРИЯМИ ПОМЕЩЕНИЙ

Handles CRUD operations for space categories (admin/moderator only).
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.text import slugify
from unidecode import unidecode

from ..models import SpaceCategory

logger = logging.getLogger(__name__)

# Константы
DEFAULT_ITEMS_PER_PAGE: int = 12


@login_required
def manage_categories(request: HttpRequest) -> HttpResponse:
    """
    Страница управления категориями помещений для админов и модераторов.
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для управления категориями')
        return redirect('dashboard')

    # Получаем все категории с подсчётом помещений
    categories: QuerySet[SpaceCategory] = SpaceCategory.objects.annotate(
        spaces_count=Count('spaces', filter=Q(spaces__is_active=True)),
        total_spaces_count=Count('spaces')
    ).order_by('name')

    # Статистика
    stats = {
        'total': categories.count(),
        'active': categories.filter(is_active=True).count(),
        'inactive': categories.filter(is_active=False).count(),
        'with_spaces': categories.filter(spaces_count__gt=0).count(),
    }

    # Пагинация
    paginator = Paginator(categories, DEFAULT_ITEMS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    try:
        categories_page = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        categories_page = paginator.get_page(1)

    return render(request, 'categories/manage.html', {
        'categories': categories_page,
        'stats': stats,
    })


@login_required
def add_category(request: HttpRequest) -> HttpResponse:
    """
    Добавление новой категории помещений.
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для добавления категорий')
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', 'fa-building').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        # Валидация
        errors = []
        if not name:
            errors.append('Название категории обязательно')
        elif len(name) > 100:
            errors.append('Название не может быть длиннее 100 символов')
        elif SpaceCategory.objects.filter(name__iexact=name).exists():
            errors.append('Категория с таким названием уже существует')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'categories/add.html', {
                'form_data': {
                    'name': name,
                    'icon': icon,
                    'description': description,
                    'is_active': is_active,
                }
            })

        # Генерируем slug
        base_slug = slugify(unidecode(name))
        slug = base_slug
        counter = 1
        while SpaceCategory.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Создаём категорию
        SpaceCategory.objects.create(
            name=name,
            slug=slug,
            icon=icon,
            description=description,
            is_active=is_active
        )

        # Очищаем кэш категорий
        cache.delete('header_categories')

        messages.success(request, f'Категория "{name}" успешно создана')
        return redirect('manage_categories')

    return render(request, 'categories/add.html', {
        'form_data': {
            'is_active': True,
            'icon': 'fa-building',
        }
    })


@login_required
def edit_category(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование категории помещений.
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для редактирования категорий')
        return redirect('dashboard')

    category = get_object_or_404(SpaceCategory, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', 'fa-building').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        # Валидация
        errors = []
        if not name:
            errors.append('Название категории обязательно')
        elif len(name) > 100:
            errors.append('Название не может быть длиннее 100 символов')
        elif SpaceCategory.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            errors.append('Категория с таким названием уже существует')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'categories/edit.html', {
                'category': category,
                'form_data': {
                    'name': name,
                    'icon': icon,
                    'description': description,
                    'is_active': is_active,
                }
            })

        # Обновляем slug если изменилось название
        if name != category.name:
            base_slug = slugify(unidecode(name))
            slug = base_slug
            counter = 1
            while SpaceCategory.objects.filter(slug=slug).exclude(pk=pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            category.slug = slug

        category.name = name
        category.icon = icon
        category.description = description
        category.is_active = is_active
        category.save()

        # Очищаем кэш категорий
        cache.delete('header_categories')

        messages.success(request, f'Категория "{name}" успешно обновлена')
        return redirect('manage_categories')

    return render(request, 'categories/edit.html', {
        'category': category,
        'form_data': {
            'name': category.name,
            'icon': category.icon,
            'description': category.description,
            'is_active': category.is_active,
        }
    })


@login_required
def delete_category(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Удаление категории помещений.
    """
    if not request.user.can_moderate:
        messages.error(request, 'У вас нет прав для удаления категорий')
        return redirect('dashboard')

    category = get_object_or_404(SpaceCategory, pk=pk)

    if request.method == 'POST':
        # Проверяем, есть ли помещения с этой категорией
        spaces_count = category.spaces.count()
        if spaces_count > 0:
            messages.error(
                request,
                f'Невозможно удалить категорию "{category.name}". '
                f'К ней привязано {spaces_count} помещений. '
                'Сначала переназначьте или удалите эти помещения.'
            )
            return redirect('manage_categories')

        category_name = category.name
        category.delete()

        # Очищаем кэш категорий
        cache.delete('header_categories')

        messages.success(request, f'Категория "{category_name}" успешно удалена')

    return redirect('manage_categories')


@login_required
def toggle_category_status(request: HttpRequest, pk: int) -> JsonResponse:
    """
    AJAX: Переключение статуса активности категории.
    """
    if not request.user.can_moderate:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешён'}, status=405)

    category = get_object_or_404(SpaceCategory, pk=pk)
    category.is_active = not category.is_active
    category.save()

    # Очищаем кэш категорий
    cache.delete('header_categories')

    return JsonResponse({
        'success': True,
        'is_active': category.is_active,
        'message': f'Категория {"активирована" if category.is_active else "деактивирована"}'
    })
