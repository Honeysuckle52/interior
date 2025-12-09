"""
НАСТРОЙКА АДМИН-ПАНЕЛИ ДЛЯ САЙТА АРЕНДЫ ООО "ИНТЕРЬЕР"
С системой отчетности, логирования, PDF экспортом и бэкапом БД
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from typing import Any, Optional

from django.contrib import admin, messages
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from django.conf import settings
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
from .forms import AdminUserCreationForm, AdminUserChangeForm


# ============== LOGGING MIXIN ДЛЯ АВТОМАТИЧЕСКОГО ЛОГИРОВАНИЯ ==============

class LoggingAdminMixin:
    """Миксин для автоматического логирования действий в админке."""

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        super().save_model(request, obj, form, change)
        ActionLog.objects.create(
            user=request.user,
            action_type=ActionLog.ActionType.UPDATE if change else ActionLog.ActionType.CREATE,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj)[:200],
            ip_address=request.META.get('REMOTE_ADDR')
        )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        ActionLog.objects.create(
            user=request.user,
            action_type=ActionLog.ActionType.DELETE,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj)[:200],
            ip_address=request.META.get('REMOTE_ADDR')
        )
        super().delete_model(request, obj)


# ============== КАСТОМНЫЙ ADMIN SITE С ОТЧЕТАМИ, PDF И БЭКАПОМ ==============

class InteriorAdminSite(AdminSite):
    """Кастомный AdminSite с дополнительными страницами отчетов, PDF экспортом и бэкапом."""

    site_header = 'ООО "ИНТЕРЬЕР" - Администрирование'
    site_title = 'ИНТЕРЬЕР Admin'
    index_title = 'Панель управления'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('reports/', self.admin_view(self.reports_view), name='reports'),
            path('reports/actions/', self.admin_view(self.action_logs_view), name='action_logs'),
            path('reports/export/json/', self.admin_view(self.export_json_view), name='export_json'),
            path('reports/export/pdf/', self.admin_view(self.export_pdf_view), name='export_pdf'),
            path('reports/dashboard/', self.admin_view(self.dashboard_view), name='reports_dashboard'),
            path('backup/', self.admin_view(self.backup_view), name='backup'),
            path('backup/create/', self.admin_view(self.create_backup), name='create_backup'),
            path('backup/download/<str:filename>/', self.admin_view(self.download_backup), name='download_backup'),
            path('backup/schedule/', self.admin_view(self.schedule_backup_view), name='schedule_backup'),
            path('backup/delete/<str:filename>/', self.admin_view(self.delete_backup), name='delete_backup'),
        ]
        return custom_urls + urls

    def backup_view(self, request: HttpRequest) -> TemplateResponse:
        """Страница управления бэкапами базы данных."""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        backups = []
        if os.path.exists(backup_dir):
            for filename in sorted(os.listdir(backup_dir), reverse=True):
                if filename.endswith('.json') or filename.endswith('.sql'):
                    filepath = os.path.join(backup_dir, filename)
                    stat = os.stat(filepath)
                    backups.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created': datetime.fromtimestamp(stat.st_mtime),
                    })

        context = {
            **self.each_context(request),
            'title': 'Резервное копирование',
            'backups': backups[:20],
        }
        return TemplateResponse(request, 'admin/backup/index.html', context)

    def create_backup(self, request: HttpRequest) -> HttpResponse:
        """Создание бэкапа базы данных с прямой отдачей файла в браузер."""
        if request.method != 'POST':
            return redirect('interior_admin:backup')

        download_direct = request.POST.get('download_direct', 'true') == 'true'
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        try:
            from django.core.management import call_command

            output = StringIO()
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '--indent=2',
                stdout=output,
                exclude=['contenttypes', 'auth.permission', 'sessions']
            )

            backup_content = output.getvalue()
            filename = f'backup_{timestamp}.json'

            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.OTHER,
                model_name='backup',
                object_repr=f'Создан бэкап: {filename}',
                ip_address=request.META.get('REMOTE_ADDR')
            )

            if download_direct:
                response = HttpResponse(
                    backup_content,
                    content_type='application/json'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = len(backup_content.encode('utf-8'))
                return response
            else:
                backup_dir = os.path.join(settings.BASE_DIR, 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                filepath = os.path.join(backup_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(backup_content)

                messages.success(request, f'Бэкап успешно создан и сохранён: {filename}')
                return redirect('interior_admin:backup')

        except Exception as e:
            messages.error(request, f'Ошибка создания бэкапа: {e}')
            return redirect('interior_admin:backup')

    def download_backup(self, request: HttpRequest, filename: str) -> HttpResponse:
        """Скачивание файла бэкапа напрямую в браузер."""
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        filepath = os.path.join(backup_dir, filename)

        if not os.path.abspath(filepath).startswith(os.path.abspath(backup_dir)):
            messages.error(request, 'Недопустимый путь к файлу')
            return redirect('interior_admin:backup')

        if not os.path.exists(filepath):
            messages.error(request, 'Файл не найден')
            return redirect('interior_admin:backup')

        with open(filepath, 'rb') as f:
            content = f.read()

        content_type = 'application/json' if filename.endswith('.json') else 'application/sql'

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(content)

        ActionLog.objects.create(
            user=request.user,
            action_type=ActionLog.ActionType.OTHER,
            model_name='backup',
            object_repr=f'Скачан бэкап: {filename}',
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return response

    def delete_backup(self, request: HttpRequest, filename: str) -> HttpResponse:
        """Удаление файла бэкапа."""
        if request.method != 'POST':
            return redirect('interior_admin:backup')

        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        filepath = os.path.join(backup_dir, filename)

        if not os.path.abspath(filepath).startswith(os.path.abspath(backup_dir)):
            messages.error(request, 'Недопустимый путь к файлу')
            return redirect('interior_admin:backup')

        if os.path.exists(filepath):
            os.remove(filepath)
            messages.success(request, f'Бэкап {filename} удалён')

            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                model_name='backup',
                object_repr=f'Удалён бэкап: {filename}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        else:
            messages.error(request, 'Файл не найден')

        return redirect('interior_admin:backup')

    def schedule_backup_view(self, request: HttpRequest) -> HttpResponse:
        """Создание бэкапа по расписанию (выбор времени)."""
        if request.method == 'POST':
            backup_time = request.POST.get('backup_time', 'now')

            if backup_time == 'now':
                return self.create_backup(request)
            else:
                messages.info(request, f'Бэкап будет создан в {backup_time}. '
                             f'Для автоматизации настройте Celery Beat или cron.')
                return redirect('interior_admin:backup')

        return redirect('interior_admin:backup')

    def export_pdf_view(self, request: HttpRequest) -> HttpResponse:
        """Экспорт отчета в PDF с поддержкой русского языка (DejaVuSans)."""
        report_type = request.GET.get('type', 'actions')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm, mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            font_registered = False
            font_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/TTF/DejaVuSans.ttf',
                'C:/Windows/Fonts/DejaVuSans.ttf',
                '/Library/Fonts/DejaVuSans.ttf',
                '/System/Library/Fonts/Supplemental/DejaVuSans.ttf',
                os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf'),
                os.path.join(settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf'),
            ]

            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                        bold_path = font_path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
                        if os.path.exists(bold_path):
                            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))
                        font_registered = True
                        break
                    except Exception:
                        continue

            font_name = 'DejaVuSans' if font_registered else 'Helvetica'

            buffer = BytesIO()

            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(A4),
                rightMargin=1*cm,
                leftMargin=1*cm,
                topMargin=1.5*cm,
                bottomMargin=1*cm
            )

            title_style = ParagraphStyle(
                'CustomTitle',
                fontName=font_name,
                fontSize=18,
                spaceAfter=20,
                alignment=1,
                textColor=colors.HexColor('#1a1a1a')
            )

            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                fontName=font_name,
                fontSize=10,
                spaceAfter=15,
                alignment=1,
                textColor=colors.HexColor('#666666')
            )

            normal_style = ParagraphStyle(
                'CustomNormal',
                fontName=font_name,
                fontSize=9,
            )

            elements = []

            title_text = {
                'actions': 'Отчёт по действиям пользователей',
                'bookings': 'Отчёт по бронированиям',
                'revenue': 'Отчёт по доходам',
                'users': 'Отчёт по пользователям',
                'logins': 'Отчёт по подключениям'
            }.get(report_type, 'Отчёт')

            elements.append(Paragraph(title_text, title_style))
            elements.append(Paragraph(
                f"ООО ИНТЕРЬЕР | Сгенерировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}",
                subtitle_style
            ))
            elements.append(Spacer(1, 15))

            if report_type == 'actions':
                data = self._get_pdf_actions_data(date_from, date_to)
                headers = ['Дата', 'Пользователь', 'Действие', 'Модель', 'Объект', 'IP']
            elif report_type == 'bookings':
                data = self._get_pdf_bookings_data(date_from, date_to)
                headers = ['ID', 'Помещение', 'Клиент', 'Статус', 'Сумма', 'Дата']
            elif report_type == 'revenue':
                data = self._get_pdf_revenue_data(date_from, date_to)
                headers = ['Период', 'Бронирований', 'Сумма']
            elif report_type == 'users':
                data = self._get_pdf_users_data(date_from, date_to)
                headers = ['Пользователь', 'Email', 'Тип', 'Регистрация', 'Бронирований']
            elif report_type == 'logins':
                data = self._get_pdf_logins_data(date_from, date_to)
                headers = ['Дата', 'Пользователь', 'IP адрес', 'Браузер']
            else:
                data = []
                headers = []

            if data:
                table_data = [headers] + data

                col_widths = None
                if report_type == 'actions':
                    col_widths = [3*cm, 3*cm, 2.5*cm, 2.5*cm, 8*cm, 3*cm]
                elif report_type == 'bookings':
                    col_widths = [1.5*cm, 7*cm, 4*cm, 3*cm, 3*cm, 3*cm]

                table = Table(table_data, repeatRows=1, colWidths=col_widths)

                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d4af37')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
                    ('FONTNAME', (0, 0), (-1, 0), font_name),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('TOPPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a1a1a')),
                    ('FONTNAME', (0, 1), (-1, -1), font_name),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d4af37')),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#b8941f')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))

                elements.append(table)
            else:
                elements.append(Paragraph("Нет данных для отображения", normal_style))

            doc.build(elements)

            buffer.seek(0)
            filename = f'report_{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'

            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.OTHER,
                model_name='report',
                object_repr=f'Скачан PDF отчёт: {report_type}',
                ip_address=request.META.get('REMOTE_ADDR')
            )

            return response

        except ImportError:
            messages.warning(request, 'Для генерации PDF установите: pip install reportlab')
            return redirect('interior_admin:reports')
        except Exception as e:
            messages.error(request, f'Ошибка генерации PDF: {e}')
            return redirect('interior_admin:reports')

    def _get_pdf_actions_data(self, date_from: Optional[str], date_to: Optional[str]) -> list:
        logs = self._get_actions_queryset(date_from, date_to)[:500]
        return [
            [
                log.created_at.strftime('%d.%m.%Y %H:%M'),
                log.user.username if log.user else 'Аноним',
                log.get_action_type_display(),
                log.model_name or '-',
                (log.object_repr or '-')[:40],
                log.ip_address or '-'
            ]
            for log in logs
        ]

    def _get_pdf_bookings_data(self, date_from: Optional[str], date_to: Optional[str]) -> list:
        bookings = self._get_bookings_queryset(date_from, date_to)[:500]
        return [
            [
                str(b.id),
                (b.space.title[:30] if b.space else '-'),
                (b.tenant.username[:20] if b.tenant else '-'),
                (b.status.name if b.status else '-'),
                f'{int(b.total_amount)} руб.',
                b.created_at.strftime('%d.%m.%Y')
            ]
            for b in bookings
        ]

    def _get_pdf_revenue_data(self, date_from: Optional[str], date_to: Optional[str]) -> list:
        bookings = self._get_bookings_queryset(date_from, date_to).filter(
            status__code__in=['confirmed', 'completed']
        )

        from django.db.models.functions import TruncDate
        daily = bookings.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-date')[:30]

        return [
            [
                d['date'].strftime('%d.%m.%Y') if d['date'] else '-',
                str(d['count']),
                f"{int(d['total'] or 0)} руб."
            ]
            for d in daily
        ]

    def _get_pdf_users_data(self, date_from: Optional[str], date_to: Optional[str]) -> list:
        users = CustomUser.objects.annotate(
            bookings_count=Count('bookings')
        ).order_by('-created_at')

        if date_from:
            try:
                dt = datetime.strptime(date_from, '%Y-%m-%d')
                users = users.filter(created_at__date__gte=dt.date())
            except ValueError:
                pass
        if date_to:
            try:
                dt = datetime.strptime(date_to, '%Y-%m-%d')
                users = users.filter(created_at__date__lte=dt.date())
            except ValueError:
                pass

        return [
            [
                u.username[:20],
                (u.email[:25] if u.email else '-'),
                u.get_user_type_display(),
                u.created_at.strftime('%d.%m.%Y'),
                str(u.bookings_count)
            ]
            for u in users[:200]
        ]

    def _get_pdf_logins_data(self, date_from: Optional[str], date_to: Optional[str]) -> list:
        logs = ActionLog.objects.filter(
            action_type__in=[ActionLog.ActionType.LOGIN, ActionLog.ActionType.LOGOUT]
        ).select_related('user').order_by('-created_at')

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

        return [
            [
                log.created_at.strftime('%d.%m.%Y %H:%M'),
                log.user.username if log.user else 'Аноним',
                log.ip_address or '-',
                self._parse_browser(log.user_agent)[:30]
            ]
            for log in logs[:500]
        ]

    def _parse_browser(self, user_agent: Optional[str]) -> str:
        if not user_agent:
            return '-'
        ua = user_agent
        if 'Chrome' in ua and 'Edg' not in ua:
            return 'Chrome'
        elif 'Firefox' in ua:
            return 'Firefox'
        elif 'Safari' in ua and 'Chrome' not in ua:
            return 'Safari'
        elif 'Edg' in ua:
            return 'Edge'
        elif 'Opera' in ua or 'OPR' in ua:
            return 'Opera'
        return ua[:20]

    def reports_view(self, request: HttpRequest) -> TemplateResponse:
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
                'logins_month': ActionLog.objects.filter(
                    action_type=ActionLog.ActionType.LOGIN,
                    created_at__gte=thirty_days_ago
                ).count(),
                'active_moderators': CustomUser.objects.filter(
                    user_type__in=['moderator', 'admin'],
                    is_active=True
                ).count(),
            },
            'recent_actions': ActionLog.objects.select_related('user')[:20],
        }
        return TemplateResponse(request, 'admin/reports/index.html', context)

    def action_logs_view(self, request: HttpRequest) -> TemplateResponse:
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
        report_type = request.GET.get('type', 'actions')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if report_type == 'actions':
            data = self._get_actions_export_data(date_from, date_to)
        elif report_type == 'bookings':
            data = self._get_bookings_export_data(date_from, date_to)
        elif report_type == 'revenue':
            data = self._get_revenue_export_data(date_from, date_to)
        elif report_type == 'users':
            data = self._get_users_export_data(date_from, date_to)
        elif report_type == 'logins':
            data = self._get_logins_export_data(date_from, date_to)
        else:
            data = {'error': 'Unknown report type'}

        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            content_type='application/json; charset=utf-8'
        )
        filename = f'report_{report_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def dashboard_view(self, request: HttpRequest) -> TemplateResponse:
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)

        bookings_by_day = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            count = Booking.objects.filter(created_at__date=date).count()
            bookings_by_day.append({
                'date': date.strftime('%d.%m'),
                'count': count
            })

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

        top_spaces = Space.objects.annotate(
            bookings_count=Count('bookings'),
            revenue=Sum('bookings__total_amount')
        ).order_by('-bookings_count')[:5]

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
        bookings = Booking.objects.select_related('space', 'tenant', 'status').order_by('-created_at')
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
        logs = self._get_actions_queryset(date_from, date_to)[:1000]
        return {
            'report_type': 'actions',
            'generated_at': timezone.now().isoformat(),
            'count': logs.count(),
            'data': [
                {
                    'datetime': log.created_at.isoformat(),
                    'user': log.user.username if log.user else None,
                    'action': log.action_type,
                    'model': log.model_name,
                    'object_id': log.object_id,
                    'object': log.object_repr,
                    'ip': log.ip_address
                }
                for log in logs
            ]
        }

    def _get_bookings_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        bookings = self._get_bookings_queryset(date_from, date_to)[:1000]
        return {
            'report_type': 'bookings',
            'generated_at': timezone.now().isoformat(),
            'count': bookings.count(),
            'data': [
                {
                    'id': b.id,
                    'space': b.space.title if b.space else None,
                    'tenant': b.tenant.username if b.tenant else None,
                    'status': b.status.name if b.status else None,
                    'total_amount': float(b.total_amount),
                    'created_at': b.created_at.isoformat()
                }
                for b in bookings
            ]
        }

    def _get_revenue_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        data = self._get_pdf_revenue_data(date_from, date_to)
        return {
            'report_type': 'revenue',
            'generated_at': timezone.now().isoformat(),
            'data': [
                {'date': d[0], 'count': d[1], 'amount': d[2]}
                for d in data
            ]
        }

    def _get_users_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        data = self._get_pdf_users_data(date_from, date_to)
        return {
            'report_type': 'users',
            'generated_at': timezone.now().isoformat(),
            'data': [
                {'username': d[0], 'email': d[1], 'type': d[2], 'registered': d[3], 'bookings': d[4]}
                for d in data
            ]
        }

    def _get_logins_export_data(self, date_from: Optional[str], date_to: Optional[str]) -> dict:
        data = self._get_pdf_logins_data(date_from, date_to)
        return {
            'report_type': 'logins',
            'generated_at': timezone.now().isoformat(),
            'data': [
                {'datetime': d[0], 'user': d[1], 'ip': d[2], 'browser': d[3]}
                for d in data
            ]
        }


# Создаём экземпляр кастомного AdminSite
interior_admin_site = InteriorAdminSite(name='interior_admin')


# ============== ADMIN CLASSES FOR MODELS ==============

@admin.register(CustomUser, site=interior_admin_site)
class CustomUserAdmin(LoggingAdminMixin, UserAdmin):
    """Админ-класс для модели CustomUser."""

    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    model = CustomUser

    list_display = ('username', 'email', 'user_type', 'is_active', 'is_staff', 'created_at')
    list_filter = ('user_type', 'is_active', 'is_staff', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'email', 'phone', 'avatar')}),
        ('Права доступа', {'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')


@admin.register(UserProfile, site=interior_admin_site)
class UserProfileAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'bio_short', 'website', 'social_telegram')
    search_fields = ('user__username', 'bio', 'website')

    @admin.display(description='О себе')
    def bio_short(self, obj):
        return (obj.bio[:50] + '...') if obj.bio and len(obj.bio) > 50 else (obj.bio or '-')


@admin.register(Region, site=interior_admin_site)
class RegionAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(City, site=interior_admin_site)
class CityAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'region', 'is_active')
    list_filter = ('region', 'is_active')
    search_fields = ('name', 'region__name')


@admin.register(SpaceCategory, site=interior_admin_site)
class SpaceCategoryAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PricingPeriod, site=interior_admin_site)
class PricingPeriodAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'description', 'hours_count', 'sort_order')
    search_fields = ('name', 'description')
    ordering = ('sort_order', 'hours_count')


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


@admin.register(Space, site=interior_admin_site)
class SpaceAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('title', 'owner', 'city', 'category', 'is_active', 'is_featured', 'created_at')
    list_filter = ('is_active', 'is_featured', 'category', 'city__region')
    search_fields = ('title', 'description', 'owner__username')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [SpaceImageInline, SpacePriceInline]


@admin.register(SpaceImage, site=interior_admin_site)
class SpaceImageAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('space', 'is_primary', 'sort_order')
    list_filter = ('is_primary',)
    search_fields = ('space__title',)


@admin.register(SpacePrice, site=interior_admin_site)
class SpacePriceAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('space', 'period', 'price', 'is_active')
    list_filter = ('period', 'is_active')
    search_fields = ('space__title',)


@admin.register(BookingStatus, site=interior_admin_site)
class BookingStatusAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'code', 'color', 'sort_order')
    search_fields = ('name', 'code')
    ordering = ('sort_order',)


@admin.register(Booking, site=interior_admin_site)
class BookingAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'space', 'tenant', 'status', 'start_datetime', 'end_datetime', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('space__title', 'tenant__username')
    date_hierarchy = 'created_at'


@admin.register(TransactionStatus, site=interior_admin_site)
class TransactionStatusAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(Transaction, site=interior_admin_site)
class TransactionAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'booking', 'amount', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('booking__id',)
    date_hierarchy = 'created_at'


@admin.register(Review, site=interior_admin_site)
class ReviewAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('space', 'author', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating', 'created_at')
    search_fields = ('space__title', 'author__username', 'comment')
    actions = ['approve_reviews', 'reject_reviews']

    @admin.action(description='Одобрить выбранные отзывы')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'Одобрено {updated} отзывов')

    @admin.action(description='Отклонить выбранные отзывы')
    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'Отклонено {updated} отзывов')


@admin.register(Favorite, site=interior_admin_site)
class FavoriteAdmin(LoggingAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'space', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'space__title')


@admin.register(ActionLog, site=interior_admin_site)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action_type', 'model_name', 'object_repr', 'ip_address')
    list_filter = ('action_type', 'model_name', 'created_at')
    search_fields = ('user__username', 'object_repr', 'ip_address')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'action_type', 'model_name', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

admin_site = interior_admin_site
