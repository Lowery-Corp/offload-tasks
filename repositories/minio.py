from functools import lru_cache
from io import BytesIO
from minio import Minio
from minio.deleteobjects import DeleteObject
from typing import Any

from core.config import settings


@lru_cache
def get_minio_client() -> Minio:
    return Minio(
        settings.minio_api_url,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )


async def get_bucket_structure(bucket_name: str) -> dict[str, Any]:
    minio_client = get_minio_client()

    objects = minio_client.list_objects(bucket_name, recursive=True)
    structure: dict[str, Any] = {}

    for obj in objects:
        if not obj.object_name:
            continue

        parts = obj.object_name.split("/")
        current_level = structure

        for part in parts[:-1]:
            current_level = current_level.setdefault(part, {})

        current_level[parts[-1]] = None

    return structure["home"] if "home" in structure else structure


async def create_bucket(bucket_name: str) -> dict[str, Any]:
    minio_client = get_minio_client()
    try:
        minio_client.make_bucket(bucket_name)
        return {"message": f"Bucket '{bucket_name}' created successfully.", "ok": True}
    except Exception as e:
        return {"error": str(e)}


async def upload_file_to_minio(
    bucket_name: str,
    file_path: str,
    file_data: bytes,
) -> dict[str, Any]:
    minio_client = get_minio_client()

    try:
        data_stream = BytesIO(file_data)

        uploaded_file = minio_client.put_object(
            bucket_name,
            file_path,
            data_stream,
            length=len(file_data),
        )

        return {
            "uploaded_file": {
                "object_name": uploaded_file.object_name,
                "etag": uploaded_file.etag,
            },
            "message": f"File '{file_path}' uploaded successfully to bucket '{bucket_name}'.",
            "ok": True,
        }
    except Exception as e:
        return {"error": str(e), "ok": False}


async def get_file_from_minio(bucket_name: str, file_path: str) -> dict[str, Any]:
    minio_client = get_minio_client()

    try:
        response = minio_client.get_object(bucket_name, file_path)
        file_data = response.read()
        response.close()
        response.release_conn()

        return {"file_data": file_data, "ok": True}
    except Exception as e:
        return {"error": str(e), "ok": False}


async def delete_path_from_minio(bucket_name: str, path: str) -> dict[str, Any]:
    minio_client = get_minio_client()

    try:
        normalized_path = path.strip()

        if normalized_path.endswith("/"):
            prefix = normalized_path.rstrip("/") + "/"

            objects = minio_client.list_objects(
                bucket_name,
                prefix=prefix,
                recursive=True,
            )

            delete_objects = [DeleteObject(obj.object_name) for obj in objects] # type: ignore

            if not delete_objects:
                return {
                    "message": f"No objects found under folder '{prefix}' in bucket '{bucket_name}'.",
                    "ok": True,
                    "deleted_count": 0,
                }

            errors = list(minio_client.remove_objects(bucket_name, delete_objects))

            if errors:
                return {
                    "message": f"Folder '{prefix}' partially deleted from bucket '{bucket_name}'.",
                    "ok": False,
                    "errors": [str(error) for error in errors],
                }

            return {
                "message": f"Folder '{prefix}' deleted successfully from bucket '{bucket_name}'.",
                "ok": True,
                "deleted_count": len(delete_objects),
            }

        minio_client.remove_object(bucket_name, normalized_path)
        return {
            "message": f"File '{normalized_path}' deleted successfully from bucket '{bucket_name}'.",
            "ok": True,
            "deleted_count": 1,
        }

    except Exception as e:
        return {"error": str(e), "ok": False}