import os
from typing import Any
from http.cookies import SimpleCookie

from schemas.api_request_errors import ApiRequestError
from http_request.http_helpers import request_json
from helpers.dependencies import join_url

AUTH_API_URL = os.getenv("AUTH_API_URL", None)
AUTH_LOGIN_PATH = os.getenv("AUTH_LOGIN_PATH", None)
SCRAPPYS_SCRAPYARD_URL = os.getenv("SCRAPPYS_SCRAPYARD_URL", None)


def extract_auth_token(payload: dict[str, Any], response_headers: dict[str, str]) -> str:
    cookie = SimpleCookie()
    set_cookie_header = response_headers.get("Set-Cookie")
    if set_cookie_header:
        cookie.load(set_cookie_header)
        for cookie_name in ("access_token", "auth_token", "authtoken", "token"):
            if cookie_name in cookie:
                return cookie[cookie_name].value

    for key in ("access_token", "auth_token", "authtoken", "token"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    raise ApiRequestError("Auth endpoint did not return an auth token")


def get_auth_token() -> str:
    username = os.getenv("INTERNAL_API_USERNAME")
    password = os.getenv("INTERNAL_API_PASSWORD")

    assert AUTH_API_URL is not None, "AUTH_API_URL must be configured"
    assert AUTH_LOGIN_PATH is not None, "AUTH_LOGIN_PATH must be configured"

    if not username or not password:
        raise ApiRequestError(
            "INTERNAL_API_USERNAME and INTERNAL_API_PASSWORD must be configured"
        )

    login_body = {
        "email": username,
        "password": password,
    }

    errors: list[str] = []
    try:
        payload, headers = request_json(
            "POST",
            join_url(AUTH_API_URL, AUTH_LOGIN_PATH),
            body=login_body,
        )
        return extract_auth_token(payload, headers)
    except ApiRequestError as exc:
        errors.append(str(exc))

    raise ApiRequestError("Could not authenticate: " + " | ".join(errors))

