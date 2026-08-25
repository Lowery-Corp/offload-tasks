import socket
from datetime import datetime, timezone
from typing import Any

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

    result = run_jobs(file_job_ids=file_job_ids)

    # if current_job.status == "chunked":
    #     return {
    #         "ok": True,
    #         "message": "Remote trigger skipped; job is already chunked",
    #         "worker_id": socket.gethostname(),
    #         "triggered_at": utc_now(),
    #         "file_id": str(file_id),
    #         "file_job_id": str(file_job_id),
    #         "final_status": current_job.status,
    #         "skipped": True,
    #     }

    return {
        "ok": True,
        "message": "Remote trigger task processed file job",
        "worker_id": socket.gethostname(),
        "triggered_at": utc_now(),
        # **result,
    }


@celery_app.task(name="tasks.file_tasks.queue_old_pending_document", bind=True, max_retries=3)  # type: ignore
def process_document(self: Any) -> dict[str, Any]:
    statuses_to_process = ["pending", "queued", "error"]
    old_jobs_ids = retrieve_old_jobs(status=statuses_to_process, limit=10)

    result = run_jobs(file_job_ids=old_jobs_ids)
    logger.info("Processed claimable file jobs", extra={"result": result})
    return {}


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")  # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
