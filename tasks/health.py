from datetime import datetime, timezone
from typing import Any

from worker.celery_app import celery_app


@celery_app.task(name="tasks.health.health_check")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": "Celery worker is running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="tasks.health.cleanup_old_results")
def cleanup_old_results() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": "Cleanup task ran",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }