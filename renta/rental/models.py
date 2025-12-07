"""
МОДЕЛИ БАЗЫ ДАННЫХ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ ООО "ИНТЕРЬЕР"
Приведены к третьей нормальной форме (3НФ)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from django.db import models
from django.db.models import Avg, QuerySet
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


def validate_username_simple(value):
    """Простой валидатор username без regex"""
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
    if not all(c in allowed for c in value):
        from django.core.exceptions import ValidationError
        raise ValidationError('Имя пользователя может содержать только латинские буквы, цифры и подчеркивание')


# ============== ПОЛЬЗОВАТЕЛИ ==============

class CustomUser(AbstractUser):
    """
    Расширенная модель пользователя.

    Роли:
        - user: Обычный пользователь (арендатор)
        - moderator: Модератор (проверка отзывов, модерация контента)
        - admin: Администратор (полный доступ)

    Attributes:
        user_type: Тип пользователя (пользователь, модератор, администратор)
        phone: Контактный телефон
        company: Название компании
        avatar: Фото профиля
        email_verified: Флаг подтверждения email
    """

    class UserType(models.TextChoices):
        USER = 'user', 'Пользователь'
        MODERATOR = 'moderator', 'Модератор'
        ADMIN = 'admin', 'Администратор'

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[validate_username_simple],
        error_messages={
            'unique': 'Пользователь с таким именем уже существует.',
        },
        verbose_name='Имя пользователя'
    )

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.USER,
        verbose_name='Тип пользователя',
        db_index=True
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    company = models.CharField(max_length=100, blank=True, verbose_name='Компания')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Аватар')
    email_verified = models.BooleanField(default=False, verbose_name='Email подтвержден')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        db_table = 'users'
        indexes = [
            models.Index(fields=['email'], name='idx_user_email'),
            models.Index(fields=['user_type', 'is_active'], name='idx_user_type_active'),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_user_type_display()})"

    def get_full_name_or_username(self) -> str:
        """Получить полное имя или username."""
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    def get_avatar_url(self) -> str:
        """Получить URL аватара или placeholder."""
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'

    @property
    def is_moderator(self) -> bool:
        """Проверить, является ли пользователь модератором."""
        return self.user_type == self.UserType.MODERATOR

    @property
    def is_admin_user(self) -> bool:
        """Проверить, является ли пользователь администратором."""
        return self.user_type == self.UserType.ADMIN or self.is_superuser

    @property
    def is_regular_user(self) -> bool:
        """Проверить, является ли пользователь обычным пользователем."""
        return self.user_type == self.UserType.USER

    @property
    def can_moderate(self) -> bool:
        """Проверить, может ли пользователь модерировать контент."""
        return self.is_moderator or self.is_admin_user or self.is_staff


class EmailVerificationToken(models.Model):
    """Токен для подтверждения email"""
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='email_token',
        verbose_name='Пользователь'
    )
    token = models.CharField(max_length=64, unique=True, verbose_name='Токен')
    expires_at = models.DateTimeField(verbose_name='Истекает')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Токен подтверждения email'
        verbose_name_plural = 'Токены подтверждения email'
        db_table = 'email_verification_tokens'

    def is_valid(self) -> bool:
        """Проверить, не истёк ли токен"""
        return timezone.now() < self.expires_at

    def __str__(self) -> str:
        return f"Email token for {self.user.username}"


class PasswordResetToken(models.Model):
    """Токен для сброса пароля"""
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='password_token',
        verbose_name='Пользователь'
    )
    token = models.CharField(max_length=64, unique=True, verbose_name='Токен')
    expires_at = models.DateTimeField(verbose_name='Истекает')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Токен сброса пароля'
        verbose_name_plural = 'Токены сброса пароля'
        db_table = 'password_reset_tokens'

    def is_valid(self) -> bool:
        """Проверить, не истёк ли токен"""
        return timezone.now() < self.expires_at

    def __str__(self) -> str:
        return f"Password reset token for {self.user.username}"


class UserProfile(models.Model):
    """
    Дополнительный профиль пользователя (вынесено для соблюдения 3НФ).

    Attributes:
        user: Связанный пользователь
        bio: Описание о себе
        website: Личный сайт
        social_vk: Ссылка на VK
        social_telegram: Username в Telegram
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь'
    )
    bio = models.TextField(blank=True, verbose_name='О себе')
    website = models.URLField(blank=True, verbose_name='Веб-сайт')
    social_vk = models.URLField(blank=True, verbose_name='ВКонтакте')
    social_telegram = models.CharField(max_length=100, blank=True, verbose_name='Telegram')

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
        db_table = 'user_profiles'

    def __str__(self) -> str:
        return f"Профиль {self.user.username}"


