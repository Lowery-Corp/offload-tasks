import os
from urllib.parse import urlencode
from typing import Any

from http_request.http_helpers import request_json
from helpers.dependencies import join_url


JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
CLAIMABLE_STATUSES = ("pending", "queued")
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", None)
FILE_JOBS_PATH = os.getenv("FILE_JOBS_PATH", "/api/v1/file-jobs")


def retrieve_jobs(auth_token: str) -> list[dict[str, Any]]:
    assert SCRAPPYS_SCRAPYARD_URL is not None, "SCRAPPYS_SCRAPYARD_URL must be configured"
    assert FILE_JOBS_PATH is not None, "FILE_JOBS_PATH must be configured"
    jobs: list[dict[str, Any]] = []
    remaining = JOB_BATCH_SIZE

    for status in CLAIMABLE_STATUSES:
        if remaining <= 0:
            break

        query = urlencode(
            {
                "status": status,
                "limit": remaining,
                "offset": 0,
            }
        )
        url = f"{join_url(SCRAPPYS_SCRAPYARD_URL, FILE_JOBS_PATH)}?{query}"
        headers = {"Cookie": f"access_token={auth_token}"}
        payload: list[dict[str, Any]] = request_json(method="GET", url=url, headers=headers)[0]

        jobs.extend(payload)
        remaining = JOB_BATCH_SIZE - len(jobs)

    return jobs

