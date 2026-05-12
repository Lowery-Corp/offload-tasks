import uuid
import socket
from datetime import datetime, timezone
from typing import Any

from helpers.dependencies import logger
from auth.dependencies import get_auth_token
from repositories.process_documents import retrieve_jobs, update_job_status, parse_file, build_file_chunks
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
        assert job.bucket_name is not None, f"Job {job.job_id} is missing bucket_name"
        assert job.storage_key is not None, f"Job {job.job_id} is missing storage_key"

        # job_updated = update_job_status(job_id=str(job.job_id), new_status="queued", auth_token=auth_token)
        # assert job_updated.status == "queued", f"Failed to update job {job.job_id} to queued status"

        raw_chunks = parse_file(bucket_name=job.bucket_name, storage_key=job.storage_key)

        create_chunks = build_file_chunks(file_id=job.file_id, raw_chunks=raw_chunks)

        for chunk in create_chunks:
            logger.info(f"Chunk for file {job.file_id}: index={chunk.chunk_index}, text={chunk.chunk_text[:100]}...")

    return {
        "ok": True,
        "message": "Retrieved file jobs from crud endpoint",
        "worker_id": socket.gethostname(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "auth_token_used": auth_token[:10] + "...",
        "storage_keys": [job.storage_key for job in jobs],
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results") # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
