# app/tasks/document_tasks.py
import time
from typing import Any
from worker import celery_app

@celery_app.task(name="app.tasks.process_document")
def process_document(document_id: int) -> dict[str, Any]:
    # simulate long-running work
    time.sleep(10)
    return {"status": "done", "document_id": document_id}
