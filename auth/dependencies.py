from fastapi import HTTPException, Request, status

from repositories.auth import get_user_from_token
from schemas.user import AuthorizedUser


async def authenticate_request(request: Request) -> AuthorizedUser:
    authorization = request.headers.get("Authorization", "")
    access_token = authorization.replace("Bearer ", "").strip()

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    authorized_user = await get_user_from_token(token=access_token)

    if not authorized_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return authorized_user