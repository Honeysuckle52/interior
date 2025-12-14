# INTERIER — Система бронирования помещений

![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

Полнофункциональная платформа для онлайн-бронирования помещений и административным контролем, разработанная на Django.

## Возможности

- Управление помещениями — добавление, редактирование, категоризация, удаление
- Управление категориями — добавление, редактирование, удаление
- Управление отзывами — добавление, редактирование, удаление
- Управление пользователями — редактирование, блокирование
- Онлайн-бронирование — выбор даты, времени и помещений через календарь
- Личный кабинет — история бронирований, просмотр избранных, редактирование профиля
- Система транзакций — информация о предоплате отправляется на почту
- Админ-панель — полный контроль над бронированиями, пользователями, помещениями, категориями и отзывами, отчетность
- Контроль пересечений — система предотвращает двойное бронирование

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Honeysuckle52/interior.git
cd renta
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте базу данных в `renta/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'interior',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

5. Примените миграции:
```bash
python manage.py makemigrations
python manage.py migrate
```

6. Загрузите тестовые данные:
```bash
python manage.py populate_db
```
7. Тестирование
```bash
python manage.py test rental
```

8. Запустите сервер:
```bash
python manage.py runserver
```

