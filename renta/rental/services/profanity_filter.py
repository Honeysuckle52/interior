"""
====================================================================
СЕРВИС ФИЛЬТРАЦИИ МАТЕРНЫХ СЛОВ ДЛЯ САЙТА "ИНТЕРЬЕР"
====================================================================
Автоматическая проверка текста на наличие нецензурной лексики.
Поддерживает русский и английский языки.
====================================================================
"""

import re
from typing import Tuple, List

# Список матерных слов (русский язык) - базовые корни
RUSSIAN_PROFANITY_ROOTS = [
    'хуй', 'хуя', 'хуе', 'хуи', 'хую',
    'пизд', 'пезд',
    'блять', 'бляд', 'блят',
    'еба', 'ебу', 'ебе', 'ебл', 'ебн', 'ёба', 'ёбу', 'ёбе', 'ёбл', 'ёбн',
    'сука', 'суч', 'сучк', 'сучар',
    'муда', 'мудо', 'муди', 'мудак',
    'залуп',
    'шлюх', 'шалав',
    'педик', 'педер', 'п��дар', 'пидор', 'пидр',
    'гандон', 'гондон',
    'дерьм', 'говн', 'срат', 'срал', 'сран', 'засран',
    'жоп', 'жёп',
    'трах', 'траха',
    'долбо', 'долбан', 'долбаё', 'долбае',
    'заеб', 'заёб', 'отъеб', 'отьеб', 'въеб', 'вьеб', 'уеб', 'уёб',
    'выеб', 'выёб', 'недоеб', 'недоёб', 'перееб', 'переёб',
]

# Английские матерные слова
ENGLISH_PROFANITY = [
    'fuck', 'shit', 'bitch', 'ass', 'damn', 'cunt', 'dick', 'cock',
    'pussy', 'whore', 'slut', 'bastard', 'nigger', 'nigga', 'fag',
    'asshole', 'motherfucker', 'bullshit', 'piss', 'crap',
]

# Замены символов на буквы (leetspeak и обфускация)
CHAR_REPLACEMENTS = {
    '0': 'о', 'o': 'о', 'O': 'О',
    '3': 'е', 'e': 'е', 'E': 'Е', 'ё': 'е', 'Ё': 'Е',
    '4': 'а', 'a': 'а', 'A': 'А', '@': 'а',
    '1': 'и', 'i': 'и', 'I': 'И', '!': 'и',
    '6': 'б', 'b': 'б', 'B': 'Б',
    'y': 'у', 'Y': 'У', 'u': 'у', 'U': 'У',
    'x': 'х', 'X': 'Х', 'h': 'х', 'H': 'Х',
    'p': 'р', 'P': 'Р',
    'c': 'с', 'C': 'С', '$': 'с',
    'k': 'к', 'K': 'К',
    'm': 'м', 'M': 'М',
    'n': 'н', 'N': 'Н',
    '*': '', '.': '', '-': '', '_': '', ' ': '',
}


def normalize_text(text: str) -> str:
    """
    Нормализует текст для проверки на мат.
    Заменяет leetspeak символы на буквы и удаляет разделители.
    """
    result = text.lower()

    for char, replacement in CHAR_REPLACEMENTS.items():
        result = result.replace(char, replacement)

    # Удаляем повторяющиеся символы (напр. "хххуууууй" -> "хуй")
    result = re.sub(r'(.)\1{2,}', r'\1', result)

    return result


def contains_profanity(text: str) -> Tuple[bool, List[str]]:
    """
    Проверяет текст на наличие матерных слов.

    Args:
        text: Текст для проверки

    Returns:
        Tuple[bool, List[str]]: (содержит_мат, список_найденных_слов)
    """
    if not text:
        return False, []

    found_words = []
    normalized = normalize_text(text)
    original_lower = text.lower()

    # Проверка русских матерных корней
    for root in RUSSIAN_PROFANITY_ROOTS:
        if root in normalized:
            found_words.append(root)

    # Проверка английских матерных слов
    for word in ENGLISH_PROFANITY:
        if word in original_lower or word in normalized:
            found_words.append(word)

    return len(found_words) > 0, list(set(found_words))


def censor_text(text: str) -> str:
    """
    Цензурирует матерные слова в тексте, заменяя их звёздочками.

    Args:
        text: Исходный текст

    Returns:
        str: Текст с заменёнными матерными словами
    """
    if not text:
        return text

    result = text

    # Паттерны для замены (с учётом разных форм слов)
    patterns = []

    for root in RUSSIAN_PROFANITY_ROOTS:
        # Создаём паттерн, который ловит слово и его окончания
        pattern = re.compile(
            r'\b\w*' + re.escape(root) + r'\w*\b',
            re.IGNORECASE | re.UNICODE
        )
        patterns.append(pattern)

    for word in ENGLISH_PROFANITY:
        pattern = re.compile(
            r'\b' + re.escape(word) + r'\w*\b',
            re.IGNORECASE
        )
        patterns.append(pattern)

    for pattern in patterns:
        result = pattern.sub(lambda m: '*' * len(m.group()), result)

    return result


def validate_comment(text: str) -> Tuple[bool, str]:
    """
    Валидирует комментарий пользователя.

    Args:
        text: Текст комментария

    Returns:
        Tuple[bool, str]: (валиден, сообщение_об_ошибке)
    """
    if not text or not text.strip():
        return False, "Комментарий не может быть пустым"

    if len(text.strip()) < 10:
        return False, "Комментарий должен содержать минимум 10 символов"

    if len(text) > 2000:
        return False, "Комментарий не может превышать 2000 символов"

    has_profanity, found_words = contains_profanity(text)
    if has_profanity:
        return False, "Комментарий содержит нецензурную лексику. Пожалуйста, перефразируйте ваш отзыв."

    return True, ""
