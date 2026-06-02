import uuid
import socket
from datetime import datetime, timezone
from typing import Any

from auth.dependencies import get_auth_token
from worker.celery_app import celery_app
from repositories.process_documents import retrieve_jobs, update_job_status, parse_file, build_file_chunks, push_chunks


@celery_app.task(name="tasks.file_tasks.remote_trigger") # type: ignore
def remote_trigger(
    file_id: uuid.UUID,
    storage_key: str,
    user_id: uuid.UUID,
    file_job_id: uuid.UUID,
) -> dict[str, Any]:

    # assert job.bucket_name is not None, f"Job {job.job_id} is missing bucket_name"
    # assert job.storage_key is not None, f"Job {job.job_id} is missing storage_key"

    # job_updated = update_job_status(job_id=str(job.job_id), new_status="queued", auth_token=auth_token)
    # assert job_updated.status == "queued", f"Failed to update job {job.job_id} to queued status"

    # raw_chunks = parse_file(bucket_name=job.bucket_name, storage_key=job.storage_key)

    # new_chunks = build_file_chunks(file_id=job.file_id, file_chunk_data=raw_chunks)

    # create_status = push_chunks(new_chunks=new_chunks, auth_token=auth_token)
    # assert create_status.get("ok"), f"Failed to push chunks for job {job.job_id}: {create_status.get('error')}"

    # job_updated = update_job_status(job_id=str(job.job_id), new_status="chunked", auth_token=auth_token)
    # assert job_updated.status == "chunked", f"Failed to update job {job.job_id} to queued status"

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

        try:
            job_updated = update_job_status(job_id=str(job.job_id), new_status="queued", auth_token=auth_token)
            assert job_updated.status == "queued", f"Failed to update job {job.job_id} to queued status"

            raw_chunks = parse_file(bucket_name=job.bucket_name, storage_key=job.storage_key)

            new_chunks = build_file_chunks(file_id=job.file_id, file_chunk_data=raw_chunks)

            create_status = push_chunks(new_chunks=new_chunks, auth_token=auth_token)
            assert create_status.get("ok"), f"Failed to push chunks for job {job.job_id}: {create_status.get('error')}"

            job_updated = update_job_status(job_id=str(job.job_id), new_status="chunked", auth_token=auth_token)
            assert job_updated.status == "chunked", f"Failed to update job {job.job_id} to queued status"
        except Exception as e:
            update_job_status(job_id=str(job.job_id), new_status="error", auth_token=auth_token)
            return {
                "ok": False,
                "message": f"Error processing job {job.job_id}: {str(e)}",
                "worker_id": socket.gethostname(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "auth_token_used": auth_token[:10] + "...",
                "storage_key": job.storage_key,
            }


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
