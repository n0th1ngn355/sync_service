# ArXiv Superconductor Papers Sync Service

Сервис синхронизации и ручного добавления статей по сверхпроводимости для последующего использования в RAG.

## Scope по PRD

Поддерживаемые фичи:
- `F001`: авто-синхронизация из arXiv (metadata -> PDF -> text -> payload)
- `F002`: управление расписанием синхронизации
- `F003`: чтение статей и статистики
- `F004`: ручное добавление статей (JSON / multipart + PDF)
- `F005`: health-check эндпоинты

Не входит в активный scope:
- legacy `users` feature (`/api/v1/users`) удалена из runtime-логики.

## Требования

- Python `3.11+`
- Docker + Docker Compose
- PostgreSQL (локально или в Docker)

## Конфигурация

1. Создай `.env` из шаблона:

```powershell
cd sync_service
copy .env.example .env
```

2. Обязательные параметры:
- блок `Database`
- `STORAGE_PATH`
- `SCHEDULER_DEFAULT_CRON`, `SCHEDULER_JOB_NAME`

Все переменные задокументированы в `.env.example`.

## Быстрый запуск (Docker Compose)

```powershell
cd sync_service
docker compose up --build
```

Проверка:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

Остановка:

```powershell
docker compose down
```

## Локальный запуск без Compose

1. Установить зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Применить миграции:

```powershell
python -m alembic upgrade head
```

3. Запустить сервис:

```powershell
python main.py
```

Swagger UI:
- `http://localhost:8000/docs`

## API (PRD)

### F005 Health
- `GET /health`
- `GET /health/live`
- `GET /health/ready`

### F002 Scheduler
- `GET /api/v1/scheduler/status`
- `PUT /api/v1/scheduler/schedule`
- `POST /api/v1/scheduler/run`
- `POST /api/v1/scheduler/pause`
- `POST /api/v1/scheduler/resume`

### F003 Papers Read
- `GET /api/v1/papers`
- `GET /api/v1/papers/stats`
- `GET /api/v1/papers/{paper_id}`
- `GET /api/v1/papers/{paper_id}/content`

### F004 Manual Add
- `POST /api/v1/papers`

Поддерживаются:
- `application/json` (добавление без PDF)
- `multipart/form-data` (metadata + PDF)

## Базовый операционный сценарий

1. Проверить, что сервис готов:

```powershell
curl http://localhost:8000/health/ready
```

2. Запустить синхронизацию вручную:

```powershell
curl -X POST http://localhost:8000/api/v1/scheduler/run
```

3. Проверить статус расписания и последние результаты:

```powershell
curl http://localhost:8000/api/v1/scheduler/status
```

4. Проверить данные в API чтения:

```powershell
curl "http://localhost:8000/api/v1/papers?offset=0&limit=20"
curl http://localhost:8000/api/v1/papers/stats
```

## Тесты

```powershell
python -m pytest -q tests/F001_auto_sync tests/F002_scheduler tests/F003_papers_read tests/F004_manual_add tests/F005_health_check
```

## Структура проекта

- `api/` - HTTP endpoints
- `service/` - бизнес-логика
- `repository/` - доступ к данным
- `model/` - SQLAlchemy модели
- `schema/` - Pydantic схемы
- `core/` - конфиг и DB-инфраструктура
- `migrations/` - Alembic миграции
- `tests/` - интеграционные и feature-тесты
- `storage/` - артефакты PDF/TXT
