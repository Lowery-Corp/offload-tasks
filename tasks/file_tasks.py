import socket
from datetime import datetime, timezone
from typing import Any

from helpers.http_helpers import get_client
from helpers.dependencies import logger
from repositories.process_documents import (
    run_jobs,
    retrieve_old_jobs,
)
from worker.celery_app import celery_app


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@celery_app.task(name="tasks.file_tasks.remote_trigger", bind=True, max_retries=3)  # type: ignore
def remote_trigger(
    self: Any,
    file_job_ids: list[str],
) -> dict[str, Any]:
    http_client = get_client()
    results: list[dict[str, Any]] = []
    try:
        results = run_jobs(file_job_ids=file_job_ids, http_client=http_client)
    except Exception as e:
        logger.error(f"Error processing remote trigger: {str(e)}", extra={"file_job_ids": file_job_ids})
        return {
            "ok": False,
            "message": f"Error processing remote trigger: {str(e)}",
            "worker_id": socket.gethostname(),
            "triggered_at": utc_now(),
            "file_job_id": file_job_ids,
            "final_status": [],
        }

    result_status = [result.get("ok", "failed") for result in results]

    return {
        "ok": True,
        "message": "Remote trigger skipped; job is already chunked",
        "worker_id": socket.gethostname(),
        "triggered_at": utc_now(),
        "file_job_id": file_job_ids,
        "final_status": result_status,
    }


@celery_app.task(name="tasks.file_tasks.queue_old_pending_document", bind=True, max_retries=3)  # type: ignore
def process_document(self: Any) -> dict[str, Any]:
    statuses_to_process = ["pending", "queued", "error"]
    http_client = None
    results: list[dict[str, Any]] = []
    old_jobs_ids: list[str] = []
    try:
        http_client = get_client()
        old_jobs_ids = retrieve_old_jobs(status=statuses_to_process, limit=10, client=http_client)
        results = run_jobs(file_job_ids=old_jobs_ids, http_client=http_client)

    except Exception as e:
        logger.error("Error processing old pending documents", extra={"error": str(e)})

    return {
        "ok": True,
        "message": "Processed old pending documents",
        "worker_id": socket.gethostname(),
        "triggered_at": utc_now(),
        "file_job_id": old_jobs_ids,
        "final_status": [result.get("ok", "failed") for result in results],
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")  # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
