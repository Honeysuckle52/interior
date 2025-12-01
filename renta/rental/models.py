"""
МОДЕЛИ БАЗЫ ДАННЫХ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ ООО "ИНТЕРЬЕР"
Приведены к третьей нормальной форме (3НФ)
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify


# ============== ПОЛЬЗОВАТЕЛИ ==============

class CustomUser(AbstractUser):
    """
    Расширенная модель пользователя
    """
    USER_TYPE_CHOICES = (
        ('client', 'Клиент'),
        ('owner', 'Владелец'),
        ('admin', 'Администратор'),
    )

    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPE_CHOICES,
        default='client',
        verbose_name='Тип пользователя'
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    company = models.CharField(max_length=100, blank=True, verbose_name='Компания')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Аватар')
    email_verified = models.BooleanField(default=False, verbose_name='Email подтвержден')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        db_table = 'users'

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    def get_full_name_or_username(self):
        """Получить полное имя или username"""
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    def get_avatar_url(self):
        """Получить URL аватара или placeholder"""
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'


class UserProfile(models.Model):
    """
    Дополнительный профиль пользователя (вынесено для соблюдения 3НФ)
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

    def __str__(self):
        return f"Профиль {self.user.username}"


# ============== СПРАВОЧНИКИ (отдельные независимые сущности для 3НФ) ==============

class Region(models.Model):
    """
    Справочник регионов (вынесен из City для соблюдения 3НФ)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Название региона')
    code = models.CharField(max_length=10, unique=True, verbose_name='Код региона')

    class Meta:
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        db_table = 'regions'
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    """
    Справочник городов
    """
    name = models.CharField(max_length=100, verbose_name='Название города')
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name='Регион'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        db_table = 'cities'
        ordering = ['name']
        unique_together = ['name', 'region']  # Уникальность города в рамках региона

    def __str__(self):
        return f"{self.name}"


class SpaceCategory(models.Model):
    """
    Категории помещений (офис, лофт, фотостудия и т.д.)
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Название категории')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='URL-имя')
    icon = models.CharField(max_length=50, default='fa-building', verbose_name='Иконка FontAwesome')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Категория помещения'
        verbose_name_plural = 'Категории помещений'
        db_table = 'space_categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class PricingPeriod(models.Model):
    """
    Справочник периодов аренды (час, день, неделя, месяц)
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

    def __str__(self):
        return self.description


# ============== ОСНОВНЫЕ СУЩНОСТИ ==============

class Space(models.Model):
    """
    Основная таблица - информация о помещениях для аренды
    """
    title = models.CharField(max_length=200, verbose_name='Название помещения')
    slug = models.SlugField(max_length=200, unique=True, verbose_name='URL-имя')
    address = models.CharField(max_length=300, verbose_name='Адрес')

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,  # Защита от удаления города с помещениями
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
        validators=[MinValueValidator(0.1)],
        verbose_name='Площадь (м²)'
    )
    max_capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Макс. вместимость'
    )
    description = models.TextField(verbose_name='Описание')

    # Владелец помещения
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='owned_spaces',
        verbose_name='Владелец'
    )

    is_active = models.BooleanField(default=True, verbose_name='Активно')
    is_featured = models.BooleanField(default=False, verbose_name='Рекомендуемое')
    views_count = models.PositiveIntegerField(default=0, verbose_name='Просмотры')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Помещение'
        verbose_name_plural = 'Помещения'
        db_table = 'spaces'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_main_image(self):
        """Получить главное изображение"""
        return self.images.filter(is_primary=True).first() or self.images.first()

    def get_min_price(self):
        """Получить минимальную цену"""
        price = self.prices.filter(is_active=True).order_by('price').first()
        return price

    def get_avg_rating(self):
        """Получить средний рейтинг"""
        from django.db.models import Avg
        result = self.reviews.filter(is_approved=True).aggregate(avg=Avg('rating'))
        return round(result['avg'] or 0, 1)

    def get_reviews_count(self):
        """Получить количество одобренных отзывов"""
        return self.reviews.filter(is_approved=True).count()

    def get_all_images(self):
        """Получить все изображения в правильном порядке"""
        return self.images.all().order_by('-is_primary', 'sort_order')

    def is_available(self):
        """Проверить доступность помещения"""
        return self.is_active and self.prices.filter(is_active=True).exists()


class SpaceImage(models.Model):
    """
    Фотографии помещений
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
    is_primary = models.BooleanField(default=False, verbose_name='Главное фото')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'Фото помещения'
        verbose_name_plural = 'Фото помещений'
        db_table = 'space_images'
        ordering = ['-is_primary', 'sort_order']

    def __str__(self):
        return f"Фото {self.space.title}"

    def get_url(self):
        """Получить URL изображения"""
        if self.image:
            return self.image.url
        return None

    def save(self, *args, **kwargs):
        # Если это главное фото, убираем флаг у других
        if self.is_primary:
            SpaceImage.objects.filter(space=self.space, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class SpacePrice(models.Model):
    """
    Цены для каждого помещения в разных периодах аренды
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
        validators=[MinValueValidator(0.01)],
        verbose_name='Цена'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    min_periods = models.PositiveIntegerField(default=1, verbose_name='Мин. периодов')
    max_periods = models.PositiveIntegerField(default=100, verbose_name='Макс. периодов')

    class Meta:
        verbose_name = 'Цена помещения'
        verbose_name_plural = 'Цены помещений'
        db_table = 'space_prices'
        unique_together = ['space', 'period']
        ordering = ['period__sort_order']

    def __str__(self):
        return f"{self.space.title} - {self.period.description}: {self.price}₽"


# ============== БРОНИРОВАНИЯ И ТРАНЗАКЦИИ ==============

class BookingStatus(models.Model):
    """
    Справочник статусов бронирования (вынесен для 3НФ)
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

    def __str__(self):
        return self.name


class Booking(models.Model):
    """
    Таблица бронирований
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

    start_datetime = models.DateTimeField(verbose_name='Начало аренды')
    end_datetime = models.DateTimeField(verbose_name='Окончание аренды')
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        db_table = 'bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Бронь #{self.id} - {self.space.title}"


class TransactionStatus(models.Model):
    """
    Справочник статусов транзакций
    """
    code = models.CharField(max_length=20, unique=True, verbose_name='Код')
    name = models.CharField(max_length=50, verbose_name='Название')

    class Meta:
        verbose_name = 'Статус транзакции'
        verbose_name_plural = 'Статусы транзакций'
        db_table = 'transaction_statuses'

    def __str__(self):
        return self.name


class Transaction(models.Model):
    """
    Таблица финансовых транзакций
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
    external_id = models.CharField(max_length=100, blank=True, verbose_name='Внешний ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата транзакции')

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        db_table = 'transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Транзакция #{self.id} - {self.amount}₽"


# ============== ОТЗЫВЫ ==============

class Review(models.Model):
    """
    Таблица отзывов о помещениях
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
        verbose_name='Рейтинг'
    )
    comment = models.TextField(verbose_name='Комментарий')
    is_approved = models.BooleanField(default=False, verbose_name='Одобрен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата отзыва')

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        db_table = 'reviews'
        ordering = ['-created_at']
        # Один пользователь - один отзыв на помещение
        unique_together = ['space', 'author']

    def __str__(self):
        return f"Отзыв {self.author.username} - {self.rating}⭐"


# ============== ИЗБРАННОЕ ==============

class Favorite(models.Model):
    """
    Избранные помещения пользователей
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

    def __str__(self):
        return f"{self.user.username} - {self.space.title}"
