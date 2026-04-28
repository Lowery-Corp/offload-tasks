from celery.schedules import crontab

from worker.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "health-check-every-minute": {
        "task": "tasks.health.health_check",
        "schedule": 60.0,
    },
    "cleanup-old-results-daily": {
        "task": "tasks.health.cleanup_old_results",
        "schedule": crontab(hour=0, minute=0),
    },
}

celery_app.conf.beat_schedule = {
    "health-check-every-minute": {
        "task": "tasks.health.health_check",
        "schedule": 60.0,
    },
    "cleanup-old-results-daily": {
        "task": "tasks.health.cleanup_old_results",
        "schedule": crontab(hour=0, minute=0),
    },
}

