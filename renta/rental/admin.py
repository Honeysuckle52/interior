"""
АДМИН-ПАНЕЛЬ ООО "ИНТЕРЬЕР"
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from typing import Any, Optional

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Avg, Sum, QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CustomUser, UserProfile, Region, City, SpaceCategory,
    PricingPeriod, Space, SpaceImage, SpacePrice,
    BookingStatus, Booking, TransactionStatus, Transaction,
    Review, Favorite, ActionLog
)
from .forms import AdminUserCreationForm, AdminUserChangeForm
from .services.logging_service import LoggingService


# ============== КАСТОМНЫЙ ADMIN SITE ==============

class InteriorAdminSite(AdminSite):
    """Кастомный AdminSite с отчётами"""

    site_header = 'ООО "ИНТЕРЬЕР" - Администрирование'
    site_title = 'ИНТЕРЬЕР Admin'
    index_title = 'Панель управления'

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
        """Страница отчётов"""
        thirty_days_ago = timezone.now() - timedelta(days=30)

        context = {
            **self.each_context(request),
            'title': 'Отчёты и аналитика',
            'stats': {
                'total_users': CustomUser.objects.count(),
                'new_users_month': CustomUser.objects.filter(created_at__gte=thirty_days_ago).count(),
                'total_spaces': Space.objects.count(),
                'active_spaces': Space.objects.filter(is_active=True).count(),
                'total_bookings': Booking.objects.count(),
                'bookings_month': Booking.objects.filter(created_at__gte=thirty_days_ago).count(),
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
        """Журнал действий"""
        user_id = request.GET.get('user')
        action_type = request.GET.get('action_type')
        model_name = request.GET.get('model')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        logs = ActionLog.objects.select_related('user').order_by('-created_at')

        if user_id:
            logs = logs.filter(user_id=user_id)
        if action_type:
            logs = logs.filter(action_type=action_type)
        if model_name:
            logs = logs.filter(model_name__icontains=model_name)
        if date_from:
            try:
                logs = logs.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
            except ValueError:
                pass
        if date_to:
            try:
                logs = logs.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
            except ValueError:
                pass

        from django.core.paginator import Paginator
        paginator = Paginator(logs, 50)
        logs_page = paginator.get_page(request.GET.get('page', 1))

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
        """Экспорт в JSON"""
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
        response['Content-Disposition'] = f'attachment; filename="report_{report_type}_{timezone.now():%Y%m%d_%H%M%S}.json"'
        return response

    def export_csv_view(self, request: HttpRequest) -> HttpResponse:
        """Экспорт в CSV"""
        report_type = request.GET.get('type', 'actions')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')
        response['Content-Disposition'] = f'attachment; filename="report_{report_type}_{timezone.now():%Y%m%d_%H%M%S}.csv"'

        writer = csv.writer(response)

        if report_type == 'actions':
            writer.writerow(['Дата', 'Пользователь', 'Действие', 'Модель', 'Объект', 'IP'])
            for log in self._get_actions_queryset(date_from, date_to):
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
            for b in self._get_bookings_queryset(date_from, date_to):
                writer.writerow([
                    b.id, b.space.title, b.tenant.username,
                    b.status.name, float(b.total_amount),
                    b.created_at.strftime('%d.%m.%Y %H:%M')
                ])

        return response

    def dashboard_view(self, request: HttpRequest) -> TemplateResponse:
        """Аналитический дашборд"""
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        bookings_by_day = []
        revenue_by_day = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            bookings_by_day.append({
                'date': date.strftime('%d.%m'),
                'count': Booking.objects.filter(created_at__date=date).count()
            })
            revenue_by_day.append({
                'date': date.strftime('%d.%m'),
                'amount': float(Booking.objects.filter(
                    created_at__date=date,
                    status__code__in=['confirmed', 'completed']
                ).aggregate(total=Sum('total_amount'))['total'] or 0)
            })

        top_spaces = Space.objects.annotate(
            bookings_count=Count('bookings'),
            revenue=Sum('bookings__total_amount')
        ).order_by('-bookings_count')[:5]

        status_distribution = list(Booking.objects.values('status__name', 'status__color').annotate(count=Count('id')))

        context = {
            **self.each_context(request),
            'title': 'Аналитический дашборд',
            'bookings_by_day': json.dumps(bookings_by_day),
            'revenue_by_day': json.dumps(revenue_by_day),
            'top_spaces': top_spaces,
            'status_distribution': status_distribution,
        }
        return TemplateResponse(request, 'admin/reports/dashboard.html', context)

    def _get_actions_queryset(self, date_from: Optional[str], date_to: Optional[str]) -> QuerySet:
        """QuerySet действий с фильтрацией"""
        logs = ActionLog.objects.select_related('user').order_by('-created_at')
        if date_from:
            try:
                logs = logs.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
            except ValueError:
                pass
        if date_to:
            try:
                logs = logs.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
            except ValueError:
                pass
        return logs

    def _get_bookings_queryset(self, date_from: Optional[str], date_to: Optional[str]) -> QuerySet:
        """QuerySet бронирований с фильтрацией"""
        bookings = Booking.objects.select_related('space', 'tenant', 'status').order_by('-created_at')
        if date_from:
            try:
                bookings = bookings.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
            except ValueError:
                pass
        if date_to:
            try:
                bookings = bookings.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
            except ValueError:
                pass
        return bookings

    def _get_actions_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Данные действий для экспорта"""
        logs = self._get_actions_queryset(date_from, date_to)[:1000]
        return {
            'report_type': 'actions',
            'generated_at': timezone.now().isoformat(),
            'total_count': logs.count(),
            'data': [{
                'id': log.id,
                'user': log.user.username if log.user else None,
                'action_type': log.action_type,
                'model_name': log.model_name,
                'object_id': log.object_id,
                'object_repr': log.object_repr,
                'changes': log.changes,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat(),
            } for log in logs]
        }

    def _get_bookings_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Данные бронирований для экспорта"""
        bookings = self._get_bookings_queryset(date_from, date_to)
        return {
            'report_type': 'bookings',
            'generated_at': timezone.now().isoformat(),
            'total_count': bookings.count(),
            'data': [{
                'id': b.id,
                'space': b.space.title,
                'tenant': b.tenant.username,
                'status': b.status.name,
                'start_datetime': b.start_datetime.isoformat(),
                'end_datetime': b.end_datetime.isoformat(),
                'total_amount': float(b.total_amount),
                'created_at': b.created_at.isoformat(),
            } for b in bookings]
        }

    def _get_revenue_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        """Данные доходов для экспорта"""
        bookings = self._get_bookings_queryset(date_from, date_to).filter(status__code__in=['confirmed', 'completed'])

        total = bookings.aggregate(total_amount=Sum('total_amount'), count=Count('id'))
        by_status = list(bookings.values('status__name').annotate(total=Sum('total_amount'), count=Count('id')))
        by_space = list(bookings.values('space__title').annotate(total=Sum('total_amount'), count=Count('id')).order_by('-total')[:10])

        return {
            'report_type': 'revenue',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_revenue': float(total['total_amount'] or 0),
                'bookings_count': total['count'] or 0,
            },
            'by_status': by_status,
            'top_spaces': by_space,
        }


admin_site = InteriorAdminSite(name='interior_admin')


# ============== МИКСИН ЛОГИРОВАНИЯ ==============

class LoggingAdminMixin:
    """Миксин логирования действий в админке"""

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        """Сохранение с логированием"""
        super().save_model(request, obj, form, change)

        action_type = ActionLog.ActionType.UPDATE if change else ActionLog.ActionType.CREATE
        changes = {}

        if change and form.changed_data:
            for field in form.changed_data:
                old_value = form.initial.get(field)
                new_value = form.cleaned_data.get(field)
                changes[field] = {'old': str(old_value) if old_value else None, 'new': str(new_value) if new_value else None}

        LoggingService.log_action(
            user=request.user,
            action_type=action_type,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj),
            changes=changes,
            request=request
        )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        """Удаление с логированием"""
        LoggingService.log_action(
            user=request.user,
            action_type=ActionLog.ActionType.DELETE,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj),
            request=request
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Массовое удаление с логированием"""
        for obj in queryset:
            LoggingService.log_action(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                model_name=obj.__class__.__name__,
                object_id=obj.pk,
                object_repr=str(obj),
                request=request
            )
        super().delete_queryset(request, queryset)


