from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
