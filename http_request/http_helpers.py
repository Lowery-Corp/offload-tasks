import os
import json
from typing import Any
from schemas.api_request_errors import ApiRequestError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "10"))


def request_json(
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
        raise ApiRequestError(
            f"{method} {url} failed with {exc.code}: {error_body}",
            status_code=exc.code,
        ) from exc
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

