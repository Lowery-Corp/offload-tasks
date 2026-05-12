import os
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

# file parsing and chunking settings
ENCODING_NAME = "cl100k_base"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120


def retrieve_jobs(auth_token: str) -> list[FileJob]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    assert FILE_JOBS_PATH is not None, "FILE_JOBS_PATH must be configured"
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
    url = f"{join_url(SCRAPPYS_SCRAPYARD_URL, FILE_JOBS_PATH)}?{query}"
    headers = {"Cookie": f"access_token={auth_token}"}
    payload: list[dict[str, Any]] = request_json(method="GET", url=url, headers=headers)[0]

    jobs = [FileJob(**job) for job in payload]
    remaining = JOB_BATCH_SIZE - len(jobs)

    return jobs


def update_job_status(job_id: str, new_status: str, auth_token: str) -> FileJob:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    assert FILE_JOBS_PATH is not None, "FILE_JOBS_PATH must be configured"

    url_path = f"{FILE_JOBS_PATH}/{job_id}"
    url = join_url(SCRAPPYS_SCRAPYARD_URL, url_path)

    headers = {"Cookie": f"access_token={auth_token}"}
    payload = {"status": new_status}
    response = request_json(method="PATCH", url=url, headers=headers, body=payload)
    return FileJob(**response[0])


def extract_pdf_to_markdown(file_path: str) -> str:
    return pymupdf4llm.to_markdown(file_path)


def get_token_count(text: str) -> int:
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    return len(encoding.encode(text))


def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_markdown(markdown_text: str) -> list[dict[str, Any]]:
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
) -> list[dict[str, Any]]:
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

    raw_chunks: list[dict[str, Any]] = split_markdown(markdown_text)
    logger.info(raw_chunks)


    return raw_chunks


def build_file_chunks(
    file_id: uuid.UUID,
    raw_chunks: list[dict[str, Any]],
) -> list[FileChunkCreate]:
    logger.info(raw_chunks)
    valid_chunks = [
        chunk
        for chunk in raw_chunks
        if str(chunk.get("content", "")).strip()
    ]

    texts = [chunk["content"] for chunk in valid_chunks]
    embeddings = create_embeddings(texts)

    file_chunks: list[FileChunkCreate] = []

    for chunk, embedding in zip(valid_chunks, embeddings):
        file_chunks.append(
            FileChunkCreate(
                file_id=file_id,
                chunk_index=chunk.get("chunk_index", 0),
                chunk_text=chunk["content"],
                embedding=embedding,
                token_count=chunk.get("token_count", 0),
            )
        )

    return file_chunks
