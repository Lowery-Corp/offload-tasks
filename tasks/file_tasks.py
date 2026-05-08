import socket
from datetime import datetime, timezone
from typing import Any

from auth.dependencies import get_auth_token
from repositories.process_documents import retrieve_jobs
from worker.celery_app import celery_app


@celery_app.task(name="tasks.file_tasks.process_document") # type: ignore
def process_document() -> dict[str, Any]:
    auth_token = get_auth_token()
    jobs = retrieve_jobs(auth_token)
    for job in jobs:
        print("Job:", job, flush=True)
    print(f"Retrieved {len(jobs)} file jobs from CRUD endpoint", flush=True)

    return {
        "ok": True,
        "message": "Retrieved file jobs from crud endpoint",
        "worker_id": socket.gethostname(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "jobs": jobs,
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results") # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
