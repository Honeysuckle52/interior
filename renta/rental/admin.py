"""
НАСТРОЙКА АДМИН-ПАНЕЛИ ДЛЯ САЙТА АРЕНДЫ ООО "ИНТЕРЬЕР"
С системой отчетности и логирования действий
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Optional

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Avg, Sum, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    CustomUser, UserProfile, Region, City, SpaceCategory,
    PricingPeriod, Space, SpaceImage, SpacePrice,
    BookingStatus, Booking, TransactionStatus, Transaction,
    Review, Favorite, ActionLog
)


# ============== КАСТОМНЫЙ ADMIN SITE С ОТЧЕТАМИ ==============

class InteriorAdminSite(AdminSite):
    """Кастомный AdminSite с дополнительными страницами отчетов."""

    site_header = 'ООО "ИНТЕРЬЕР" - Администрирование'
    site_title = 'ИНТЕРЬЕР Admin'
    index_title = 'Панель управления сайтом аренды помещений'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reports/', self.admin_view(self.reports_view), name='reports'),
            path('reports/actions/', self.admin_view(self.action_logs_view), name='action_logs'),
            path('reports/export/json/', self.admin_view(self.export_json_view), name='export_json'),
            path('reports/export/csv/', self.admin_view(self.export_csv_view), name='export_csv'),
            path('reports/dashboard/', self.admin_view(self.dashboard_view), name='reports_dashboard'),
        ]
        return custom_urls + urls

    def reports_view(self, request: HttpRequest) -> TemplateResponse:
        """Главная страница отчетов."""
        # Статистика за последние 30 дней
        thirty_days_ago = timezone.now() - timedelta(days=30)

        context = {
            **self.each_context(request),
            'title': 'Отчеты и аналитика',
            'stats': {
                'total_users': CustomUser.objects.count(),
                'new_users_month': CustomUser.objects.filter(
                    created_at__gte=thirty_days_ago
                ).count(),
                'total_spaces': Space.objects.count(),
                'active_spaces': Space.objects.filter(is_active=True).count(),
                'total_bookings': Booking.objects.count(),
                'bookings_month': Booking.objects.filter(
                    created_at__gte=thirty_days_ago
                ).count(),
                'revenue_month': Booking.objects.filter(
                    created_at__gte=thirty_days_ago,
                    status__code__in=['confirmed', 'completed']
                ).aggregate(total=Sum('total_amount'))['total'] or 0,
                'total_reviews': Review.objects.count(),
                'pending_reviews': Review.objects.filter(is_approved=False).count(),
            },
            'recent_actions': ActionLog.objects.select_related('user')[:20],
        }
        return TemplateResponse(request, 'admin/reports/index.html', context)

    def action_logs_view(self, request: HttpRequest) -> TemplateResponse:
        """Страница журнала действий с фильтрацией."""
        # Получаем параметры фильтрации
        user_id = request.GET.get('user')
        action_type = request.GET.get('action_type')
        model_name = request.GET.get('model')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        logs = ActionLog.objects.select_related('user').order_by('-created_at')

        # Применяем фильтры
        if user_id:
            logs = logs.filter(user_id=user_id)
        if action_type:
            logs = logs.filter(action_type=action_type)
        if model_name:
            logs = logs.filter(model_name__icontains=model_name)
        if date_from:
            try:
                dt = datetime.strptime(date_from, '%Y-%m-%d')
                logs = logs.filter(created_at__date__gte=dt.date())
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d')
                logs = logs.filter(created_at__date__lte=dt.date())
            except ValueError:
                pass

        # Пагинация
        from django.core.paginator import Paginator
        paginator = Paginator(logs, 50)
        page = request.GET.get('page', 1)
        logs_page = paginator.get_page(page)

        context = {
            **self.each_context(request),
            'title': 'Журнал действий',
            'logs': logs_page,
            'users': CustomUser.objects.all(),
            'action_types': ActionLog.ActionType.choices,
            'filters': {
                'user': user_id,
                'action_type': action_type,
                'model': model_name,
                'date_from': date_from,
                'date_to': date_to,
            },
        }
        return TemplateResponse(request, 'admin/reports/action_logs.html', context)

    def export_json_view(self, request: HttpRequest) -> HttpResponse:
        """Экспорт отчета в JSON."""
        report_type = request.GET.get('type', 'actions')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if report_type == 'actions':
            data = self._get_actions_export_data(date_from, date_to)
        elif report_type == 'bookings':
            data = self._get_bookings_export_data(date_from, date_to)
        elif report_type == 'revenue':
            data = self._get_revenue_export_data(date_from, date_to)
        else:
            data = {'error': 'Unknown report type'}

        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            content_type='application/json; charset=utf-8'
        )
        filename = f'report_{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def export_csv_view(self, request: HttpRequest) -> HttpResponse:
        """Экспорт отчета в CSV."""
        report_type = request.GET.get('type', 'actions')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')  # BOM для Excel
        filename = f'report_{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)

        if report_type == 'actions':
            writer.writerow(['Дата', 'Пользователь', 'Действие', 'Модель', 'Объект', 'IP'])
            logs = self._get_actions_queryset(date_from, date_to)
            for log in logs:
                writer.writerow([
                    log.created_at.strftime('%d.%m.%Y %H:%M'),
                    log.user.username if log.user else 'Аноним',
                    log.get_action_type_display(),
                    log.model_name,
                    log.object_repr,
                    log.ip_address or '-'
                ])
        elif report_type == 'bookings':
            writer.writerow(['ID', 'Помещение', 'Клиент', 'Статус', 'Сумма', 'Дата'])
            bookings = self._get_bookings_queryset(date_from, date_to)
            for b in bookings:
                writer.writerow([
                    b.id,
                    b.space.title,
                    b.tenant.username,
                    b.status.name,
                    float(b.total_amount),
                    b.created_at.strftime('%d.%m.%Y %H:%M')
                ])

        return response

    def dashboard_view(self, request: HttpRequest) -> TemplateResponse:
        """Дашборд с графиками и аналитикой."""
        # Данные за последние 30 дней
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        # Бронирования по дням
        bookings_by_day = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            count = Booking.objects.filter(created_at__date=date).count()
            bookings_by_day.append({
                'date': date.strftime('%d.%m'),
                'count': count
            })

        # Доход по дням
        revenue_by_day = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            total = Booking.objects.filter(
                created_at__date=date,
                status__code__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            revenue_by_day.append({
                'date': date.strftime('%d.%m'),
                'amount': float(total)
            })

        # Топ помещений
        top_spaces = Space.objects.annotate(
            bookings_count=Count('bookings'),
            revenue=Sum('bookings__total_amount')
        ).order_by('-bookings_count')[:5]

        # Статусы бронирований
        status_distribution = Booking.objects.values(
            'status__name', 'status__color'
        ).annotate(count=Count('id'))

        context = {
            **self.each_context(request),
            'title': 'Аналитический дашборд',
            'bookings_by_day': json.dumps(bookings_by_day),
            'revenue_by_day': json.dumps(revenue_by_day),
            'top_spaces': top_spaces,
            'status_distribution': list(status_distribution),
        }
        return TemplateResponse(request, 'admin/reports/dashboard.html', context)

    def _get_actions_queryset(self, date_from: Optional[str], date_to: Optional[str]) -> QuerySet:
        """Получить QuerySet действий с фильтрацией по датам."""
        logs = ActionLog.objects.select_related('user').order_by('-created_at')
        if date_from:
            try:
                dt = datetime.strptime(date_from, '%Y-%m-%d')
                logs = logs.filter(created_at__date__gte=dt.date())
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d')
                logs = logs.filter(created_at__date__lte=dt.date())
            except ValueError:
                pass
        return logs

    def _get_bookings_queryset(self, date_from: Optional[str], date_to: Optional[str]) -> QuerySet:
        """Получить QuerySet бронирований с фильтрацией по датам."""
        bookings = Booking.objects.select_related(
            'space', 'tenant', 'status'
        ).order_by('-created_at')
        if date_from:
            try:
                dt = datetime.strptime(date_from, '%Y-%m-%d')
                bookings = bookings.filter(created_at__date__gte=dt.date())
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d')
                bookings = bookings.filter(created_at__date__lte=dt.date())
            except ValueError:
                pass
        return bookings

    def _get_actions_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Подготовить данные действий для экспорта."""
        logs = self._get_actions_queryset(date_from, date_to)[:1000]
        return {
            'report_type': 'actions',
            'generated_at': timezone.now().isoformat(),
            'total_count': logs.count(),
            'data': [
                {
                    'id': log.id,
                    'user': log.user.username if log.user else None,
                    'action_type': log.action_type,
                    'model_name': log.model_name,
                    'object_id': log.object_id,
                    'object_repr': log.object_repr,
                    'changes': log.changes,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at.isoformat(),
                }
                for log in logs
            ]
        }

    def _get_bookings_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Подготовить данные бронирований для экспорта."""
        bookings = self._get_bookings_queryset(date_from, date_to)
        return {
            'report_type': 'bookings',
            'generated_at': timezone.now().isoformat(),
            'total_count': bookings.count(),
            'data': [
                {
                    'id': b.id,
                    'space': b.space.title,
                    'tenant': b.tenant.username,
                    'status': b.status.name,
                    'start_datetime': b.start_datetime.isoformat(),
                    'end_datetime': b.end_datetime.isoformat(),
                    'total_amount': float(b.total_amount),
                    'created_at': b.created_at.isoformat(),
                }
                for b in bookings
            ]
        }

    def _get_revenue_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Подготовить данные по доходам для экспорта."""
        bookings = self._get_bookings_queryset(date_from, date_to).filter(
            status__code__in=['confirmed', 'completed']
        )

        total = bookings.aggregate(
            total_amount=Sum('total_amount'),
            count=Count('id')
        )

        by_status = bookings.values('status__name').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        )

        by_space = bookings.values('space__title').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')[:10]

        return {
            'report_type': 'revenue',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_revenue': float(total['total_amount'] or 0),
                'bookings_count': total['count'] or 0,
            },
            'by_status': list(by_status),
            'top_spaces': list(by_space),
        }


