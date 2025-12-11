"""
Django settings for renta project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure--c7t$e)$do1-%#43@y@!&pgqqa_7ovk)km0lq@#qwh$b0cm1gd'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

JAZZMIN_SETTINGS = {
    "site_title": "ИНТЕРЬЕР Admin",
    "site_header": "ИНТЕРЬЕР",
    "site_brand": "ООО ИНТЕРЬЕР",
    "site_logo": None,
    "login_logo": None,
    "site_logo_classes": "img-circle",
    "site_icon": None,
    "welcome_sign": "Добро пожаловать в панель управления",
    "copyright": "ООО ИНТЕРЬЕР",
    "user_avatar": "avatar",

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    "order_with_respect_to": ["rental", "auth"],

    "topmenu_links": [
        {"name": "Главная", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Сайт", "url": "/", "new_window": True},
        {"name": "Отчеты", "url": "interior_admin:reports"},
        {"name": "Backup", "url": "interior_admin:backup"},
    ],

    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "rental.CustomUser": "fas fa-user-circle",
        "rental.Region": "fas fa-globe-europe",
        "rental.City": "fas fa-city",
        "rental.SpaceCategory": "fas fa-th-large",
        "rental.PricingPeriod": "fas fa-clock",
        "rental.Space": "fas fa-building",
        "rental.SpaceImage": "fas fa-images",
        "rental.SpacePrice": "fas fa-ruble-sign",
        "rental.BookingStatus": "fas fa-info-circle",
        "rental.Booking": "fas fa-calendar-check",
        "rental.TransactionStatus": "fas fa-exchange-alt",
        "rental.Transaction": "fas fa-credit-card",
        "rental.Review": "fas fa-star",
        "rental.Favorite": "fas fa-heart",
        "rental.ActionLog": "fas fa-history",
    },

    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": True,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,

    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "rental.space": "collapsible",
        "rental.customuser": "horizontal_tabs",
    },

    "custom_css": "css/admin_custom.css",
    "custom_js": "js/admin_custom.js",
}

JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",

    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,

    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-warning",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,

    "footer_fixed": False,
    "footer_small_text": True,

    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-warning",
    "accent": "accent-warning",
    "navbar_small_text": False,

    "button_classes": {
        "primary": "btn-warning",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },

    "actions_sticky_top": True,
}

# Application definition
INSTALLED_APPS = [
    'jazzmin',  # Должен быть ПЕРЕД django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rental',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'rental.middleware.BlockedUserMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'renta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'rental.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'renta.wsgi.application'

# Database - PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'interior'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgre'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'rental.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login settings
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

# Messages
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Для разработки: установите переменную окружения EMAIL_HOST_PASSWORD
# Для получения пароля приложения: https://account.mail.ru/user/2-step-auth/passwords/

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'  # Изменено на SMTP
)

# Настройки SMTP для Mail.ru
EMAIL_HOST = 'smtp.mail.ru'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False  # Важно: SSL и TLS взаимоисключающие

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'danil_naumov_90@bk.ru')

EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'fDwwurqGAMSfNry3JlZU')

DEFAULT_FROM_EMAIL = f'INTERIOR <{EMAIL_HOST_USER}>'

# Таймаут для SMTP соединения (секунды)
EMAIL_TIMEOUT = 30

# Получите данные в личном кабинете ЮKassa:
YOOKASSA_SHOP_ID = os.environ.get('YOOKASSA_SHOP_ID', '1225524')
YOOKASSA_SECRET_KEY = os.environ.get('YOOKASSA_SECRET_KEY', 'test_-W5gL0m29-Vj5oYnjMBKZ62jHkNiMBFdsmiaZeGhiQs')

# Процент предоплаты (10%)
PREPAYMENT_PERCENT = 10
# Часов до начала для бесплатной отмены
CANCELLATION_HOURS = 24

# Получите ключ на https://developer.tech.yandex.ru/
# Выберите API "JavaScript API и HTTP Геокодер"
YANDEX_GEOCODER_API_KEY = os.environ.get('YANDEX_GEOCODER_API_KEY', '607b4bfc-3ec1-4a3f-aa87-ce16df446f1e')

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'rental': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
