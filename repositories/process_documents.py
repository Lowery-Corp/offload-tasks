import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Any

from http_request.http_helpers import request_json
from helpers.dependencies import join_url
from schemas.file_job import FileJob


JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
CLAIMABLE_STATUSES = ("pending")
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", None)
FILE_JOBS_PATH = os.getenv("FILE_JOBS_PATH", "/api/v1/file-jobs")


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
