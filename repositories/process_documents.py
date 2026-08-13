import os
import tempfile
import hashlib
from typing import Any
from httpx import Client
import pymupdf4llm
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from helpers.dependencies import join_url, logger
from helpers.http_helpers import CLIENT
from schemas.file_job import FileJob
from schemas.file_chunk import FileChunkCreate
from repositories.minio import get_file_from_minio
from repositories.openapi import create_embeddings

JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
CLAIMABLE_STATUSES = ("pending")
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", None)
FILE_JOBS_PATH = os.getenv("FILE_JOBS_PATH", "/api/v1/file-jobs")
FILES_PATH = os.getenv("FILES_PATH", "/api/v1/files")

# file parsing and chunking settings
ENCODING_NAME = "cl100k_base"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def set_job_status(
    *,
    job_id: str,
    status: str,
    required: bool = True,
) -> None:
    try:
        update_job_status(job_id=str(job_id), new_status=status)
    except Exception:
        if required:
            raise
        logger.warning(
            "Optional job status update failed",
            extra={"job_id": str(job_id), "status": status},
            exc_info=True,
        )


def mark_job_error(job_id: str, auth_token: str) -> None:
    try:
        set_job_status(job_id=job_id, status="error")
    except Exception:
        logger.exception("Failed to mark job as error", extra={"job_id": str(job_id)})


def set_file_status(
    *,
    user_file_id: int | str,
    status: str,
    auth_token: str,
    required: bool = True,
) -> None:
    try:
        update_file_status(
            user_file_id=str(user_file_id),
            new_status=status,
            auth_token=auth_token,
        )
    except Exception:
        if required:
            raise
        logger.warning(
            "Optional file status update failed",
            extra={"user_file_id": str(user_file_id), "status": status},
            exc_info=True,
        )


def mark_file_error(user_file_id: int | str | str, auth_token: str) -> None:
    try:
        set_file_status(user_file_id=user_file_id, status="error", auth_token=auth_token)
    except Exception:
        logger.exception(
            "Failed to mark file as error",
            extra={"user_file_id": str(user_file_id)},
        )


def retrieve_job(job_id: str, client: Client = CLIENT) -> FileJob:
    print("CLIENT", client.headers, flush=True)
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"

    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/{job_id}")
    print("Retrieving job:", url, flush=True)
    response = client.get(url)
    response.raise_for_status()
    file_job = FileJob(**response.json())

    return file_job


def update_job_status(job_id: str, new_status: str, client: Client = CLIENT) -> FileJob:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/{job_id}")
    print("Updating job status:", url, new_status, flush=True)
    quit()

    payload = {"status": new_status}
    response = client.patch(url, json=payload)
    updated_job = FileJob(**response.json())

    if updated_job.status != new_status:
        raise RuntimeError(
            f"Expected job {job_id} to be {new_status}, got {updated_job.status}"
        )

    return updated_job


def update_file_status(user_file_id: str, new_status: str, client: Client) -> dict[str, Any]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILES_PATH}/{user_file_id}")

    payload = {"status": new_status}
    response = client.patch(url, json=payload)
    response.raise_for_status()
    updated_file = response.json()

    return updated_file


def extract_pdf_to_markdown(file_path: str) -> str:
    return pymupdf4llm.to_markdown(file_path)


def normalize_chunk_text(text: str) -> str:
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip leading/trailing whitespace from the whole chunk
    text = text.strip()

    # Remove trailing spaces from each line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Collapse excessive blank lines, but preserve paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def get_token_count(text: str) -> int:
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    return len(encoding.encode(text))


def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_markdown(markdown_text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=ENCODING_NAME,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n## ",
            "\n### ",
            "\n#### ",
            "\n\n",
            "\n",
            " ",
            "",
        ],
    )

    return splitter.split_text(markdown_text)


def parse_file(
    bucket_name: str,
    storage_key: str,
) -> dict[str, Any]:
    job_file = get_file_from_minio(
        bucket_name=bucket_name,
        file_path=storage_key,
    )

    if not job_file.get("ok"):
        logger.error(f"Failed to retrieve file from MinIO: {job_file.get('error')}")
        raise Exception(f"Failed to retrieve file from MinIO: {job_file.get('error')}")

    logger.info(f"Parsing file from bucket '{bucket_name}' with storage key '{storage_key}'")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
        file_data = job_file.get("file_data")
        if not isinstance(file_data, bytes):
            raise ValueError("Expected 'file_data' to be of type 'bytes'")
        tmp_file.write(file_data)
        tmp_file.flush()

        markdown_text = extract_pdf_to_markdown(tmp_file.name)

    raw_chunks: list[str] = split_markdown(markdown_text)

    clean_chunks: list[str] = []

    for chunk in raw_chunks:
        clean_chunk = normalize_chunk_text(chunk)

        if clean_chunk:
            clean_chunks.append(clean_chunk)

    parsed_chunks: list[dict[str, Any]] = [
        {
            "chunk_index": index,
            "content": chunk,
            "content_hash": get_content_hash(chunk),
            "token_count": get_token_count(chunk),
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "encoding_name": ENCODING_NAME,
        }
        for index, chunk in enumerate(clean_chunks)
    ]

    return {
        "bucket_name": bucket_name,
        "storage_key": storage_key,
        "extractor_name": "pymupdf4llm",
        "extraction_format": "markdown",
        "extraction_text": markdown_text,
        "extraction_hash": get_content_hash(markdown_text),
        "token_count": get_token_count(markdown_text),
        "chunk_count": len(parsed_chunks),
        "chunks": parsed_chunks,
    }


