import socket
import uuid
from datetime import datetime, timezone
from typing import Any

from auth.dependencies import get_auth_token
from helpers.dependencies import logger
from repositories.process_documents import (
    build_file_chunks,
    parse_file,
    push_chunks,
    retrieve_job,
    retrieve_jobs,
    update_job_status,
)
from schemas.api_request_errors import ApiRequestError
from worker.celery_app import celery_app


RETRYABLE_ERRORS = (ApiRequestError, TimeoutError, ConnectionError)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_uuid(value: uuid.UUID | str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid UUID") from exc


def retry_if_transient(task: Any, exc: Exception) -> None:
    if not isinstance(exc, RETRYABLE_ERRORS):
        return

    retry_count = getattr(task.request, "retries", 0)
    max_retries = getattr(task, "max_retries", 3)
    if retry_count >= max_retries:
        return

    countdown = min(60, 2 ** retry_count)
    raise task.retry(exc=exc, countdown=countdown)


def set_job_status(
    *,
    job_id: uuid.UUID,
    status: str,
    auth_token: str,
    required: bool = True,
) -> None:
    try:
        update_job_status(job_id=str(job_id), new_status=status, auth_token=auth_token)
    except Exception:
        if required:
            raise
        logger.warning(
            "Optional job status update failed",
            extra={"job_id": str(job_id), "status": status},
            exc_info=True,
        )


def mark_job_error(job_id: uuid.UUID, auth_token: str) -> None:
    try:
        set_job_status(job_id=job_id, status="error", auth_token=auth_token)
    except Exception:
        logger.exception("Failed to mark job as error", extra={"job_id": str(job_id)})


def process_file_job(
    *,
    file_id: uuid.UUID | str,
    file_job_id: uuid.UUID | str,
    bucket_name: str,
    storage_key: str,
    auth_token: str,
) -> dict[str, Any]:
    file_uuid = normalize_uuid(file_id, "file_id")
    job_uuid = normalize_uuid(file_job_id, "file_job_id")

    if not bucket_name:
        raise ValueError(f"Job {job_uuid} is missing bucket_name")
    if not storage_key:
        raise ValueError(f"Job {job_uuid} is missing storage_key")

    set_job_status(job_id=job_uuid, status="queued", auth_token=auth_token)
    set_job_status(job_id=job_uuid, status="processing", auth_token=auth_token, required=False)

    parsed_file = parse_file(bucket_name=bucket_name, storage_key=storage_key)

    set_job_status(job_id=job_uuid, status="chunking", auth_token=auth_token, required=False)
    set_job_status(job_id=job_uuid, status="embedding", auth_token=auth_token, required=False)

    new_chunks = build_file_chunks(file_id=file_uuid, file_chunk_data=parsed_file)
    create_status = push_chunks(new_chunks=new_chunks, auth_token=auth_token)
    if not create_status.get("ok"):
        raise RuntimeError(
            f"Failed to push chunks for job {job_uuid}: {create_status.get('error')}"
        )

    set_job_status(job_id=job_uuid, status="chunked", auth_token=auth_token)

    return {
        "file_id": str(file_uuid),
        "file_job_id": str(job_uuid),
        "bucket_name": bucket_name,
        "storage_key": storage_key,
        "chunk_count": len(new_chunks),
        "token_count": parsed_file.get("token_count", 0),
        "final_status": "chunked",
    }


@celery_app.task(name="tasks.file_tasks.remote_trigger", bind=True, max_retries=3)  # type: ignore
def remote_trigger(
    self: Any,
    file_id: uuid.UUID | str,
    storage_key: str,
    user_id: uuid.UUID | str,
    file_job_id: uuid.UUID | str,
) -> dict[str, Any]:
    auth_token = ""
    job_uuid: uuid.UUID | None = None

    try:
        job_uuid = normalize_uuid(file_job_id, "file_job_id")
        file_uuid = normalize_uuid(file_id, "file_id")
        user_uuid = normalize_uuid(user_id, "user_id")
        auth_token = get_auth_token()

        current_job = retrieve_job(job_id=str(job_uuid), auth_token=auth_token)
        if current_job.status == "chunked":
            return {
                "ok": True,
                "message": "Remote trigger skipped; job is already chunked",
                "worker_id": socket.gethostname(),
                "triggered_at": utc_now(),
                "file_id": str(file_uuid),
                "file_job_id": str(job_uuid),
                "final_status": current_job.status,
                "skipped": True,
            }

        result = process_file_job(
            file_id=file_uuid,
            file_job_id=job_uuid,
            bucket_name=f"user-{user_uuid}-bucket",
            storage_key=storage_key,
            auth_token=auth_token,
        )

        return {
            "ok": True,
            "message": "Remote trigger task processed file job",
            "worker_id": socket.gethostname(),
            "triggered_at": utc_now(),
            **result,
        }
    except Exception as exc:
        job_id_text = str(job_uuid or file_job_id)
        if auth_token and job_uuid is not None:
            mark_job_error(job_uuid, auth_token)
        retry_if_transient(self, exc)
        return {
            "ok": False,
            "message": f"Error processing job {job_id_text}: {exc}",
            "worker_id": socket.gethostname(),
            "triggered_at": utc_now(),
            "file_job_id": job_id_text,
            "storage_key": storage_key,
            "final_status": "error",
        }


@celery_app.task(name="tasks.file_tasks.queue_old_pending_document", bind=True, max_retries=3)  # type: ignore
def process_document(self: Any) -> dict[str, Any]:
    try:
        auth_token = get_auth_token()
        jobs = retrieve_jobs(auth_token)
    except Exception as exc:
        retry_if_transient(self, exc)
        return {
            "ok": False,
            "message": f"Error retrieving file jobs: {exc}",
            "worker_id": socket.gethostname(),
            "processed_at": utc_now(),
        }

    results: list[dict[str, Any]] = []
    for job in jobs:
        try:
            result = process_file_job(
                file_id=job.file_id,
                file_job_id=job.job_id,
                bucket_name=job.bucket_name or "",
                storage_key=job.storage_key or "",
                auth_token=auth_token,
            )
            results.append({"ok": True, **result})
        except Exception as exc:
            mark_job_error(job.job_id, auth_token)
            results.append(
                {
                    "ok": False,
                    "file_id": str(job.file_id),
                    "file_job_id": str(job.job_id),
                    "storage_key": job.storage_key,
                    "message": str(exc),
                    "final_status": "error",
                }
            )

    failed_count = sum(1 for result in results if not result["ok"])

    return {
        "ok": failed_count == 0,
        "message": "Processed claimable file jobs",
        "worker_id": socket.gethostname(),
        "processed_at": utc_now(),
        "count": len(jobs),
        "processed_count": len(results) - failed_count,
        "failed_count": failed_count,
        "results": results,
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")  # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
