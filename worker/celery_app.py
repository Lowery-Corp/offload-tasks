import os
from kombu import Exchange, Queue

from celery import Celery

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "amqp://offload:offload@offload-task-broker:5672//",
)

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    "rpc://",
)

celery_app = Celery(
    "offload_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "tasks.health",
        "tasks.file_tasks",
    ],
)

celery_app.conf.update( # type: ignore
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,

    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("documents", Exchange("documents"), routing_key="documents"),
        Queue("maintenance", Exchange("maintenance"), routing_key="maintenance"),
    ),
)