# ============== СПРАВОЧНИКИ ==============

class Region(models.Model):
    """
    Справочник регионов.

    Attributes:
        name: Название региона
        code: Код региона (уникальный)
    """

    name = models.CharField(max_length=100, unique=True, verbose_name='Название региона')
    code = models.CharField(max_length=10, unique=True, verbose_name='Код региона')

    class Meta:
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        db_table = 'regions'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    """
    Справочник городов.

    Attributes:
        name: Название города
        region: Связанный регион
        is_active: Флаг активности
    """

    name = models.CharField(max_length=100, verbose_name='Название города', db_index=True)
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name='Регион'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен', db_index=True)

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        db_table = 'cities'
        ordering = ['name']
        unique_together = ['name', 'region']
        indexes = [
            models.Index(fields=['is_active', 'name'], name='idx_city_active_name'),
        ]

    def __str__(self) -> str:
        return self.name


class SpaceCategory(models.Model):
    """
    Категории помещений (офис, лофт, фотостудия и т.д.).

    Attributes:
        name: Название категории
        slug: URL-friendly имя
        icon: CSS класс иконки FontAwesome
        description: Описание категории
        is_active: Флаг активности
    """

    name = models.CharField(max_length=100, unique=True, verbose_name='Название категории')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='URL-имя')
    icon = models.CharField(max_length=50, default='fa-building', verbose_name='Иконка FontAwesome')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активна', db_index=True)

    class Meta:
        verbose_name = 'Категория помещения'
        verbose_name_plural = 'Категории помещений'
        db_table = 'space_categories'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class PricingPeriod(models.Model):
    """
    Справочник периодов аренды (час, день, неделя, месяц).

    Attributes:
        name: Код периода
        description: Описание периода
        hours_count: Количество часов в периоде
        sort_order: Порядок сортировки
    """

    name = models.CharField(max_length=50, unique=True, verbose_name='Код периода')
    description = models.CharField(max_length=100, verbose_name='Описание')
    hours_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Количество часов'
    )
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок сортировки')

    class Meta:
        verbose_name = 'Период аренды'
        verbose_name_plural = 'Периоды аренды'
        db_table = 'pricing_periods'
        ordering = ['sort_order', 'hours_count']

    def __str__(self) -> str:
        return self.description


# ============== ОСНОВНЫЕ СУЩНОСТИ ==============

class SpaceQuerySet(models.QuerySet):
    """QuerySet для модели Space с часто используемыми запросами."""

    def active(self) -> 'SpaceQuerySet':
        """Получить только активные помещения."""
        return self.filter(is_active=True)

    def featured(self) -> 'SpaceQuerySet':
        """Получить рекомендуемые помещения."""
        return self.active().filter(is_featured=True)

    def with_relations(self) -> 'SpaceQuerySet':
        """Получить с предзагрузкой связей."""
        return self.select_related(
            'city', 'city__region', 'category', 'owner'
        ).prefetch_related(
            'images', 'prices', 'prices__period'
        )


class SpaceManager(models.Manager):
    """Менеджер для модели Space."""

    def get_queryset(self) -> SpaceQuerySet:
        return SpaceQuerySet(self.model, using=self._db)

    def active(self) -> SpaceQuerySet:
        return self.get_queryset().active()

    def featured(self) -> SpaceQuerySet:
        return self.get_queryset().featured()

    def with_relations(self) -> SpaceQuerySet:
        return self.get_queryset().with_relations()


