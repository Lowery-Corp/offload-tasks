# app/tasks/document_tasks.py
from typing import Any
from schemas.file import NewFileIngestionTask
# from repositories.minio import get_file_from_minio
from worker.worker import celery_app

@celery_app.task(name="tasks.file_ingestion.process_document")
def process_document(file_metadata: NewFileIngestionTask) -> dict[str, Any]:
    print(f"File metadata: {file_metadata}", flush=True)
    # simulate long-running work
    bucket_name = f"""user-{file_metadata.user_id}-bucket"""
    storage_key = file_metadata.storage_key
    print(f"Processing document with storage key: {storage_key} from bucket: {bucket_name}", flush=True)
    # user_file = run(get_file_from_minio(bucket_name=bucket_name, file_path=storage_key))
    # print(user_file.keys())
    return {"ok": True, "document_id": storage_key}