# ============== ИНЛАЙНЫ ==============

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


# ============== АДМИНКИ МОДЕЛЕЙ ==============

@admin.register(CustomUser, site=admin_site)
class CustomUserAdmin(LoggingAdminMixin, UserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm

    list_display = ['username', 'email', 'get_full_name_display', 'user_type', 'phone', 'is_active', 'get_bookings_count', 'created_at']
    list_filter = ['user_type', 'is_active', 'is_staff', 'created_at']
    search_fields = ['username', 'email', 'phone', 'first_name', 'last_name', 'company']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    inlines = [UserProfileInline, BookingInline]

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'email')}),
        ('Информация о клиенте', {'fields': ('user_type', 'phone', 'company', 'avatar', 'email_verified'), 'classes': ('wide',)}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'), 'classes': ('collapse',)}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('username', 'email', 'password1', 'password2')}),
        ('Дополнительно', {'fields': ('user_type', 'phone'), 'classes': ('wide',)}),
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


@admin.register(Region, site=admin_site)
class RegionAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'is_active', 'cities_count']
    list_filter = ['is_active']
    search_fields = ['name']

    @admin.display(description='Городов')
    def cities_count(self, obj):
        return obj.cities.count()


@admin.register(City, site=admin_site)
class CityAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'region', 'is_active', 'spaces_count']
    list_filter = ['is_active', 'region']
    search_fields = ['name']

    @admin.display(description='Помещений')
    def spaces_count(self, obj):
        return obj.spaces.count()