def build_file_chunks(
    file_id: str,
    file_chunk_data: dict[str, Any],
) -> list[FileChunkCreate]:

    raw_chunks = file_chunk_data.get("chunks")
    if not isinstance(raw_chunks, list):
        raise ValueError("Parsed file data is missing a valid 'chunks' list")

    valid_chunks: list[dict[str, Any]] = []
    for chunk in raw_chunks:
        if not isinstance(chunk, dict):
            raise ValueError(f"Expected parsed chunk to be a dict, got {type(chunk)}")
        if str(chunk.get("content", "")).strip():
            valid_chunks.append(chunk)

    texts: list[str] = []
    for chunk in valid_chunks:
        content = chunk.get("content")
        if not isinstance(content, str):
            raise ValueError(f"Expected chunk content to be of type 'str', got {type(content)}")
        texts.append(content)

    embeddings = create_embeddings(texts)
    if len(embeddings) != len(valid_chunks):
        raise RuntimeError("Embedding count did not match chunk count")

    file_chunks: list[FileChunkCreate] = []
    for chunk, embedding in zip(valid_chunks, embeddings):
        file_chunks.append(
            FileChunkCreate(
                file_id=str(file_id),
                chunk_index=chunk.get("chunk_index", 0),
                chunk_text=chunk["content"],
                embedding=embedding,
                token_count=chunk.get("token_count", 0),
            )
        )

    return file_chunks


def push_chunks(new_chunks: list[FileChunkCreate], auth_token: str) -> dict[str, Any]:
    scrappyard_url, _ = require_scrappyard_config()
    skipped_conflicts = 0

    for chunk in new_chunks:
        try:
            request_json(
                method="POST",
                url=join_url(scrappyard_url, "/api/v1/file-chunks"),
                headers={"Cookie": f"access_token={auth_token}"},
                body=chunk.model_dump(),
            )
        except ApiRequestError as exc:
            if exc.status_code != 409:
                raise
            skipped_conflicts += 1
            logger.info(
                "File chunk already exists; skipping duplicate create",
                extra={
                    "file_id": chunk.file_id,
                    "chunk_index": chunk.chunk_index,
                },
            )

    created_count = len(new_chunks) - skipped_conflicts
    return {
        "ok": True,
        "message": f"Pushed {created_count} chunks to the API; skipped {skipped_conflicts} existing chunks",
        "created_count": created_count,
        "skipped_conflicts": skipped_conflicts,
    }


def process_file_job(
    *,
    file_id: str,
    file_job_id: str,
    bucket_name: str,
    storage_key: str,
    user_file_id: str,
) -> dict[str, Any]:
    assert bucket_name, "bucket_name must be provided"
    assert storage_key, "storage_key must be provided"

    # set_job_status(job_id=file_job_id, status="processing", required=False)

    # parsed_file = parse_file(bucket_name=bucket_name, storage_key=storage_key)

    # set_job_status(job_id=file_job_id, status="chunking", required=False)
    # set_job_status(job_id=file_job_id, status="embedding", required=False)

    # new_chunks = build_file_chunks(file_id=file_id, file_chunk_data=parsed_file)
    # create_status = push_chunks(new_chunks=new_chunks)
    # if not create_status.get("ok"):
    #     raise RuntimeError(
    #         f"Failed to push chunks for job {file_job_id}: {create_status.get('error')}"
    #     )

    # file_status_id = user_file_id if user_file_id is not None else file_id
    # set_file_status(user_file_id=file_status_id, status="ready")
    # set_job_status(job_id=file_job_id, status="chunked")

    # return {
    #     "file_id": str(file_id),
    #     "file_job_id": str(file_job_id),
    #     "bucket_name": bucket_name,
    #     "storage_key": storage_key,
    #     "chunk_count": len(new_chunks),
    #     "token_count": parsed_file.get("token_count", 0),
    #     "final_status": "chunked",
    # }
    return {
        "ok": True,
    }
