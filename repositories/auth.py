from httpx import ConnectTimeout, HTTPError

from httpxC.http_client import http_client
from schemas.user import AuthorizedUser
from core.config import settings
from core.retry import build_http_retry


@build_http_retry(attempts=2)
async def get_user_from_token(token: str) -> AuthorizedUser | None:
    auth_endpoint = f"{settings.auth_api_url}/api/v1/auth/me"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = await http_client.get(auth_endpoint, headers=headers)

        if response.status_code == 401:
            return None

        response.raise_for_status()
        data = response.json()

        return AuthorizedUser(
            id=str(data.get("id", "")),
            username=data.get("username", ""),
            email=data.get("email", ""),
            is_admin=False,
        )
    except ConnectTimeout:
        return None
    except HTTPError:
        return None
