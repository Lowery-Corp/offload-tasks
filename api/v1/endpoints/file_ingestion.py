from fastapi import APIRouter, Depends

from auth.dependencies import authenticate_request
from schemas.user import AuthorizedUser
from schemas.file import NewFileIngestionTask
from repositories.minio import get_file_from_minio

router = APIRouter(tags=["ingestion"])


@router.post("/file", summary="Offload file ingestion task to Celery")
async def offload_file_ingestion_task(
    file_metadata: NewFileIngestionTask,
    authorized_user: AuthorizedUser = Depends(authenticate_request),
) -> dict[str, str | bool]:
    print(f"Received file ingestion request for user {authorized_user.username} (ID: {authorized_user.id})", flush=True)
    print(f"Is admin: {authorized_user.is_admin}", flush=True)
    print(f"File metadata: {file_metadata}", flush=True)

    bucket_name = f"""user-{file_metadata.user_id}-bucket"""

    user_file = await get_file_from_minio(bucket_name=bucket_name, file_path=file_metadata.storage_key)

    print(user_file.keys())

    print("Offloading file ingestion task to Celery...", flush=True)
    return {"message": "File ingestion task offloaded to Celery", "ok": True}