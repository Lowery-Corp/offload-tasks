# app/main.py
from fastapi import FastAPI
from app.tasks.file_tasks import process_document

app = FastAPI()

@app.post("/documents/{document_id}/process")
async def queue_document_processing(document_id: int) -> dict[str, str]:
    task = process_document.delay(document_id)
    return {
        "task_id": task.id,
        "status": "queued",
    }