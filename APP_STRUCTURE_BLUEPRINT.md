# App Structure Blueprint

This repository is structured as a small Python background-task service. It uses Celery for task execution, Redis for broker/result storage, SQLAlchemy for optional async database access, and repository modules for external service integrations.

Use this document as the structural blueprint when asking agents to create new apps with the same shape.

## High-Level Layout

```text
offload-tasks/
├── db/
├── repositories/
├── schemas/
├── tasks/
├── worker/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── README.md
└── __init__.py
```

## Directory Purposes

### `worker/`

Owns Celery application setup and worker entrypoints.

- `worker/celery_app.py` creates the shared `celery_app` instance.
- `worker/worker.py` exposes the Celery app used by the worker process and imports task modules so Celery registers them.
- `worker/beat.py` configures scheduled tasks for Celery Beat.
- `worker/__init__.py` marks the directory as a Python package.

Use this directory for process-level worker configuration, task registration, queue settings, serializers, result expiration, timezone settings, and beat schedules. Avoid putting business logic here; task behavior belongs in `tasks/`.

### `tasks/`

Contains Celery task definitions.

- `tasks/health.py` contains health-check and cleanup tasks.
- `tasks/file_tasks.py` contains file/document-related task examples.
- `tasks/__init__.py` marks the directory as a Python package.

Use this directory for functions decorated with `@celery_app.task(...)`. Tasks should orchestrate work, validate task-level inputs, call repository/database helpers, and return JSON-serializable results. Keep reusable integration code out of task files.

### `db/`

Contains database connection/session infrastructure.

- `db/session.py` initializes an async SQLAlchemy engine, creates an async session factory, provides an async task-safe session context manager, and disposes the engine on shutdown.
- `db/__init__.py` marks the directory as a Python package.

Use this directory for database lifecycle code and shared persistence utilities. Keep domain queries or service-specific storage operations in repositories or dedicated modules rather than directly inside `db/session.py`.

### `repositories/`

Contains integrations with external systems and storage backends.

- `repositories/minio.py` wraps MinIO object-storage operations such as bucket creation, object upload, object read, object deletion, and bucket tree inspection.

Use this directory for adapters around external services such as object storage, third-party APIs, queues, search, or other infrastructure. Repositories should hide client setup and external API details from tasks.

### `schemas/`

Contains Pydantic data models used to validate structured inputs and outputs.

- `schemas/file.py` defines file-ingestion task input shape.
- `schemas/user.py` defines user/auth-related models.
- `schemas/__init__.py` marks the directory as a Python package.

Use this directory for request payloads, task payloads, result payloads, and shared DTO-style objects. Schemas should stay mostly declarative and should not own infrastructure behavior.

## Top-Level Files

### `Dockerfile`

Defines the Python runtime image.

Current responsibilities:

- Uses `python:3.13-slim`.
- Sets `/app` as the working directory.
- Installs OS dependencies and Python requirements.
- Copies the repository into the container.
- Sets `PYTHONPATH=/app`.

When creating a new app with this structure, keep the Dockerfile generic and let `docker-compose.yaml` decide which command each service runs.

### `docker-compose.yaml`

Defines the runtime services for local/container deployment.

Current services:

- `worker`: runs a Celery worker using `celery -A worker.worker:celery_app worker --loglevel=info`.
- `beat`: runs Celery Beat using `celery -A worker.beat:celery_app beat --loglevel=info`.
- `offload-task-cache`: runs Redis for Celery broker and result backend.
- `flower`: present as a commented-out optional monitoring service.

Current volumes:

- `offload-task-cache`: Redis data volume.
- `celery-beat-data`: Celery Beat schedule data volume.

Use this file to define process roles. Each service should share the same image when possible but run a different command.

### `requirements.txt`

Pins Python runtime dependencies.

Current dependency groups:

- Celery and Redis support.
- Async database support through SQLAlchemy and asyncpg.
- Environment/settings helpers.
- Flower for optional Celery monitoring.
- Watchfiles for development workflows.

When adding a new capability, keep dependencies explicit and pinned.

### `README.md`

Provides human-facing project documentation. The current README describes the intended stack, but parts of its project-structure example reference an older `app/` directory layout. Prefer this blueprint when generating new apps from the current repository shape.

### `__init__.py`

Marks the repository root as importable Python package context when needed. Most imports in this project rely on `PYTHONPATH=/app` and top-level packages such as `worker`, `tasks`, `db`, `schemas`, and `repositories`.

## Runtime Flow

1. Docker Compose starts Redis.
2. Docker Compose starts the Celery worker and Celery Beat containers.
3. `worker/celery_app.py` creates the Celery application using `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.
4. `worker/worker.py` imports task modules so worker processes know which tasks exist.
5. `worker/beat.py` registers periodic task schedules.
6. Task functions in `tasks/` execute work and call helpers from `db/`, `repositories/`, and `schemas/` as needed.

## Naming and Import Conventions

Use top-level package imports:

```python
from worker.celery_app import celery_app
from db.session import get_db_session
from schemas.file import NewFileIngestionTask
```

Use explicit Celery task names that match the module path:

```python
@celery_app.task(name="tasks.file_tasks.process_document")
def process_document():
    ...
```

Register new task modules in `worker/celery_app.py` by adding them to `include=[...]`, and import them in `worker/worker.py` if the worker entrypoint should force registration.

## Environment Variables

Core variables used by this structure:

- `CELERY_BROKER_URL`: Redis URL for Celery broker traffic.
- `CELERY_RESULT_BACKEND`: Redis URL for Celery task results.
- `DATABASE_URL`: async SQLAlchemy database URL.
- `DB_POOL_SIZE`: optional database pool size.
- `DB_MAX_OVERFLOW`: optional database overflow connection count.
- `DB_ECHO`: optional SQLAlchemy query logging toggle.

Repository integrations may require additional variables. For example, `repositories/minio.py` expects settings for MinIO connection details from `core.config.settings`; a new app should either include a matching `core/config.py` settings module or adapt the repository to its local settings pattern.

## Blueprint for New Apps

When creating a new app from this structure, keep the same package boundaries:

```text
new-app/
├── db/
│   ├── __init__.py
│   └── session.py
├── repositories/
│   └── <external_service>.py
├── schemas/
│   ├── __init__.py
│   └── <domain>.py
├── tasks/
│   ├── __init__.py
│   ├── health.py
│   └── <domain>_tasks.py
├── worker/
│   ├── __init__.py
│   ├── beat.py
│   ├── celery_app.py
│   └── worker.py
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

Recommended agent instructions for future apps:

- Put Celery app configuration only in `worker/celery_app.py`.
- Put periodic schedules only in `worker/beat.py`.
- Put task functions in `tasks/`, grouped by domain.
- Put external service clients and adapters in `repositories/`.
- Put async database setup in `db/session.py`.
- Put Pydantic models in `schemas/`.
- Keep task return values JSON serializable.
- Add new task modules to Celery `include` and worker imports.
- Keep Docker Compose service commands explicit for each process role.
- Keep the runtime image generic and reuse it for worker, beat, API, and monitoring processes when possible.

## Extension Points

Common additions for new apps:

- `core/config.py`: centralized settings using Pydantic Settings.
- `api/` or `app/`: FastAPI routes and application setup if the service also exposes HTTP endpoints.
- `services/`: domain orchestration that is shared by API handlers and tasks.
- `models/`: SQLAlchemy ORM models if the app owns database tables.
- `tests/`: unit and integration tests for tasks, repositories, and schema validation.

Add these only when the app needs them. The base structure is intentionally worker-first and keeps process setup, task orchestration, external integrations, and schemas separate.