class Space(models.Model):
    """
    Основная таблица - информация о помещениях для аренды.

    Attributes:
        title: Название помещения
        slug: URL-friendly имя
        address: Физический адрес
        city: Город расположения
        category: Категория помещения
        area_sqm: Площадь в квадратных метрах
        max_capacity: Максимальная вместимость
        description: Полное описание
        owner: Владелец помещения
        is_active: Флаг активности
        is_featured: Флаг рекомендации
        views_count: Счетчик просмотров
    """

    title = models.CharField(max_length=200, verbose_name='Название помещения')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='URL-имя')
    address = models.CharField(max_length=300, verbose_name='Адрес')

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='spaces',
        verbose_name='Город'
    )
    category = models.ForeignKey(
        SpaceCategory,
        on_delete=models.PROTECT,
        related_name='spaces',
        verbose_name='Категория'
    )

    area_sqm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.1'))],
        verbose_name='Площадь (м²)'
    )
    max_capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Макс. вместимость'
    )
    description = models.TextField(verbose_name='Описание')

    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='owned_spaces',
        verbose_name='Владелец'
    )

    is_active = models.BooleanField(default=True, verbose_name='Активно', db_index=True)
    is_featured = models.BooleanField(default=False, verbose_name='Рекомендуемое', db_index=True)
    views_count = models.PositiveIntegerField(default=0, verbose_name='Просмотры')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    objects = SpaceManager()

    class Meta:
        verbose_name = 'Помещение'
        verbose_name_plural = 'Помещения'
        db_table = 'spaces'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_featured'], name='idx_space_active_featured'),
            models.Index(fields=['city', 'is_active'], name='idx_space_city_active'),
            models.Index(fields=['category', 'is_active'], name='idx_space_category_active'),
            models.Index(fields=['-views_count'], name='idx_space_views'),
        ]

    def __str__(self) -> str:
        return self.title

    def get_main_image(self) -> Optional['SpaceImage']:
        """Получить главное изображение."""
        return self.images.filter(is_primary=True).first() or self.images.first()

    def get_min_price(self) -> Optional['SpacePrice']:
        """Получить минимальную цену."""
        return self.prices.filter(is_active=True).order_by('price').first()

    def get_avg_rating(self) -> float:
        """Получить средний рейтинг."""
        result = self.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))
        return round(result['avg'] or 0, 1)

    def get_reviews_count(self) -> int:
        """Получить количество одобренных отзывов."""
        return self.reviews.filter(is_approved=True).count()

    def get_all_images(self) -> QuerySet['SpaceImage']:
        """Получить все изображения в правильном порядке."""
        return self.images.all().order_by('-is_primary', 'sort_order')

    def is_available(self) -> bool:
        """Проверить доступность помещения."""
        return self.is_active and self.prices.filter(is_active=True).exists()

    def increment_views(self) -> None:
        """Атомарно увеличить счетчик просмотров."""
        Space.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)


