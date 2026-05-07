import os
import json
import socket
from http.cookies import SimpleCookie
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from typing import Any

from worker.celery_app import celery_app
from repositories.minio import get_file_from_minio  # noqa: F401

JOB_BATCH_SIZE = int(os.getenv("FILE_JOB_BATCH_SIZE", "10"))
CLAIMABLE_STATUSES = ("pending", "queued")
AUTH_API_URL = os.getenv("AUTH_API_URL", None)
AUTH_LOGIN_PATH = os.getenv("AUTH_LOGIN_PATH", "/api/v1/auth/login")
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", "https://dscrapyard.johnmgrubbs.io")
FILE_JOBS_PATH = os.getenv("FILE_JOBS_PATH", "/api/v1/file-jobs")
API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "10"))


class ApiRequestError(RuntimeError):
    pass


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _request_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[Any, dict[str, str]]:
    request_headers = {
        "Accept": "application/json",
        **(headers or {}),
    }
    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=request_headers, method=method)

    try:
        with urlopen(request, timeout=API_REQUEST_TIMEOUT) as response:
            response_body = response.read()
            response_headers = dict(response.headers.items())
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ApiRequestError(f"{method} {url} failed with {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise ApiRequestError(f"{method} {url} failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ApiRequestError(f"{method} {url} timed out") from exc

    if not response_body:
        return None, response_headers

    try:
        return json.loads(response_body), response_headers
    except json.JSONDecodeError as exc:
        raise ApiRequestError(f"{method} {url} returned invalid JSON") from exc


def _extract_auth_token(payload: Any, response_headers: dict[str, str]) -> str:
    cookie = SimpleCookie()
    set_cookie_header = response_headers.get("Set-Cookie")
    if set_cookie_header:
        cookie.load(set_cookie_header)
        for cookie_name in ("access_token", "auth_token", "authtoken", "token"):
            if cookie_name in cookie:
                return cookie[cookie_name].value

    if isinstance(payload, dict):
        for key in ("access_token", "auth_token", "authtoken", "token"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value

    raise ApiRequestError("Auth endpoint did not return an auth token")


def get_auth_token() -> str:
    username = os.getenv("INTERNAL_API_USERNAME")
    password = os.getenv("INTERNAL_API_PASSWORD")

    if not username or not password:
        raise ApiRequestError(
            "INTERNAL_API_USERNAME and INTERNAL_API_PASSWORD must be configured"
        )

    login_body = {
        "email": username,
        "password": password,
    }
    auth_base_urls = [AUTH_API_URL]
    if SCRAPPYS_SCRAPYARD_URL not in auth_base_urls:
        auth_base_urls.append(SCRAPPYS_SCRAPYARD_URL)

    errors: list[str] = []
    for base_url in auth_base_urls:
        try:
            payload, headers = _request_json(
                "POST",
                _join_url(base_url, AUTH_LOGIN_PATH),
                body=login_body,
            )
            return _extract_auth_token(payload, headers)
        except ApiRequestError as exc:
            errors.append(str(exc))

    raise ApiRequestError("Could not authenticate: " + " | ".join(errors))


def retrieve_jobs(auth_token: str) -> list[dict[str, Any]]:
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
        payload, _headers = _request_json(
            "GET",
            f"{_join_url(SCRAPPYS_SCRAPYARD_URL, FILE_JOBS_PATH)}?{query}",
            headers={
                "Cookie": f"access_token={auth_token}",
            },
        )

        if not isinstance(payload, list):
            raise ApiRequestError("CRUD endpoint did not return a list of file jobs")

        jobs.extend(payload)
        remaining = JOB_BATCH_SIZE - len(jobs)

    return jobs


@celery_app.task(name="tasks.file_tasks.process_document") # type: ignore
def process_document() -> dict[str, Any]:
    auth_token = get_auth_token()
    jobs = retrieve_jobs(auth_token)
    # for job in jobs:
        # bucket_name
    print(f"Retrieved {len(jobs)} file jobs from CRUD endpoint", flush=True)

    return {
        "ok": True,
        "message": "Retrieved file jobs from crud endpoint",
        "worker_id": socket.gethostname(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "jobs": jobs,
    }


@celery_app.task(name="tasks.file_tasks.cleanup_old_results") # type: ignore
def cleanup_old_results() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Cleanup task ran",
    }
