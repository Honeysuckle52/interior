"""
====================================================================
СЕРВИС ГЕОКОДИРОВАНИЯ ДЛЯ САЙТА АРЕНДЫ ПОМЕЩЕНИЙ "ИНТЕРЬЕР"
====================================================================
Этот файл содержит сервис для получения координат (широта/долгота)
по адресу через Яндекс Геокодер API.

Как работает:
1. При создании/редактировании помещения вызывается geocode_address()
2. Сервис отправляет запрос к Яндекс Геокодер API с полным адресом
3. API возвращает координаты, которые сохраняются в модель Space
4. На странице помещения карта использует сохранённые координаты
   (без дополнительных запросов к API)

Настройка:
- Получите API ключ на https://developer.tech.yandex.ru/
- Добавьте YANDEX_GEOCODER_API_KEY в settings.py или переменные окружения
====================================================================
"""

from __future__ import annotations

import logging
import requests
from typing import Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


def geocode_address(city: str, address: str) -> Optional[Tuple[float, float]]:
    """
    Получение координат по адресу через Яндекс Геокодер API.

    Args:
        city: Название города
        address: Адрес (улица, дом)

    Returns:
        Tuple[float, float]: (широта, долгота) или None при ошибке

    Example:
        >>> coords = geocode_address("Москва", "ул. Тверская, 1")
        >>> print(coords)  # (55.757994, 37.612893)
    """
    api_key = getattr(settings, 'YANDEX_GEOCODER_API_KEY', None)

    if not api_key:
        logger.warning("YANDEX_GEOCODER_API_KEY не настроен в settings.py")
        return None

    full_address = f"{city}, {address}"

    try:
        response = requests.get(
            'https://geocode-maps.yandex.ru/1.x/',
            params={
                'apikey': api_key,
                'geocode': full_address,
                'format': 'json',
                'results': 1,
            },
            timeout=5
        )
        response.raise_for_status()

        data = response.json()

        # Извлекаем координаты из ответа API
        geo_objects = data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember', [])

        if not geo_objects:
            logger.warning(f"Адрес не найден: {full_address}")
            return None

        # Яндекс возвращает координаты в формате "долгота широта"
        pos = geo_objects[0]['GeoObject']['Point']['pos']
        longitude, latitude = map(float, pos.split())

        logger.info(f"Геокодирование успешно: {full_address} -> ({latitude}, {longitude})")
        return (latitude, longitude)

    except requests.exceptions.Timeout:
        logger.error(f"Таймаут при геокодировании: {full_address}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса геокодирования: {e}")
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга ответа геокодера: {e}")
        return None


def update_space_coordinates(space) -> bool:
    """
    Обновляет координаты помещения по его адресу.

    Args:
        space: Объект модели Space

    Returns:
        bool: True если координаты обновлены, False при ошибке
    """
    if not space.city or not space.address:
        return False

    coords = geocode_address(space.city.name, space.address)

    if coords:
        space.latitude, space.longitude = coords
        space.save(update_fields=['latitude', 'longitude'])
        return True

    return False
