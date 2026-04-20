from fastapi import APIRouter

router = APIRouter(tags=["file-ingestion"])


@router.get("")
async def offload_file_ingestion_task() -> dict[str, str | bool]:
    print("Offloading file ingestion task to Celery...", flush=True)
    return {"message": "File ingestion task offloaded to Celery", "ok": True}