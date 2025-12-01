"""
КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
"""

from django.apps import AppConfig


class RentalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rental'
    verbose_name = 'Аренда помещений'

    def ready(self):
        """Подключаем сигналы при загрузке приложения"""
        import rental.signals  # noqa
