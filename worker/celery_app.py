import os

from celery import Celery

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "redis://offload-task-cache:6379/0",
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "redis://offload-task-cache:6379/1",
)

celery_app = Celery(
    "offload_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "tasks.health",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
)