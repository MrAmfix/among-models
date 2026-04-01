# Among Models

Мини-игра на FastAPI: игрок среди нескольких LLM-участников отвечает на вопросы, обсуждает раунды и пытается не выдать себя в финальном голосовании.

## Что внутри

- Backend: FastAPI + SQLAlchemy
- База данных: PostgreSQL
- Миграции: Alembic
- UI: Jinja2 + Bootstrap
- LLM-провайдер: OpenRouter API

## Основные возможности

- Регистрация/логин, роли `user` и `admin`
- Создание игры с выбором моделей
- 3 раунда: вопрос -> ответы -> обсуждение
- Финальное голосование и страница результатов
- Админ-панель:
  - выдача пользователям лимита игр
  - управление каталогом моделей (активация/деактивация, добавление)

## Требования

- Docker + Docker Compose (рекомендуемый запуск)
- или Python 3.11 и PostgreSQL 16 для локального запуска без Docker
- API-ключ OpenRouter

## Запуск через Docker (рекомендуется)

1. Подготовьте `.env` в корне проекта (можно на основе `.env.example`).
2. Убедитесь, что заполнены переменные:
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
   - `POSTGRES_DB`
   - `DB_PORT`
   - `WEB_PORT`
   - `SECRET_KEY`
   - `ADMIN_LOGIN`
   - `ADMIN_PASSWORD`
   - `OPENROUTER_API_KEY`
3. Запустите:

```bash
docker compose up --build
```

4. Откройте приложение:

```text
http://localhost:${WEB_PORT}
```

При старте контейнера `web` автоматически:
- применяет миграции Alembic,
- создаёт администратора из `ADMIN_LOGIN/ADMIN_PASSWORD`,
- запускает Uvicorn.

## Структура проекта

- `app/main.py` — инициализация приложения
- `app/routes/` — HTTP-роуты
- `app/services/` — игровая логика и интеграция с OpenRouter
- `app/models/` — SQLAlchemy-модели
- `alembic/` — миграции БД
- `app/templates/` — HTML-шаблоны
- `app/static/` — CSS/статические файлы
