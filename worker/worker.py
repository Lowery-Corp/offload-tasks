# worker/worker.py

from worker.celery_app import celery_app

import tasks.health  # noqa: F401
import tasks.file_tasks  # noqa: F401

__all__ = ["celery_app"]
