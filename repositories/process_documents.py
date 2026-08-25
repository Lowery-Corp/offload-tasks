import os
import re
import tempfile
import hashlib
from typing import Any
from httpx import Client
import pymupdf4llm
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from helpers.dependencies import join_url, logger
from schemas.file_job import FileJob
from schemas.file_chunk import FileChunkCreate
from repositories.minio import get_file_from_minio
from repositories.openapi import create_embeddings

JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", None)
FILE_JOBS_PATH = os.getenv("FILE_JOBS_PATH", "/api/v1/data/jobs")
FILES_PATH = os.getenv("FILES_PATH", "/api/v1/data/file")
FILE_CHUNK_PATH = os.getenv("FILE_CHUNK_PATH", "/api/v1/data/file-chunks")

# file parsing and chunking settings
ENCODING_NAME = "cl100k_base"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# ################################# Object status updates ############################################################
def update_job_status(job_id: str, new_status: str, client: Client) -> FileJob:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/{job_id}")
    print("Updating job status:", url, new_status, flush=True)

    payload = {"status": new_status}
    response = client.patch(url, json=payload)
    updated_job = FileJob(**response.json())

    if updated_job.status != new_status:
        raise RuntimeError(
            f"Expected job {job_id} to be {new_status}, got {updated_job.status}"
        )

    return updated_job


def update_file_status(file_id: str, new_status: str, client: Client) -> dict[str, Any]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILES_PATH}/{file_id}")

    payload = {"status": new_status}
    response = client.patch(url, json=payload)
    response.raise_for_status()
    updated_file = response.json()

    return updated_file


def update_file_and_job_status(
    file_id: str,
    job_id: str,
    client: Client,
    new_job_status: str | None = None,
    new_file_status: str | None = None,
) -> bool:
    updated_file = None
    updated_job = None
    if new_file_status:
        updated_file = update_file_status(file_id=file_id, new_status=new_file_status, client=client)
    if new_job_status:
        updated_job = update_job_status(job_id=job_id, new_status=new_job_status, client=client)

    logger.info(f"Updated file and job status for job {job_id}: file_status={updated_file.get('status') if updated_file else 'N/A'}, job_status={updated_job.status if updated_job else 'N/A'}")
    return True


def update_attempt_count(job_id: str, client: Client) -> FileJob:
    logger.info(f"Incrementing attempt count for job {job_id}")
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/{job_id}/increment_attempts")
    logger.info(f"Sending POST request to {url}")
    response = client.patch(url)
    response.raise_for_status()
    updated_job = FileJob(**response.json())
    return updated_job
# #############################################################################################
# ################################# retrieve objects ############################################################

def retrieve_job(job_id: str, client: Client) -> FileJob:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/{job_id}")
    response = client.get(url)
    response.raise_for_status()
    file_job = FileJob(**response.json())
    return file_job


def retrieve_old_jobs( status: list[str], client: Client, limit: int = 10) -> list[str]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    params: dict[str, Any] = {"status": status, "limit": limit}
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_JOBS_PATH}/list")
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def retrieve_file(file_id: str, client: Client) -> dict[str, Any]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILES_PATH}/{file_id}")
    response = client.get(url)
    response.raise_for_status()
    response_data = dict(response.json())
    if not isinstance(response_data.get("files"), list) or not response_data.get("files"):
        raise ValueError(f"Expected 'files' to be a non-empty list in the response for file_id {file_id}")
    file_data = response_data.get("files", [])[0]
    return file_data
# #############################################################################################
# ################################# File processing ############################################################

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
        chunk_size=200,
        chunk_overlap=40,
        separators=[
            "\n## ",
            "\n### ",
            "\n#### ",
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
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

# #############################################################################################
# ############################### Data Updates ##############################################################

def push_chunks(new_chunks: list[FileChunkCreate], client: Client) -> dict[str, Any]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    skipped_conflicts = 0

    for chunk in new_chunks:
        response = client.post(
            join_url(SCRAPPYS_SCRAPYARD_URL, FILE_CHUNK_PATH),
            json=chunk.model_dump(),
        )
        response.raise_for_status()


    created_count = len(new_chunks) - skipped_conflicts
    return {
        "ok": True,
        "message": f"Pushed {created_count} chunks to the API; skipped {skipped_conflicts} existing chunks",
        "created_count": created_count,
        "skipped_conflicts": skipped_conflicts,
    }


def delete_file_chunks(file_id: str, client: Client) -> dict[str, Any]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, f"{FILE_CHUNK_PATH}/{file_id}")
    response = client.delete(url)
    response.raise_for_status()
    return response.json()

