"""
ПРЕДСТАВЛЕНИЯ АУТЕНТИФИКАЦИИ
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy

from ..forms import CustomUserCreationForm, CustomAuthenticationForm
from ..models import UserProfile


class CustomLoginView(LoginView):
    """
    Страница входа с кастомной формой
    """
    form_class = CustomAuthenticationForm
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('home')

    def form_valid(self, form):
        """При успешном входе показываем сообщение"""
        messages.success(
            self.request, 
            f'Добро пожаловать, {form.get_user().username}!'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        """При ошибке входа показываем сообщение"""
        messages.error(
            self.request, 
            'Неверное имя пользователя или пароль'
        )
        return super().form_invalid(form)

    def get_success_url(self):
        """Перенаправление после входа"""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('dashboard')


def register_view(request):
    """
    Страница регистрации нового пользователя
    """
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Создаем профиль если не создан в форме
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(user=user)
            
            # Автоматический вход после регистрации
            login(request, user)
            messages.success(
                request, 
                f'Добро пожаловать, {user.username}! Регистрация прошла успешно.'
            )
            return redirect('dashboard')
        else:
            # Показываем ошибки формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'auth/register.html', {'form': form})


@login_required
def logout_view(request):
    """
    Выход из системы (POST запрос для безопасности)
    """
    if request.method == 'POST':
        username = request.user.username
        logout(request)
        messages.info(request, f'До свидания, {username}!')
        return redirect('home')
    
    # GET запрос - показываем подтверждение
    return render(request, 'auth/logout_confirm.html')
