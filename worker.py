from celery import Celery # type: ignore

from core.config import settings

CELERY_BROKER = f"""{settings.redis_url}/0"""
CELERY_BROKER_BACKEND = f"""{settings.redis_url}/1"""

celery_app = Celery(
    "Offload Tasks",
    broker=CELERY_BROKER,
    backend=CELERY_BROKER_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)