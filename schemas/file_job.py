import uuid
from datetime import datetime

from pydantic import BaseModel

class FileJob(BaseModel):
    id: int
    job_id: uuid.UUID
    file_id: uuid.UUID
    job_type: str
    status: str
    attempt_count: int
    max_attempts: int
    user_file_id: str | None
    storage_key: str | None
    bucket_name: str | None
    queue_name: str | None
    worker_id: str | None
    error_message: str | None
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

