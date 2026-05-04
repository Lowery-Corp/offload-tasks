# tasks/file_tasks.py

import asyncio
import os
import socket
from datetime import datetime, timezone
from typing import Any

from worker.celery_app import celery_app

JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
CLAIMABLE_STATUSES = ("pending", "queued")


@celery_app.task(name="tasks.file_tasks.process_document")
def process_document() -> dict[str, Any]:
    jobs = None # this will be the jobs retrieved from the database

    return {
        "ok": True,
        "message": "Claimed file jobs from file_job",
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results")
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
