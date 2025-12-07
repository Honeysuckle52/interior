"""
Кастомный обработчик логов для записи в базу данных PostgreSQL.
Логи сохраняются в таблицу ActionLog.
"""

import logging
import traceback
from typing import Optional


class DatabaseLogHandler(logging.Handler):
    """
    Обработчик логов Django, который записывает логи в базу данных.
    Использует модель ActionLog для хранения записей.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_emitting = False  # Защита от рекурсии

    def emit(self, record: logging.LogRecord) -> None:
        """
        Записывает лог-запись в базу данных.

        Args:
            record: Объект LogRecord с информацией о логе
        """
        # Защита от рекурсии (если лог генерируется при записи в БД)
        if self._is_emitting:
            return

        self._is_emitting = True

        try:
            # Ленивый импорт для избежания циклических зависимостей
            from rental.models import ActionLog

            # Форматируем сообщение
            message = self.format(record)

            # Определяем тип действия на основе уровня лога
            if record.levelno >= logging.ERROR:
                action_type = ActionLog.ActionType.OTHER
            elif record.levelno >= logging.WARNING:
                action_type = ActionLog.ActionType.OTHER
            else:
                action_type = ActionLog.ActionType.VIEW

            # Собираем дополнительные данные
            changes = {
                'level': record.levelname,
                'module': record.module,
                'funcName': record.funcName,
                'lineno': record.lineno,
                'pathname': record.pathname,
            }

            # Добавляем traceback если есть исключение
            if record.exc_info:
                changes['traceback'] = ''.join(
                    traceback.format_exception(*record.exc_info)
                )

            # Создаем запись в базе данных
            ActionLog.objects.create(
                user=None,  # Django логи обычно не привязаны к пользователю
                action_type=action_type,
                model_name=f'django.{record.name}',
                object_id=None,
                object_repr=message[:255],  # Ограничиваем длину
                changes=changes,
                ip_address=None,
                user_agent=f'Logger: {record.name}'
            )

        except Exception:
            # В случае ошибки записи в БД, не падаем
            # Можно вывести в stderr для отладки
            self.handleError(record)
        finally:
            self._is_emitting = False