# Создаем экземпляр кастомного AdminSite
admin_site = InteriorAdminSite(name='interior_admin')


# ============== МИКСИН ДЛЯ ЛОГИРОВАНИЯ ДЕЙСТВИЙ В АДМИНКЕ ==============

class LoggingAdminMixin:
    """Миксин для автоматического логирования действий в админке."""

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        """Сохранение с логированием."""
        super().save_model(request, obj, form, change)

        from .middleware import log_action

        action_type = ActionLog.ActionType.UPDATE if change else ActionLog.ActionType.CREATE
        changes = {}

        if change and form.changed_data:
            for field in form.changed_data:
                old_value = form.initial.get(field)
                new_value = form.cleaned_data.get(field)
                changes[field] = {
                    'old': str(old_value) if old_value else None,
                    'new': str(new_value) if new_value else None,
                }

        log_action(
            user=request.user,
            action_type=action_type,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj),
            changes=changes,
            request=request
        )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        """Удаление с логированием."""
        from .middleware import log_action

        log_action(
            user=request.user,
            action_type=ActionLog.ActionType.DELETE,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj),
            request=request
        )

        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Массовое удаление с логированием."""
        from .middleware import log_action

        for obj in queryset:
            log_action(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                model_name=obj.__class__.__name__,
                object_id=obj.pk,
                object_repr=str(obj),
                request=request
            )

        super().delete_queryset(request, queryset)


# ============== ПОЛЬЗОВАТЕЛИ ==============

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'Дополнительная информация'
    verbose_name_plural = 'Дополнительная информация'
    fk_name = 'user'


class BookingInline(admin.TabularInline):
    model = Booking
    fk_name = 'tenant'
    extra = 0
    readonly_fields = ['space', 'status', 'start_datetime', 'total_amount', 'created_at']
    fields = ['space', 'status', 'start_datetime', 'total_amount', 'created_at']
    can_delete = False
    max_num = 5
    verbose_name = 'Последнее бронирование'
    verbose_name_plural = 'Последние бронирования'

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(CustomUser, site=admin_site)
class CustomUserAdmin(LoggingAdminMixin, UserAdmin):
    list_display = [
        'username', 'email', 'get_full_name_display', 'user_type',
        'phone', 'is_active', 'get_bookings_count', 'created_at'
    ]
    list_filter = ['user_type', 'is_active', 'is_staff', 'created_at']
    search_fields = ['username', 'email', 'phone', 'first_name', 'last_name', 'company']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    inlines = [UserProfileInline, BookingInline]

    fieldsets = UserAdmin.fieldsets + (
        ('Информация о клиенте', {
            'fields': ('user_type', 'phone', 'company', 'avatar', 'email_verified'),
            'classes': ('wide',)
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительно', {
            'fields': ('email', 'user_type', 'phone'),
            'classes': ('wide',)
        }),
    )

    actions = ['make_owner', 'make_client', 'deactivate_users']

    @admin.display(description='ФИО')
    def get_full_name_display(self, obj: CustomUser) -> str:
        return obj.get_full_name() or '-'

    @admin.display(description='Бронирований')
    def get_bookings_count(self, obj: CustomUser) -> str:
        count = obj.bookings.count()
        return format_html('<b>{}</b>', count) if count > 0 else '0'

    @admin.action(description='Сделать владельцами')
    def make_owner(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(user_type=CustomUser.UserType.OWNER)
        self.message_user(request, f'{updated} пользователей стали владельцами')

    @admin.action(description='Сделать клиентами')
    def make_client(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(user_type=CustomUser.UserType.CLIENT)
        self.message_user(request, f'{updated} пользователей стали клиентами')

    @admin.action(description='Деактивировать')
    def deactivate_users(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} пользователей деактивировано')


# ============== СПРАВОЧНИКИ ==============

@admin.register(Region, site=admin_site)
class RegionAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'code', 'get_cities_count']
    search_fields = ['name', 'code']
    ordering = ['name']

    @admin.display(description='Городов')
    def get_cities_count(self, obj: Region) -> int:
        return obj.cities.count()


@admin.register(City, site=admin_site)
class CityAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'region', 'is_active', 'get_spaces_count']
    list_filter = ['region', 'is_active']
    search_fields = ['name', 'region__name']
    list_editable = ['is_active']
    ordering = ['name']

    @admin.display(description='Помещений')
    def get_spaces_count(self, obj: City) -> str:
        count = obj.spaces.filter(is_active=True).count()
        return format_html('<b>{}</b>', count) if count > 0 else '0'


@admin.register(SpaceCategory, site=admin_site)
class SpaceCategoryAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon_preview', 'is_active', 'get_spaces_count']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['is_active']
    list_editable = ['is_active']
    search_fields = ['name']

    @admin.display(description='Иконка')
    def icon_preview(self, obj: SpaceCategory) -> str:
        return format_html('<i class="fas {}"></i> {}', obj.icon, obj.icon)

    @admin.display(description='Помещений')
    def get_spaces_count(self, obj: SpaceCategory) -> int:
        return obj.spaces.filter(is_active=True).count()


@admin.register(PricingPeriod, site=admin_site)
class PricingPeriodAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'description', 'hours_count', 'sort_order']
    list_editable = ['sort_order']
    ordering = ['sort_order']


# ============== ПОМЕЩЕНИЯ ==============

class SpaceImageInline(admin.TabularInline):
    model = SpaceImage
    extra = 1
    fields = ['image', 'image_preview', 'alt_text', 'is_primary', 'sort_order']
    readonly_fields = ['image_preview']
    ordering = ['-is_primary', 'sort_order']

    @admin.display(description='Превью')
    def image_preview(self, obj: SpaceImage) -> str:
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 60px; object-fit: cover;"/>',
                obj.image.url
            )
        return '-'


class SpacePriceInline(admin.TabularInline):
    model = SpacePrice
    extra = 0
    fields = ['period', 'price', 'is_active', 'min_periods', 'max_periods']
    ordering = ['period__sort_order']


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ['author', 'rating', 'comment', 'is_approved', 'created_at']
    fields = ['author', 'rating', 'comment', 'is_approved', 'created_at']
    can_delete = True
    max_num = 10


@admin.register(Space, site=admin_site)
class SpaceAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = [
        'title', 'city', 'category', 'area_sqm', 'max_capacity',
        'get_min_price_display', 'is_active', 'is_featured',
        'views_count', 'get_bookings_count', 'created_at'
    ]
    list_filter = ['city__region', 'city', 'category', 'is_active', 'is_featured', 'created_at']
    search_fields = ['title', 'address', 'description', 'owner__username']
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ['is_active', 'is_featured']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    inlines = [SpaceImageInline, SpacePriceInline, ReviewInline]
    readonly_fields = ['views_count', 'created_at', 'updated_at', 'get_stats']

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'slug', 'category', 'owner')
        }),
        ('Местоположение', {
            'fields': ('city', 'address')
        }),
        ('Характеристики', {
            'fields': ('area_sqm', 'max_capacity', 'description')
        }),
        ('Настройки', {
            'fields': ('is_active', 'is_featured'),
            'classes': ('wide',)
        }),
        ('Статистика', {
            'fields': ('views_count', 'get_stats', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['make_featured', 'remove_featured', 'activate_spaces', 'deactivate_spaces']

    @admin.display(description='Цена')
    def get_min_price_display(self, obj: Space) -> str:
        price = obj.get_min_price()
        if price:
            return format_html('от <b>{} ₽</b>/{}', int(price.price), price.period.name)
        return '-'

    @admin.display(description='Брони')
    def get_bookings_count(self, obj: Space) -> int:
        return obj.bookings.count()

    @admin.display(description='Статистика')
    def get_stats(self, obj: Space) -> str:
        stats = obj.reviews.filter(is_approved=True).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        revenue = obj.bookings.filter(
            status__code='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        return format_html(
            '<div>Отзывов: {} | Рейтинг: {} | Доход: {} ₽</div>',
            stats['count'] or 0,
            round(stats['avg_rating'] or 0, 1),
            int(revenue)
        )

    @admin.action(description='Сделать рекомендуемыми')
    def make_featured(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} помещений добавлено в рекомендуемые')

    @admin.action(description='Убрать из рекомендуемых')
    def remove_featured(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} помещений убрано из рекомендуемых')

    @admin.action(description='Активировать')
    def activate_spaces(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} помещений активировано')

    @admin.action(description='Деактивировать')
    def deactivate_spaces(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} помещений деактивировано')


@admin.register(SpaceImage, site=admin_site)
class SpaceImageAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['space', 'image_preview', 'is_primary', 'sort_order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['space__title', 'alt_text']
    list_editable = ['is_primary', 'sort_order']

    @admin.display(description='Фото')
    def image_preview(self, obj: SpaceImage) -> str:
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 80px; max-height: 50px; object-fit: cover;"/>',
                obj.image.url
            )
        return '-'


# ============== БРОНИРОВАНИЯ ==============

@admin.register(BookingStatus, site=admin_site)
class BookingStatusAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['code', 'name', 'color_preview', 'sort_order']
    list_editable = ['sort_order']
    ordering = ['sort_order']

    @admin.display(description='Вид')
    def color_preview(self, obj: BookingStatus) -> str:
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            obj.color, obj.name
        )


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ['status', 'amount', 'payment_method', 'external_id', 'created_at']
    can_delete = False


@admin.register(Booking, site=admin_site)
class BookingAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = [
        'id', 'space', 'tenant', 'status_badge', 'period',
        'start_datetime', 'end_datetime', 'total_amount_display', 'created_at'
    ]
    list_filter = ['status', 'period', 'created_at', 'space__city']
    search_fields = ['space__title', 'tenant__username', 'tenant__email', 'id']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    inlines = [TransactionInline]

    fieldsets = (
        ('Бронирование', {
            'fields': ('space', 'tenant', 'status')
        }),
        ('Период аренды', {
            'fields': ('period', 'periods_count', 'start_datetime', 'end_datetime')
        }),
        ('Стоимость', {
            'fields': ('price_per_period', 'total_amount')
        }),
        ('Дополнительно', {
            'fields': ('comment', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['confirm_bookings', 'cancel_bookings', 'complete_bookings']

    @admin.display(description='Статус')
    def status_badge(self, obj: Booking) -> str:
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            obj.status.color, obj.status.name
        )

    @admin.display(description='Сумма')
    def total_amount_display(self, obj: Booking) -> str:
        return format_html('<b>{} ₽</b>', int(obj.total_amount))

    @admin.action(description='Подтвердить бронирования')
    def confirm_bookings(self, request: HttpRequest, queryset: QuerySet) -> None:
        confirmed_status = BookingStatus.objects.filter(code='confirmed').first()
        if confirmed_status:
            updated = queryset.filter(status__code='pending').update(status=confirmed_status)
            self.message_user(request, f'{updated} бронирований подтверждено')
        else:
            self.message_user(request, 'Статус "Подтверждено" не найден', level=messages.ERROR)

    @admin.action(description='Отменить бронирования')
    def cancel_bookings(self, request: HttpRequest, queryset: QuerySet) -> None:
        cancelled_status = BookingStatus.objects.filter(code='cancelled').first()
        if cancelled_status:
            updated = queryset.exclude(status__code__in=['cancelled', 'completed']).update(status=cancelled_status)
            self.message_user(request, f'{updated} бронирований отменено')
        else:
            self.message_user(request, 'Статус "Отменено" не найден', level=messages.ERROR)

    @admin.action(description='Завершить бронирования')
    def complete_bookings(self, request: HttpRequest, queryset: QuerySet) -> None:
        completed_status = BookingStatus.objects.filter(code='completed').first()
        if completed_status:
            updated = queryset.filter(status__code='confirmed').update(status=completed_status)
            self.message_user(request, f'{updated} бронирований завершено')
        else:
            self.message_user(request, 'Статус "Завершено" не найден', level=messages.ERROR)


# ============== ТРАНЗАКЦИИ ==============

@admin.register(TransactionStatus, site=admin_site)
class TransactionStatusAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['code', 'name']


@admin.register(Transaction, site=admin_site)
class TransactionAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'booking', 'status', 'amount_display', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['booking__id', 'external_id']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']

    @admin.display(description='Сумма')
    def amount_display(self, obj: Transaction) -> str:
        return format_html('<b>{} ₽</b>', int(obj.amount))


# ============== ОТЗЫВЫ И ИЗБРАННОЕ ==============

@admin.register(Review, site=admin_site)
class ReviewAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['space', 'author', 'rating_display', 'comment_short', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['space__title', 'author__username', 'comment']
    list_editable = ['is_approved']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    actions = ['approve_reviews', 'reject_reviews']

    @admin.display(description='Рейтинг')
    def rating_display(self, obj: Review) -> str:
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #ffc107;">{}</span>', stars)

    @admin.display(description='Комментарий')
    def comment_short(self, obj: Review) -> str:
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment

    @admin.action(description='Одобрить выбранные отзывы')
    def approve_reviews(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'Одобрено {updated} отзывов')

    @admin.action(description='Отклонить выбранные отзывы')
    def reject_reviews(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'Отклонено {updated} отзывов')


@admin.register(Favorite, site=admin_site)
class FavoriteAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['user', 'space', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'space__title']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']


# ============== ЖУРНАЛ ДЕЙСТВИЙ ==============

@admin.register(ActionLog, site=admin_site)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action_type_badge', 'model_name', 'object_repr_short', 'ip_address']
    list_filter = ['action_type', 'model_name', 'created_at']
    search_fields = ['user__username', 'model_name', 'object_repr', 'ip_address']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = [
        'user', 'action_type', 'model_name', 'object_id', 'object_repr',
        'changes_display', 'ip_address', 'user_agent', 'created_at'
    ]

    fieldsets = (
        ('Информация о действии', {
            'fields': ('user', 'action_type', 'created_at')
        }),
        ('Объект', {
            'fields': ('model_name', 'object_id', 'object_repr')
        }),
        ('Изменения', {
            'fields': ('changes_display',),
            'classes': ('collapse',)
        }),
        ('Технические данные', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return request.user.is_superuser

    @admin.display(description='Тип действия')
    def action_type_badge(self, obj: ActionLog) -> str:
        colors = {
            'create': 'success',
            'update': 'primary',
            'delete': 'danger',
            'view': 'info',
            'login': 'success',
            'logout': 'secondary',
            'other': 'warning',
        }
        color = colors.get(obj.action_type, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_action_type_display()
        )

    @admin.display(description='Объект')
    def object_repr_short(self, obj: ActionLog) -> str:
        text = obj.object_repr
        return text[:50] + '...' if len(text) > 50 else text

    @admin.display(description='Изменения')
    def changes_display(self, obj: ActionLog) -> str:
        if not obj.changes:
            return '-'
        formatted = json.dumps(obj.changes, ensure_ascii=False, indent=2)
        return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted)
