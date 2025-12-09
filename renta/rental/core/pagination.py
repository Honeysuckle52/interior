"""
====================================================================
ЦЕНТРАЛИЗОВАННАЯ ПАГИНАЦИЯ
====================================================================
Единая точка для пагинации во всех представлениях.
====================================================================
"""

from __future__ import annotations

from typing import Optional

from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet
from django.http import HttpRequest


# Константы пагинации
DEFAULT_PAGE_SIZE: int = 12
MAX_PAGE_SIZE: int = 100
MIN_PAGE_SIZE: int = 5


def paginate(
    queryset: QuerySet,
    request: HttpRequest,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_param: str = 'page',
    per_page_param: str = 'per_page'
) -> tuple[Page, Paginator]:
    """
    Унифицированная пагинация queryset.

    Args:
        queryset: QuerySet для пагинации
        request: HTTP запрос
        page_size: Размер страницы по умолчанию
        page_param: Имя параметра для номера страницы
        per_page_param: Имя параметра для размера страницы

    Returns:
        Кортеж (Page объект, Paginator объект)
    """
    # Получаем размер страницы из параметров запроса
    try:
        per_page = int(request.GET.get(per_page_param, page_size))
        per_page = max(MIN_PAGE_SIZE, min(per_page, MAX_PAGE_SIZE))
    except (ValueError, TypeError):
        per_page = page_size

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param, 1)

    try:
        page = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page = paginator.get_page(1)

    return page, paginator


class PaginationMixin:
    """
    Миксин для class-based views с пагинацией.

    Атрибуты:
        default_page_size: Размер страницы по умолчанию
        max_page_size: Максимальный размер страницы
        page_param: Имя параметра номера страницы
        per_page_param: Имя параметра размера страницы
    """

    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE
    page_param: str = 'page'
    per_page_param: str = 'per_page'

    def paginate_queryset(
        self,
        queryset: QuerySet,
        page_size: Optional[int] = None
    ) -> tuple[Page, Paginator]:
        """
        Пагинация queryset.

        Args:
            queryset: QuerySet для пагинации
            page_size: Размер страницы (опционально)

        Returns:
            Кортеж (Page, Paginator)
        """
        return paginate(
            queryset,
            self.request,
            page_size or self.default_page_size,
            self.page_param,
            self.per_page_param
        )
