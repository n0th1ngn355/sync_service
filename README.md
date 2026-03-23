# Sync Service (Superconductivity Papers)

Сервис для синхронизации и хранения научных статей по сверхпроводимости.

Текущий статус реализации:
- F002: управление расписанием синхронизации (`/api/v1/scheduler/*`)
- F003: чтение статей (`GET /api/v1/papers`, детали, контент, статистика)
- F004: ручное добавление статей (`POST /api/v1/papers`, JSON и multipart)
- F005: health-check (`/health`, `/health/live`, `/health/ready`)

## 1. Требования

- Python 3.11+
- Docker (рекомендуется для PostgreSQL)
- PowerShell (команды ниже даны для Windows)

## 2. Быстрый старт

### 2.1. Виртуальное окружение и зависимости

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

### 2.2. Поднять PostgreSQL в Docker

```powershell
docker run --name sync-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=sync_service `
  -p 5432:5432 -d postgres:16
```

Если порт `5432` занят, используй `-p 5433:5432` и выстави `DB_PORT=5433` в `.env`.

### 2.3. Настроить `.env`

Минимальный пример:

```env
MODE_DEBUG=True
SERVICE_NAME=ArXiv Superconductor Papers Sync Service
SERVICE_VERSION=0.1.0

STORAGE_PATH=storage

# F002 scheduler defaults
SCHEDULER_JOB_NAME=sync_pipeline
SCHEDULER_DEFAULT_CRON=0 * * * *

DB_ENGINE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sync_service
DB_USER=postgres
DB_PASSWORD=postgres
```

### 2.4. Применить миграции

```powershell
python -m alembic upgrade head
python -m alembic current
```

### 2.5. Запустить сервис

```powershell
python main.py
```

Swagger:
- `http://localhost:8000/docs`

## 3. Ручная проверка API

### 3.1. Health-check (F005)

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### 3.2. Scheduler API (F002)

Получить статус расписания:

```powershell
curl http://localhost:8000/api/v1/scheduler/status
```

Обновить расписание cron:

```powershell
curl -X PUT http://localhost:8000/api/v1/scheduler/schedule `
  -H "Content-Type: application/json" `
  -d '{"cron_expression":"0 3 * * *"}'
```

Обновить расписание preset:

```powershell
curl -X PUT http://localhost:8000/api/v1/scheduler/schedule `
  -H "Content-Type: application/json" `
  -d '{"preset":"weekly"}'
```

Ручной запуск:

```powershell
curl -X POST http://localhost:8000/api/v1/scheduler/run
```

Пауза / возобновление:

```powershell
curl -X POST http://localhost:8000/api/v1/scheduler/pause
curl -X POST http://localhost:8000/api/v1/scheduler/resume
```

Ожидания:
- `/run`: `202 Accepted`, если не запущено; `409 Conflict`, если уже выполняется
- `/schedule`: изменения применяются без перезапуска (hot reload)

### 3.3. Проверка чтения статей (F003)

```powershell
curl "http://localhost:8000/api/v1/papers?offset=0&limit=10"
curl http://localhost:8000/api/v1/papers/stats
```

### 3.4. Добавить статью без PDF (F004)

```powershell
curl -X POST http://localhost:8000/api/v1/papers `
  -H "Content-Type: application/json" `
  -d '{"title":"Manual Paper","source":"manual","authors":"Author A"}'
```

Ожидание:
- HTTP `201`
- `status = "DONE"`

### 3.5. Добавить статью с PDF (F004)

```powershell
curl -X POST http://localhost:8000/api/v1/papers `
  -F "metadata={\"title\":\"Test Paper\",\"source\":\"manual\"}" `
  -F "file=@C:/tmp/test.pdf;type=application/pdf"
```

Ожидание:
- HTTP `201`
- `status = "PROCESSING"`
- PDF сохраняется в `STORAGE_PATH/papers/<paper_id>/...`

Важно:
- Полная фоновая обработка PDF после загрузки — следующими блоками пайплайна.

### 3.6. Проверка дедупликации (F004)

Повтори `POST` с тем же `source + external_id`:
- ожидается `409 Conflict`.

## 4. Тесты

Запуск целевых тестов:

```powershell
python -m pytest -q tests\F002_scheduler tests\F003_papers_read tests\F004_manual_add tests\F005_health_check
```

## 5. Работа с Alembic

Полезные команды:

```powershell
python -m alembic current
python -m alembic history
python -m alembic upgrade head
```

Создать новую миграцию:

```powershell
python -m alembic revision --autogenerate -m "add ..."
python -m alembic upgrade head
```

### Важное правило

- `upgrade` выполняет SQL миграций и меняет схему БД.
- `stamp` только записывает версию в `alembic_version`, но не выполняет SQL.

`stamp` использовать только осознанно.

## 6. Типовые проблемы

### Ошибка `relation "paper" does not exist`

Почти всегда это рассинхрон миграций.

Проверка:

```powershell
python -c "from core.config import configs; print(configs.database_url_sync)"
python -m alembic current
docker exec -it sync-postgres psql -U postgres -d sync_service -c "\dt public.*"
```

Если в `alembic_version` стоит `head`, а таблиц нет (на ранней стадии проекта, когда данных нет):

```powershell
python -m alembic stamp base
python -m alembic upgrade head
```

### Ошибка `Pipeline is already running`

`POST /api/v1/scheduler/run` уже выполняется в другом запуске.
Подожди завершения и повтори запрос.

## 7. Структура проекта

- `api/` — HTTP-эндпоинты
- `service/` — бизнес-логика
- `repository/` — доступ к БД
- `model/` — SQLAlchemy-модели
- `schema/` — Pydantic-схемы
- `migrations/` — Alembic-миграции
- `tests/` — тесты по фичам
- `storage/` — файловое хранилище (PDF/TXT)
