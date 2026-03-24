# Sync Service (Superconductivity Papers)

Сервис для синхронизации и хранения научных статей по сверхпроводимости.

Текущий статус реализации:
- F001: автоматическая синхронизация 1→4 (OAI-PMH, manifest index, PDF download, PDF→text→payload)
- F002: управление расписанием синхронизации (`/api/v1/scheduler/*`)
- F003: чтение статей (`GET /api/v1/papers`, детали, контент, статистика)
- F004: ручное добавление статей (`POST /api/v1/papers`, JSON и multipart)
- F005: health-check (`/health`, `/health/live`, `/health/ready`)

## 1. Требования

- Python 3.11+
- Docker (рекомендуется для PostgreSQL)
- PowerShell (команды ниже даны для Windows)

## 2. Быстрый старт

### 2.0. Docker Compose (одной командой)

```powershell
cd sync_service
copy .env.example .env
docker compose up --build
```

Проверка, что сервис поднялся:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

Ожидается `200 OK`.

Остановить:

```powershell
docker compose down
```

Остановить и удалить тома БД/хранилища:

```powershell
docker compose down -v
```

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
LOG_LEVEL=INFO
SERVICE_NAME=ArXiv Superconductor Papers Sync Service
SERVICE_VERSION=0.1.0

STORAGE_PATH=storage

# F001 sync settings
SYNC_OVERLAP_DAYS=2
SYNC_PROCESS_BATCH_SIZE=300

ARXIV_OAI_BASE_URL=https://oaipmh.arxiv.org/oai
ARXIV_OAI_SET=physics:cond-mat
ARXIV_MANIFEST_URL=
ARXIV_PDF_BASE_URL=https://arxiv.org/pdf
ARXIV_HTTP_TIMEOUT_SECONDS=60

# Optional S3 TAR download mode (F001 step 3)
ARXIV_PDF_USE_S3=False
ARXIV_S3_BUCKET=arxiv
ARXIV_S3_REGION=us-east-1
ARXIV_S3_REQUEST_PAYER=True

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

В консоль будут выводиться логи scheduler и sync pipeline (старт, прогресс, ошибки, итог).

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

### 3.3. Проверка автосинхронизации (F001)

F001 запускается через scheduler:

```powershell
curl -X POST http://localhost:8000/api/v1/scheduler/run
```

Проверить результат:

```powershell
curl http://localhost:8000/api/v1/scheduler/status
curl "http://localhost:8000/api/v1/papers?source=arxiv&offset=0&limit=20"
```

В БД:

```powershell
docker exec -it sync-postgres psql -U postgres -d sync_service -c "select source,last_status,last_success_datestamp,last_rows,total_rows from sync_state order by updated_at desc limit 3;"
docker exec -it sync-postgres psql -U postgres -d sync_service -c "select status,count(*) from paper group by status order by status;"
```

Ожидания:
- новые OAI-записи `cond-mat.supr-con` создаются как `paper.status=NEW` (шаг metadata sync)
- при наличии PDF статья доходит до `DONE`/`FILTERED`, ошибки фиксируются как `ERROR`/`NOT_FOUND`
- `sync_state` обновляет `last_success_datestamp` и `last_status`

### 3.4. Проверка чтения статей (F003)

```powershell
curl "http://localhost:8000/api/v1/papers?offset=0&limit=10"
curl http://localhost:8000/api/v1/papers/stats
```

### 3.5. Добавить статью без PDF (F004)

```powershell
curl -X POST http://localhost:8000/api/v1/papers `
  -H "Content-Type: application/json" `
  -d '{"title":"Manual Paper","source":"manual","authors":"Author A"}'
```

Ожидание:
- HTTP `201`
- `status = "DONE"`

### 3.6. Добавить статью с PDF (F004)

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

### 3.7. Проверка дедупликации (F004)

Повтори `POST` с тем же `source + external_id`:
- ожидается `409 Conflict`.

## 4. Тесты

Запуск целевых тестов:

```powershell
python -m pytest -q tests
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
