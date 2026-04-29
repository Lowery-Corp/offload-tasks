# tasks/file_tasks.py

from typing import Any

from worker.celery_app import celery_app


@celery_app.task(name="tasks.file_tasks.process_document")
def process_document() -> dict[str, Any]:


    return {
        "ok": True,
        "message": "Document processed successfully",
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")
def cleanup_old_results() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": "Cleanup task ran",
    }
