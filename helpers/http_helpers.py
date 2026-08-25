import os
import httpx

API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "10"))
SCRAPPYS_API_KEY = os.getenv("SCRAPPYS_API_KEY", "")

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SCRAPPYS_API_KEY,
}

_client: httpx.Client | None = None
_client_pid: int | None = None


def get_client() -> httpx.Client:
    global _client, _client_pid

    current_pid = os.getpid()

    # New Celery child process -> create its own connection pool
    if _client is None or _client_pid != current_pid:
        if _client is not None:
            _client.close()

        _client = httpx.Client(
            headers=HEADERS,
            timeout=httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=30.0,
                pool=10.0,
            ),
        )

        _client_pid = current_pid

    return _client