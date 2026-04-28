from worker.celery_app import celery_app

# Import tasks so the worker registers them.
import tasks.health  # noqa: F401


__all__ = ["celery_app"]