@admin.register(SpaceCategory, site=admin_site)
class SpaceCategoryAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'spaces_count']
    list_filter = ['is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='Помещений')
    def spaces_count(self, obj):
        return obj.spaces.count()


@admin.register(PricingPeriod, site=admin_site)
class PricingPeriodAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'hours_count', 'description', 'is_active']
    list_filter = ['is_active']


@admin.register(Space, site=admin_site)
class SpaceAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['title', 'owner', 'city', 'category', 'area', 'is_active', 'views_count', 'created_at']
    list_filter = ['is_active', 'is_featured', 'category', 'city']
    search_fields = ['title', 'description', 'address']
    date_hierarchy = 'created_at'
    prepopulated_fields = {'slug': ('title',)}


@admin.register(BookingStatus, site=admin_site)
class BookingStatusAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['name', 'code', 'color', 'sort_order']
    list_editable = ['sort_order']


@admin.register(Booking, site=admin_site)
class BookingAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'space', 'tenant', 'status', 'start_datetime', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['space__title', 'tenant__username']
    date_hierarchy = 'created_at'


@admin.register(Review, site=admin_site)
class ReviewAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ['space', 'author', 'rating', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'rating', 'created_at']
    actions = ['approve_reviews']

    @admin.action(description='Одобрить отзывы')
    def approve_reviews(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} отзывов одобрено')


@admin.register(ActionLog, site=admin_site)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action_type', 'model_name', 'object_repr', 'ip_address']
    list_filter = ['action_type', 'model_name', 'created_at']
    search_fields = ['user__username', 'object_repr', 'ip_address']
    date_hierarchy = 'created_at'
    readonly_fields = ['user', 'action_type', 'model_name', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent', 'created_at']

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return request.user.is_superuser
