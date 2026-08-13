import os
import httpx

API_REQUEST_TIMEOUT = float(os.getenv("API_REQUEST_TIMEOUT", "10"))
SCRAPPYS_API_KEY = os.getenv("SCRAPPYS_API_KEY", "")

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SCRAPPYS_API_KEY,
}

CLIENT = httpx.Client(
    timeout=API_REQUEST_TIMEOUT,
    headers=HEADERS,
)