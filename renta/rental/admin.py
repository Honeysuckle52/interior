"""
НАСТРОЙКА АДМИН-ПАНЕЛИ ДЛЯ САЙТА АРЕНДЫ ООО "ИНТЕРЬЕР"
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.db.models import Count, Avg, Sum

from .models import (
    CustomUser, UserProfile, Region, City, SpaceCategory,
    PricingPeriod, Space, SpaceImage, SpacePrice,
    BookingStatus, Booking, TransactionStatus, Transaction,
    Review, Favorite
)


# ============== НАСТРОЙКА ЗАГОЛОВКОВ ==============

admin.site.site_header = 'ООО "ИНТЕРЬЕР" - Администрирование'
admin.site.site_title = 'ИНТЕРЬЕР Admin'
admin.site.index_title = 'Панель управления сайтом аренды помещений'


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

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
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

    def get_full_name_display(self, obj):
        return obj.get_full_name() or '-'
    get_full_name_display.short_description = 'ФИО'

    def get_bookings_count(self, obj):
        count = obj.bookings.count()
        return format_html('<b>{}</b>', count) if count > 0 else '0'
    get_bookings_count.short_description = 'Бронирований'


# ============== СПРАВОЧНИКИ ==============

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'get_cities_count']
    search_fields = ['name', 'code']
    ordering = ['name']

    def get_cities_count(self, obj):
        return obj.cities.count()
    get_cities_count.short_description = 'Городов'


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'is_active', 'get_spaces_count']
    list_filter = ['region', 'is_active']
    search_fields = ['name', 'region__name']
    list_editable = ['is_active']
    ordering = ['name']

    def get_spaces_count(self, obj):
        count = obj.spaces.filter(is_active=True).count()
        return format_html('<b>{}</b>', count) if count > 0 else '0'
    get_spaces_count.short_description = 'Помещений'


@admin.register(SpaceCategory)
class SpaceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon_preview', 'is_active', 'get_spaces_count']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['is_active']
    list_editable = ['is_active']
    search_fields = ['name']

    def icon_preview(self, obj):
        return format_html('<i class="fas {}"></i> {}', obj.icon, obj.icon)
    icon_preview.short_description = 'Иконка'

    def get_spaces_count(self, obj):
        return obj.spaces.filter(is_active=True).count()
    get_spaces_count.short_description = 'Помещений'


@admin.register(PricingPeriod)
class PricingPeriodAdmin(admin.ModelAdmin):
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

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 60px; object-fit: cover;"/>',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Превью'


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


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
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

    def get_min_price_display(self, obj):
        price = obj.get_min_price()
        if price:
            return format_html('от <b>{} ₽</b>/{}'.format(
                int(price.price), price.period.name
            ))
        return '-'
    get_min_price_display.short_description = 'Цена'

    def get_bookings_count(self, obj):
        return obj.bookings.count()
    get_bookings_count.short_description = 'Брони'

    def get_stats(self, obj):
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
    get_stats.short_description = 'Статистика'


@admin.register(SpaceImage)
class SpaceImageAdmin(admin.ModelAdmin):
    list_display = ['space', 'image_preview', 'is_primary', 'sort_order', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at']
    search_fields = ['space__title', 'alt_text']
    list_editable = ['is_primary', 'sort_order']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 80px; max-height: 50px; object-fit: cover;"/>',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Фото'


# ============== БРОНИРОВАНИЯ ==============

@admin.register(BookingStatus)
class BookingStatusAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'color_preview', 'sort_order']
    list_editable = ['sort_order']
    ordering = ['sort_order']

    def color_preview(self, obj):
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            obj.color, obj.name
        )
    color_preview.short_description = 'Вид'


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ['status', 'amount', 'payment_method', 'external_id', 'created_at']
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
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

    def status_badge(self, obj):
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            obj.status.color, obj.status.name
        )
    status_badge.short_description = 'Статус'

    def total_amount_display(self, obj):
        return format_html('<b>{} ₽</b>', int(obj.total_amount))
    total_amount_display.short_description = 'Сумма'


# ============== ТРАНЗАКЦИИ ==============

@admin.register(TransactionStatus)
class TransactionStatusAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking', 'status', 'amount_display', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['booking__id', 'external_id']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']

    def amount_display(self, obj):
        return format_html('<b>{} ₽</b>', int(obj.amount))
    amount_display.short_description = 'Сумма'


# ============== ОТЗЫВЫ И ИЗБРАННОЕ ==============

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['space', 'author', 'rating_display', 'comment_short', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['space__title', 'author__username', 'comment']
    list_editable = ['is_approved']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    actions = ['approve_reviews', 'reject_reviews']

    def rating_display(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #ffc107;">{}</span>', stars)
    rating_display.short_description = 'Рейтинг'

    def comment_short(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_short.short_description = 'Комментарий'

    @admin.action(description='Одобрить выбранные отзывы')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'Одобрено {updated} отзывов')

    @admin.action(description='Отклонить выбранные отзывы')
    def reject_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'Отклонено {updated} отзывов')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'space', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'space__title']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']