class SpaceImage(models.Model):
    """
    Фотографии помещений.

    Attributes:
        space: Связанное помещение
        image: Файл изображения
        alt_text: Альтернативный текст
        is_primary: Флаг главного фото
        sort_order: Порядок сортировки
    """

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Помещение'
    )
    image = models.ImageField(
        upload_to='spaces/%Y/%m/',
        verbose_name='Изображение'
    )
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='Alt текст')
    is_primary = models.BooleanField(default=False, verbose_name='Главное фото', db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'Фото помещения'
        verbose_name_plural = 'Фото помещений'
        db_table = 'space_images'
        ordering = ['-is_primary', 'sort_order']
        indexes = [
            models.Index(fields=['space', 'is_primary'], name='idx_image_space_primary'),
        ]

    def __str__(self) -> str:
        return f"Фото {self.space.title}"

    def get_url(self) -> Optional[str]:
        """Получить URL изображения."""
        if self.image:
            return self.image.url
        return None

    def save(self, *args, **kwargs) -> None:
        """Сохранить с обработкой флага главного фото."""
        if self.is_primary:
            SpaceImage.objects.filter(
                space=self.space, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class SpacePrice(models.Model):
    """
    Цены для каждого помещения в разных периодах аренды.

    Attributes:
        space: Связанное помещение
        period: Период аренды
        price: Цена за период
        is_active: Флаг активности
        min_periods: Минимальное количество периодов
        max_periods: Максимальное количество периодов
    """

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name='prices',
        verbose_name='Помещение'
    )
    period = models.ForeignKey(
        PricingPeriod,
        on_delete=models.PROTECT,
        related_name='space_prices',
        verbose_name='Период'
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Цена'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна', db_index=True)
    min_periods = models.PositiveIntegerField(default=1, verbose_name='Мин. периодов')
    max_periods = models.PositiveIntegerField(default=100, verbose_name='Макс. периодов')

    class Meta:
        verbose_name = 'Цена помещения'
        verbose_name_plural = 'Цены помещений'
        db_table = 'space_prices'
        unique_together = ['space', 'period']
        ordering = ['period__sort_order']
        indexes = [
            models.Index(fields=['space', 'is_active'], name='idx_price_space_active'),
        ]

    def __str__(self) -> str:
        return f"{self.space.title} - {self.period.description}: {self.price}₽"


# ============== БРОНИРОВАНИЯ И ТРАНЗАКЦИИ ==============

class BookingStatus(models.Model):
    """
    Справочник статусов бронирования.

    Attributes:
        code: Уникальный код статуса
        name: Отображаемое название
        color: CSS класс цвета Bootstrap
        sort_order: Порядок сортировки
    """

    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')
    color = models.CharField(max_length=20, default='secondary', verbose_name='Цвет Bootstrap')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Статус бронирования'
        verbose_name_plural = 'Статусы бронирований'
        db_table = 'booking_statuses'
        ordering = ['sort_order']

    def __str__(self) -> str:
        return self.name


class BookingManager(models.Manager):
    """Менеджер для модели Booking."""

    def active(self) -> QuerySet['Booking']:
        """Получить активные бронирования."""
        return self.filter(status__code__in=['pending', 'confirmed'])

    def for_user(self, user: CustomUser) -> QuerySet['Booking']:
        """Получить бронирования пользователя."""
        return self.filter(tenant=user)

    def for_space(self, space_id: int) -> QuerySet['Booking']:
        """Получить бронирования помещения."""
        return self.filter(space_id=space_id)


class Booking(models.Model):
    """
    Таблица бронирований.

    Attributes:
        space: Арендуемое помещение
        tenant: Арендатор
        period: Период аренды
        status: Текущий статус
        start_datetime: Дата и время начала
        end_datetime: Дата и время окончания
        periods_count: Количество периодов
        price_per_period: Цена за один период
        total_amount: Общая сумма
        comment: Комментарий к бронированию
    """

    space = models.ForeignKey(
        Space,
        on_delete=models.PROTECT,
        related_name='bookings',
        verbose_name='Помещение'
    )
    tenant = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name='Арендатор'
    )
    period = models.ForeignKey(
        PricingPeriod,
        on_delete=models.PROTECT,
        verbose_name='Период аренды'
    )
    status = models.ForeignKey(
        BookingStatus,
        on_delete=models.PROTECT,
        verbose_name='Статус'
    )

    start_datetime = models.DateTimeField(verbose_name='Начало аренды', db_index=True)
    end_datetime = models.DateTimeField(verbose_name='Окончание аренды', db_index=True)
    periods_count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Количество периодов'
    )

    price_per_period = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Цена за период'
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Общая стоимость'
    )

    comment = models.TextField(blank=True, verbose_name='Комментарий')
    moderator_comment = models.TextField(blank=True, verbose_name='Комментарий модератора')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    objects = BookingManager()

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        db_table = 'bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_booking_tenant_status'),
            models.Index(fields=['space', 'start_datetime'], name='idx_booking_space_start'),
            models.Index(
                fields=['start_datetime', 'end_datetime'],
                name='idx_booking_period'
            ),
        ]

    def __str__(self) -> str:
        return f"Бронь #{self.id} - {self.space.title}"

    @property
    def is_cancellable(self) -> bool:
        """Проверить, можно ли отменить бронирование."""
        return self.status.code in ['pending', 'confirmed']

    @property
    def is_active(self) -> bool:
        """Проверить, активно ли бронирование."""
        return self.status.code in ['pending', 'confirmed']


