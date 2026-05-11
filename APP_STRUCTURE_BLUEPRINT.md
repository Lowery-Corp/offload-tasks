# App Structure Blueprint

This repository is structured as a small Python background-task service. It uses Celery for task execution, RabbitMQ for broker delivery, and repository/helper modules for external service integrations.

Use this document as the structural blueprint when asking agents to create new apps with the same shape.

## High-Level Layout

```text
offload-tasks/
├── auth/
├── helpers/
├── http_request/
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

Use this directory for functions decorated with `@celery_app.task(...)`. Tasks should orchestrate work, validate task-level inputs, call auth/repository/helper modules, and return JSON-serializable results. Keep reusable integration code out of task files.

### `auth/`

Contains authentication helpers for task-to-service API calls.

- `auth/dependencies.py` reads auth endpoint settings and internal credentials from the environment, posts login requests, extracts a token from either response cookies or JSON response bodies, and raises `ApiRequestError` when authentication fails.

Use this directory for authentication flows that are shared by tasks and repositories. Keep endpoint-specific CRUD logic in `repositories/`.

### `http_request/`

Contains low-level HTTP utilities.

- `http_request/http_helpers.py` provides `request_json(...)`, a small JSON HTTP client built on the Python standard library. It supports JSON request bodies, custom headers, response header capture, timeout handling, and normalized `ApiRequestError` failures.

Use this directory for reusable transport-level helpers. Keep auth, domain URL construction, and response interpretation outside this package.

### `helpers/`

Contains small shared utility functions.

- `helpers/dependencies.py` currently provides `join_url(...)` for safely combining base URLs and paths.

Use this directory for simple cross-cutting utilities that do not belong to a domain repository.

### `repositories/`

Contains integrations with external systems and storage backends.

- `repositories/minio.py` wraps MinIO object-storage operations such as bucket creation, object upload, object read, object deletion, and bucket tree inspection.
- `repositories/process_documents.py` retrieves claimable file jobs from the Scrappyard CRUD endpoint. It requests `pending` and `queued` jobs up to `FILE_JOB_BATCH_SIZE`, passing the auth token as an `access_token` cookie.

Use this directory for adapters around external services such as object storage, third-party APIs, queues, search, or other infrastructure. Repositories should hide client setup and external API details from tasks.

### `schemas/`

Contains Pydantic data models used to validate structured inputs and outputs.

- `schemas/file.py` defines file-ingestion task input shape.
- `schemas/api_request_errors.py` defines `ApiRequestError`, the shared exception raised by HTTP/auth integration helpers.
- `schemas/user.py` defines user/auth-related models.
- `schemas/__init__.py` marks the directory as a Python package.

Use this directory for request payloads, task payloads, result payloads, and shared DTO-style objects. Schemas should stay mostly declarative and should not own infrastructure behavior.

## Top-Level Files

### `Dockerfile`

Defines the Python runtime image.

Current responsibilities:

- Uses `python:3.13-slim`.
- Sets `/app` as the working directory.
- Installs Python requirements.
- Copies the repository into the container.
- Sets `PYTHONPATH=/app`.
- Defines a default `uvicorn app.main:app` command, although the current Compose worker and beat services override it.

When creating a new app with this structure, keep the Dockerfile generic and let `docker-compose.yaml` decide which command each service runs. If no API package exists, prefer a neutral default command or rely on Compose overrides.

### `docker-compose.yaml`

Defines the runtime services for local/container deployment.

Current services:

- `worker`: runs a Celery worker using `celery -A worker.worker:celery_app worker --loglevel=info`.
- `beat`: runs Celery Beat using `celery -A worker.beat:celery_app beat --loglevel=info`.
- `offload-task-broker`: runs RabbitMQ for Celery broker delivery.
- `flower`: present as a commented-out optional monitoring service.

Current volumes:

- `offload-task-broker`: RabbitMQ data volume.
- `celery-beat-data`: declared for Celery Beat schedule data and mounted at `/app/celerybeat`.

Current environment wiring:

- `worker` reads `.env` and sets RabbitMQ broker and Celery result backend URLs.
- `beat` sets RabbitMQ broker and Celery result backend URLs.

Use this file to define process roles. Each service should share the same image when possible but run a different command.

### `requirements.txt`

Pins Python runtime dependencies.

Current dependency groups:

- Celery and RabbitMQ/AMQP support.
- Pydantic and settings helpers.
- Environment/settings helpers.
- MinIO object-storage client support.
- Standard auth/security-related packages used by adjacent integrations.
- Flower for optional Celery monitoring.
- Watchfiles for development workflows.
- SQLAlchemy and asyncpg remain pinned, but the current repository does not include a `db/` package.

When adding a new capability, keep dependencies explicit and pinned.

### `README.md`

Provides human-facing project documentation. The current README describes a broader FastAPI plus Celery stack, but parts of its project-structure and command examples reference an older `app/` directory layout. Prefer this blueprint when generating new apps from the current repository shape.

### `__init__.py`

Marks the repository root as importable Python package context when needed. Most imports in this project rely on `PYTHONPATH=/app` and top-level packages such as `worker`, `tasks`, `auth`, `helpers`, `http_request`, `schemas`, and `repositories`.

## Runtime Flow

1. Docker Compose starts RabbitMQ.
2. Docker Compose starts the Celery worker and Celery Beat containers.
3. `worker/celery_app.py` creates the Celery application using `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.
4. `worker/worker.py` imports task modules so worker processes know which tasks exist.
5. `worker/beat.py` registers periodic task schedules.
6. Beat currently schedules `tasks.file_tasks.process_document` every 10 seconds.
7. `process_document` authenticates through `auth.dependencies.get_auth_token()`.
8. The task passes the token to `repositories.process_documents.retrieve_jobs(...)`.
9. `retrieve_jobs(...)` calls the Scrappyard CRUD endpoint for `pending` and `queued` jobs and returns the retrieved jobs.
10. Task functions in `tasks/` execute work and call helpers from `auth/`, `helpers/`, `http_request/`, `repositories/`, and `schemas/` as needed.

