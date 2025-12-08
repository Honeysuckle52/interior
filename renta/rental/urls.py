"""
URL-МАРШРУТЫ ДЛЯ ПРИЛОЖЕНИЯ RENTAL
"""

from django.urls import path
from .views import (
    # Главная
    home,
    # Помещения
    spaces_list, space_detail,
    # Аутентификация
    CustomLoginView, register_view, logout_view,
    # Личный кабинет
    dashboard, profile, my_bookings, my_favorites, view_user_profile,
    # Избранное
    toggle_favorite,
    # Бронирования
    create_booking, booking_detail, cancel_booking,
    # Отзывы
    create_review, edit_review, admin_delete_review, approve_review, manage_reviews,
    manage_users, user_detail, block_user, unblock_user, verify_user_email,
)
from .views.favorites import check_favorite
from .views.bookings import get_price_for_period, confirm_booking, reject_booking, manage_bookings
from .views.reviews import my_reviews, delete_review
from .views.auth import (
    verify_email,
    resend_verification,
    password_reset_request,
    password_reset_confirm,
    verify_email_code,
    resend_verification_code,
)
from .views.users import users_ajax
from .views.spaces import spaces_ajax, manage_spaces, add_space, edit_space, delete_space  # Добавлены новые views


urlpatterns = [
    # ============== ГЛАВНАЯ ==============
    path('', home, name='home'),

    # ============== ПОМЕЩЕНИЯ ==============
    path('spaces/', spaces_list, name='spaces_list'),
    path('spaces/<int:pk>/', space_detail, name='space_detail'),
    path('api/spaces/', spaces_ajax, name='spaces_ajax'),

    # ============== УПРАВЛЕНИЕ ПОМЕЩЕНИЯМИ (Модератор/Админ) ==============
    path('manage/spaces/', manage_spaces, name='manage_spaces'),
    path('manage/spaces/add/', add_space, name='add_space'),
    path('manage/spaces/<int:pk>/edit/', edit_space, name='edit_space'),
    path('manage/spaces/<int:pk>/delete/', delete_space, name='delete_space'),

    # ============== АУТЕНТИФИКАЦИЯ ==============
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    path('verify-code/', verify_email_code, name='verify_email_code'),
    path('resend-code/', resend_verification_code, name='resend_verification_code'),

    path('verify-email/<str:token>/', verify_email, name='verify_email'),
    path('resend-verification/', resend_verification, name='resend_verification'),
    path('password-reset/', password_reset_request, name='password_reset'),
    path('reset-password/<str:token>/', password_reset_confirm, name='password_reset_confirm'),

    # ============== ЛИЧНЫЙ КАБИНЕТ ==============
    path('dashboard/', dashboard, name='dashboard'),
    path('profile/', profile, name='profile'),
    path('my-bookings/', my_bookings, name='my_bookings'),
    path('my-favorites/', my_favorites, name='my_favorites'),
    path('my-reviews/', my_reviews, name='my_reviews'),

    path('users/<int:pk>/profile/', view_user_profile, name='view_user_profile'),

    # ============== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (Модератор) ==============
    path('manage/users/', manage_users, name='manage_users'),
    path('api/users/', users_ajax, name='users_ajax'),
    path('manage/users/<int:pk>/', user_detail, name='user_detail_mod'),
    path('manage/users/<int:pk>/block/', block_user, name='block_user'),
    path('manage/users/<int:pk>/unblock/', unblock_user, name='unblock_user'),
    path('manage/users/<int:pk>/verify-email/', verify_user_email, name='verify_user_email_mod'),

    # ============== ИЗБРАННОЕ (AJAX) ==============
    path('spaces/<int:pk>/favorite/', toggle_favorite, name='toggle_favorite'),
    path('spaces/<int:pk>/check-favorite/', check_favorite, name='check_favorite'),

    # ============== БРОНИРОВАНИЯ ==============
    path('spaces/<int:pk>/book/', create_booking, name='create_booking'),
    path('bookings/<int:pk>/', booking_detail, name='booking_detail'),
    path('bookings/<int:pk>/cancel/', cancel_booking, name='cancel_booking'),
    path('bookings/<int:pk>/confirm/', confirm_booking, name='confirm_booking'),
    path('bookings/<int:pk>/reject/', reject_booking, name='reject_booking'),
    path('manage/bookings/', manage_bookings, name='manage_bookings'),

    # ============== ОТЗЫВЫ ==============
    path('spaces/<int:pk>/review/', create_review, name='create_review'),
    path('reviews/<int:pk>/delete/', delete_review, name='delete_review'),
    path('reviews/<int:pk>/edit/', edit_review, name='edit_review'),
    path('reviews/<int:pk>/admin-delete/', admin_delete_review, name='admin_delete_review'),
    path('reviews/<int:pk>/approve/', approve_review, name='approve_review'),
    path('manage/reviews/', manage_reviews, name='manage_reviews'),

    # ============== API (AJAX) ==============
    path('api/price/<int:space_id>/<int:period_id>/', get_price_for_period, name='get_price'),
]