# #############################################################################################
# ############################### Main ##############################################################

def run_jobs(
    file_job_ids: list[str],
    http_client: Client
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for file_job_id in file_job_ids:
        updating_attempts = update_attempt_count(job_id=file_job_id, client=http_client)
        assert updating_attempts is not None, f"Failed to update attempt count for job {file_job_id}"

        current_job = retrieve_job(job_id=file_job_id, client=http_client)
        file_id = str(current_job.file_id)

        try:
            deleted_status = delete_file_chunks(file_id=file_id, client=http_client)
            logger.info(f"Deleted existing chunks for file {file_id}: {deleted_status.get('message')}")
        except Exception as e:
            update_file_and_job_status(
                file_id=file_id,
                job_id=file_job_id,
                new_file_status="error",
                new_job_status="error",
                client=http_client
            )
            logger.info(f"Failed to delete existing chunks for file {file_id}: {e}")
            raise RuntimeError(f"Failed to delete existing chunks for file {file_id}: {e}")

        file = retrieve_file(file_id=file_id, client=http_client)
        storage_key = file.get("storage_key", None)
        user_id = file.get("user_id", None)

        if not storage_key:
            logger.error(f"File {file_id} does not have a valid storage_key")
            raise ValueError(f"File {file_id} does not have a valid storage_key")
        if not user_id:
            logger.error(f"File {file_id} does not have a valid user_id")
            raise ValueError(f"File {file_id} does not have a valid user_id")

        result = process_file_job(
            file_id=file_id,
            file_job_id=file_job_id,
            bucket_name=f"user-{user_id}-bucket",
            storage_key=storage_key,
            http_client=http_client
        )
        results.append(result)
    return results


def process_file_job(
    *,
    file_id: str,
    file_job_id: str,
    bucket_name: str,
    storage_key: str,
    http_client: Client,
) -> dict[str, Any]:
    assert bucket_name, "bucket_name must be provided"
    assert storage_key, "storage_key must be provided"

    update_file_and_job_status(
        file_id=file_id,
        job_id=file_job_id,
        new_file_status="processing",
        new_job_status="processing",
        client=http_client
    )

    try:
        parsed_file = parse_file(bucket_name=bucket_name, storage_key=storage_key)
        logger.info(f"Parsed file job {file_job_id}: {parsed_file.get('chunk_count', 0)} chunks, {parsed_file.get('token_count', 0)} tokens")
    except Exception as e:
        logger.error(f"Error parsing file for job {file_job_id}: {e}")
        update_file_and_job_status(
            file_id=file_id,
            job_id=file_job_id,
            new_file_status="error",
            new_job_status="error",
            client=http_client,
        )
        raise ValueError(f"Error parsing file for job {file_job_id}: {e}")

    update_file_and_job_status(
        file_id=file_id,
        job_id=file_job_id,
        new_file_status="parsed",
        client=http_client,
    )

    try:
        new_chunks = build_file_chunks(file_id=file_id, file_chunk_data=parsed_file)
        logger.info(f"Built {len(new_chunks)} new chunks for job {file_job_id}")
    except Exception as e:
        logger.error(f"Error building file chunks for job {file_job_id}: {e}")
        update_file_and_job_status(
            file_id=file_id,
            job_id=file_job_id,
            new_file_status="error",
            new_job_status="error",
            client=http_client,
        )
        raise ValueError(f"Error building file chunks for job {file_job_id}: {e}")

    update_file_and_job_status(
        file_id=file_id,
        job_id=file_job_id,
        new_job_status="chunking",
        client=http_client,
    )

    try:
        create_status = push_chunks(new_chunks=new_chunks, client=http_client)
        logger.info(f"Pushed chunks for job {file_job_id}: {create_status.get('message')}")
    except Exception as e:
        logger.error(f"Error pushing chunks for job {file_job_id}: {e}")
        update_file_and_job_status(
            file_id=file_id,
            job_id=file_job_id,
            new_file_status="error",
            new_job_status="error",
            client=http_client,
        )
        raise RuntimeError(f"Error pushing chunks for job {file_job_id}: {e}")

    update_file_and_job_status(
        file_id=file_id,
        job_id=file_job_id,
        new_file_status="ready",
        new_job_status="finished",
        client=http_client
    )

    return {
        "ok": True,
        "message": f"Processed file job {file_job_id} successfully",
        "file_id": str(file_id),
        "file_job_id": str(file_job_id),
        "bucket_name": bucket_name,
        "storage_key": storage_key,
        "chunk_count": len(new_chunks),
        "token_count": parsed_file.get("token_count", 0),
    }

# #############################################################################################