class TransactionStatus(models.Model):
    """
    Справочник статусов транзакций.

    Attributes:
        code: Уникальный код статуса
        name: Отображаемое название
    """

    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        verbose_name = 'Статус транзакции'
        verbose_name_plural = 'Статусы транзакций'
        db_table = 'transaction_statuses'

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    """
    Таблица финансовых транзакций.

    Attributes:
        booking: Связанное бронирование
        status: Статус транзакции
        amount: Сумма транзакции
        payment_method: Способ оплаты
        external_id: Внешний ID (от платежной системы)
    """

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Бронирование'
    )
    status = models.ForeignKey(
        TransactionStatus,
        on_delete=models.PROTECT,
        verbose_name='Статус'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Сумма'
    )
    payment_method = models.CharField(max_length=50, blank=True, verbose_name='Способ оплаты')
    external_id = models.CharField(max_length=100, blank=True, verbose_name='Внешний ID', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата транзакции', db_index=True)

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        db_table = 'transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'status'], name='idx_transaction_booking'),
        ]

    def __str__(self) -> str:
        return f"Транзакция #{self.id} - {self.amount}₽"


# ============== ОТЗЫВЫ ==============

class Review(models.Model):
    """
    Таблица отзывов о помещениях.

    Attributes:
        space: Помещение, к которому относится отзыв
        author: Автор отзыва
        booking: Связанное бронирование (опционально)
        rating: Оценка от 1 до 5
        comment: Текст отзыва
        is_approved: Флаг модерации
    """

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Помещение'
    )
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='Автор'
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review',
        verbose_name='Бронирование'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Рейтинг',
        db_index=True
    )
    comment = models.TextField(verbose_name='Комментарий')
    is_approved = models.BooleanField(default=False, verbose_name='Одобрен', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата отзыва', db_index=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        db_table = 'reviews'
        ordering = ['-created_at']
        unique_together = ['space', 'author']
        indexes = [
            models.Index(fields=['space', 'is_approved'], name='idx_review_space_approved'),
            models.Index(fields=['author', 'created_at'], name='idx_review_author'),
        ]

    def __str__(self) -> str:
        return f"Отзыв {self.author.username} - {self.rating} звёзд"


# ============== ИЗБРАННОЕ ==============

class Favorite(models.Model):
    """
    Избранные помещения пользователей.

    Attributes:
        user: Пользователь
        space: Помещение в избранном
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Пользователь'
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='Помещение'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        db_table = 'favorites'
        unique_together = ['user', 'space']
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_favorite_user'),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.space.title}"


# ============== ЛОГИРОВАНИЕ ДЕЙСТВИЙ ==============

class ActionLog(models.Model):
    """
    Журнал действий пользователей для системы отчетности.

    Attributes:
        user: Пользователь, выполнивший действие
        action_type: Тип действия
        model_name: Название модели
        object_id: ID объекта
        object_repr: Строковое представление объекта
        changes: JSON с изменениями
        ip_address: IP адрес ользователя
        user_agent: User-Agent браузера
    """

    class ActionType(models.TextChoices):
        CREATE = 'create', 'Создание'
        UPDATE = 'update', 'Редактирование'
        DELETE = 'delete', 'Удаление'
        VIEW = 'view', 'Просмотр'
        LOGIN = 'login', 'Вход'
        LOGOUT = 'logout', 'Выход'
        OTHER = 'other', 'Другое'

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='action_logs',
        verbose_name='Пользователь'
    )
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        verbose_name='Тип действия',
        db_index=True
    )
    model_name = models.CharField(max_length=100, verbose_name='Модель', db_index=True)
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID объекта')
    object_repr = models.CharField(max_length=255, verbose_name='Представление объекта')
    changes = models.JSONField(default=dict, blank=True, verbose_name='Изменения')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP адрес')
    user_agent = models.TextField(blank=True, verbose_name='User-Agent')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата действия', db_index=True)

    class Meta:
        verbose_name = 'Журнал действий'
        verbose_name_plural = 'Журнал действий'
        db_table = 'action_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action_type'], name='idx_log_user_action'),
            models.Index(fields=['model_name', 'object_id'], name='idx_log_model_object'),
            models.Index(fields=['created_at', 'action_type'], name='idx_log_date_action'),
        ]

    def __str__(self) -> str:
        user_str = self.user.username if self.user else 'Аноним'
        return f"{user_str} - {self.get_action_type_display()} - {self.model_name}"
