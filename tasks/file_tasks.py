import uuid
import socket
from datetime import datetime, timezone
from typing import Any

from auth.dependencies import get_auth_token
from repositories.process_documents import retrieve_jobs, update_job_status
from worker.celery_app import celery_app


@celery_app.task(name="tasks.file_tasks.remote_trigger") # type: ignore
def remote_trigger(
    file_id: uuid.UUID,
    storage_key: str,
    user_id: uuid.UUID,
    file_job_id: uuid.UUID,
) -> dict[str, Any]:

    return {
        "ok": True,
        "message": "Remote trigger task ran",
        "worker_id": socket.gethostname(),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(name="tasks.file_tasks.queue_old_pending_document") # type: ignore
def process_document() -> dict[str, Any]:
    auth_token = get_auth_token()
    jobs = retrieve_jobs(auth_token)
    for job in jobs:
        job_updated = update_job_status(job_id=str(job.job_id), new_status="queued", auth_token=auth_token)
        assert job_updated.status == "queued", f"Failed to update job {job.job_id} to queued status"

    return {
        "ok": True,
        "message": "Retrieved file jobs from crud endpoint",
        "worker_id": socket.gethostname(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "auth_token_used": auth_token[:10] + "...",
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results") # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
