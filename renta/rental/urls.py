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
    dashboard, profile, my_bookings, my_favorites,
    # Избранное
    toggle_favorite,
    # Бронирования
    create_booking, booking_detail, cancel_booking,
    # Отзывы
    create_review,
)
from .views.favorites import check_favorite
from .views.bookings import get_price_for_period
from .views.reviews import my_reviews, delete_review


urlpatterns = [
    # ============== ГЛАВНАЯ ==============
    path('', home, name='home'),

    # ============== ПОМЕЩЕНИЯ ==============
    path('spaces/', spaces_list, name='spaces_list'),
    path('spaces/<int:pk>/', space_detail, name='space_detail'),

    # ============== АУТЕНТИФИКАЦИЯ ==============
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    # ============== ЛИЧНЫЙ КАБИНЕТ ==============
    path('dashboard/', dashboard, name='dashboard'),
    path('profile/', profile, name='profile'),
    path('my-bookings/', my_bookings, name='my_bookings'),
    path('my-favorites/', my_favorites, name='my_favorites'),
    path('my-reviews/', my_reviews, name='my_reviews'),

    # ============== ИЗБРАННОЕ (AJAX) ==============
    path('spaces/<int:pk>/favorite/', toggle_favorite, name='toggle_favorite'),
    path('spaces/<int:pk>/check-favorite/', check_favorite, name='check_favorite'),

    # ============== БРОНИРОВАНИЯ ==============
    path('spaces/<int:pk>/book/', create_booking, name='create_booking'),
    path('bookings/<int:pk>/', booking_detail, name='booking_detail'),
    path('bookings/<int:pk>/cancel/', cancel_booking, name='cancel_booking'),

    # ============== ОТЗЫВЫ ==============
    path('spaces/<int:pk>/review/', create_review, name='create_review'),
    path('reviews/<int:pk>/delete/', delete_review, name='delete_review'),

    # ============== API (AJAX) ==============
    path('api/price/<int:space_id>/<int:period_id>/', get_price_for_period, name='get_price'),
]
