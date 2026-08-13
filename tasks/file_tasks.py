import socket
from datetime import datetime, timezone
from typing import Any

from repositories.process_documents import (
    process_file_job,
    retrieve_job,
)
from worker.celery_app import celery_app


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@celery_app.task(name="tasks.file_tasks.remote_trigger", bind=True, max_retries=3)  # type: ignore
def remote_trigger(
    self: Any,
    file_job_ids: list[str],
) -> dict[str, Any]:

    for file_job_id in file_job_ids:
        current_job = retrieve_job(job_id=file_job_id)
        file_id = current_job.file_id
        print("Current job retrieved:", current_job, flush=True)
        if current_job.status == "chunked":
            return {
                "ok": True,
                "message": "Remote trigger skipped; job is already chunked",
                "worker_id": socket.gethostname(),
                "triggered_at": utc_now(),
                "file_id": str(file_id),
                "file_job_id": str(file_job_id),
                "final_status": current_job.status,
                "skipped": True,
            }


        user_file_id = current_job.user_file_id
        # result = process_file_job(
        #     file_id=file_id,
        #     file_job_id=file_job_id,
        #     bucket_name=f"user-{file_id}-bucket",
        #     storage_key=storage_key,
        #     user_file_id=user_file_id,
        # )

    return {
        "ok": True,
        "message": "Remote trigger task processed file job",
        "worker_id": socket.gethostname(),
        "triggered_at": utc_now(),
        # **result,
    }


@celery_app.task(name="tasks.file_tasks.queue_old_pending_document", bind=True, max_retries=3)  # type: ignore
def process_document(self: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Processed claimable file jobs",
        "worker_id": socket.gethostname(),
        "processed_at": utc_now(),
        "count": 1,
        "processed_count": 1,
        "failed_count": 0,
        "results": True,
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")  # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
