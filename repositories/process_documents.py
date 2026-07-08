import os
import re
import uuid
import tempfile
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Any

import pymupdf4llm
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from helpers.dependencies import logger
from http_request.http_helpers import request_json
from helpers.dependencies import join_url
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


def require_scrappyard_config() -> tuple[str, str]:
    if SCRAPPYS_SCRAPYARD_URL is None:
        raise RuntimeError("SCRAPPYS_SCRAPYARD_URL must be configured")
    if FILE_JOBS_PATH is None:
        raise RuntimeError("FILE_JOBS_PATH must be configured")
    return SCRAPPYS_SCRAPYARD_URL, FILE_JOBS_PATH


def retrieve_jobs(auth_token: str) -> list[FileJob]:
    scrappyard_url, file_jobs_path = require_scrappyard_config()
    jobs: list[FileJob] = []
    remaining = JOB_BATCH_SIZE

    queued_at = datetime.now() - timedelta(minutes=10)

    query = urlencode(
        {
            "status": CLAIMABLE_STATUSES,
            "limit": remaining,
            "offset": 0,
            "queued_before": queued_at,
            "add_file_data": True,
        }
    )
    url = f"{join_url(scrappyard_url, file_jobs_path)}?{query}"
    headers = {"Cookie": f"access_token={auth_token}"}
    payload: list[dict[str, Any]] = request_json(method="GET", url=url, headers=headers)[0]

    jobs = [FileJob(**job) for job in payload]
    remaining = JOB_BATCH_SIZE - len(jobs)

    return jobs


def retrieve_job(job_id: str, auth_token: str) -> FileJob:
    scrappyard_url, file_jobs_path = require_scrappyard_config()
    url = join_url(scrappyard_url, f"{file_jobs_path}/{job_id}")
    headers = {"Cookie": f"access_token={auth_token}"}
    response = request_json(method="GET", url=url, headers=headers)
    return FileJob(**response[0])


def update_job_status(job_id: str, new_status: str, auth_token: str) -> FileJob:
    scrappyard_url, file_jobs_path = require_scrappyard_config()
    url = join_url(scrappyard_url, f"{file_jobs_path}/{job_id}")

    headers = {"Cookie": f"access_token={auth_token}"}
    payload = {"status": new_status}
    response = request_json(method="PATCH", url=url, headers=headers, body=payload)
    updated_job = FileJob(**response[0])

    if updated_job.status != new_status:
        raise RuntimeError(
            f"Expected job {job_id} to be {new_status}, got {updated_job.status}"
        )

    return updated_job


def update_file_status(user_file_id: str, new_status: str, auth_token: str) -> dict[str, Any]:
    scrappyard_url, _ = require_scrappyard_config()
    url = join_url(scrappyard_url, f"{FILES_PATH}/{user_file_id}")

    headers = {"Cookie": f"access_token={auth_token}"}
    payload = {"status": new_status}
    response = request_json(method="PATCH", url=url, headers=headers, body=payload)
    updated_file = response[0]

    if (
        isinstance(updated_file, dict)
        and "status" in updated_file
        and updated_file["status"] != new_status
    ):
        raise RuntimeError(
            f"Expected file {user_file_id} to be {new_status}, got {updated_file['status']}"
        )

    return updated_file if isinstance(updated_file, dict) else {}


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
    file_id: uuid.UUID,
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

    for chunk in new_chunks:
        request_json(
            method="POST",
            url=join_url(scrappyard_url, "/api/v1/file-chunks"),
            headers={"Cookie": f"access_token={auth_token}"},
            body=chunk.model_dump(),
        )

    return {"ok": True, "message": f"Pushed {len(new_chunks)} chunks to the API"}