## Naming and Import Conventions

Use top-level package imports:

```python
from worker.celery_app import celery_app
from auth.dependencies import get_auth_token
from repositories.process_documents import retrieve_jobs
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

- `CELERY_BROKER_URL`: RabbitMQ AMQP URL for Celery broker traffic.
- `CELERY_RESULT_BACKEND`: Celery result backend URL; defaults to `rpc://`.
- `AUTH_API_URL`: base URL for the auth service.
- `AUTH_LOGIN_PATH`: login path on the auth service.
- `INTERNAL_API_USERNAME`: internal service username/email used to authenticate.
- `INTERNAL_API_PASSWORD`: internal service password used to authenticate.
- `SCRAPPYS_SCRAPYARD_URL`: base URL for the Scrappyard CRUD service.
- `FILE_JOBS_PATH`: path for file job listing; defaults to `/api/v1/file-jobs`.
- `FILE_JOB_BATCH_SIZE`: maximum number of jobs to retrieve per polling run; defaults to `10`.
- `API_REQUEST_TIMEOUT`: timeout in seconds for JSON HTTP requests; defaults to `10`.

Object-storage integrations may require additional variables:

- `MINIO_API_URL`: MinIO endpoint.
- `MINIO_ROOT_USER`: MinIO access key.
- `MINIO_ROOT_PASSWORD`: MinIO secret key.
- `MINIO_SECURE`: whether MinIO should use TLS; defaults to `false`.

## Blueprint for New Apps

When creating a new app from this structure, keep the same package boundaries:

```text
new-app/
├── auth/
│   └── dependencies.py
├── helpers/
│   └── dependencies.py
├── http_request/
│   └── http_helpers.py
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
- Put shared authentication helpers in `auth/`.
- Put low-level HTTP helpers in `http_request/`.
- Put small URL/path/config utility functions in `helpers/`.
- Put external service clients and adapters in `repositories/`.
- Put Pydantic models in `schemas/`.
- Keep task return values JSON serializable.
- Add new task modules to Celery `include` and worker imports.
- Keep Docker Compose service commands explicit for each process role.
- Keep the runtime image generic and reuse it for worker, beat, API, and monitoring processes when possible.

## Extension Points

Common additions for new apps:

- `core/config.py`: centralized settings using Pydantic Settings.
- `api/` or `app/`: FastAPI routes and application setup if the service also exposes HTTP endpoints.
- `db/`: async SQLAlchemy connection/session infrastructure if the service owns direct database access.
- `services/`: domain orchestration that is shared by API handlers and tasks.
- `models/`: SQLAlchemy ORM models if the app owns database tables.
- `tests/`: unit and integration tests for tasks, repositories, and schema validation.

Add these only when the app needs them. The base structure is intentionally worker-first and keeps process setup, task orchestration, authentication/transport helpers, external integrations, and schemas separate.
