from celery.schedules import crontab

from worker.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "health-check-every-minute": {
        "task": "tasks.health.health_check",
        "schedule": 60.0,
    },
    "health-cleanup-old-results-daily": {
        "task": "tasks.health.cleanup_old_results",
        "schedule": crontab(hour=0, minute=0),
    },
    "file-check-every-ten-secs": {
        "task": "tasks.file_tasks.process_document",
        "schedule": 10.0,
    },
    "file-cleanup-old-results-daily": {
        "task": "tasks.file_tasks.cleanup_old_results",
        "schedule": crontab(hour=0, minute=0),
    },
}
