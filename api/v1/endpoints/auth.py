from fastapi import APIRouter, Response, Cookie

from schemas.user import UserLogin
from repositories.auth import (
    login_user,
)
from schemas.user import AuthorizedUser, UserToken
from repositories.auth import get_user_from_token

router = APIRouter(tags=["auth"])

@router.post("/login")
async def login_route(
    UserLogin: UserLogin,
    response: Response,
) -> dict[str, str]:
    user_token: UserToken | bool = await login_user(
        UserLogin.email,
        UserLogin.password,
    )
    if type(user_token) is bool:
        if user_token is False:
            return {"message": "Invalid email or password"}
        elif user_token is True:
            return {"message": "There was an error logging in"}

    response.set_cookie(
        key="access_token",
        value=user_token.token,
        httponly=True,
        secure=True,      # True in production over HTTPS
        samesite="lax",    # often fine for same-site frontend/backend
        max_age=60 * 60 * 24,  # 1 day, adjust as needed
        expires=60 * 60 * 24,  # 1 day, adjust as needed
        path="/",
    )

    return {"message": "Successfully logged in"}


@router.get("/me")
async def get_current_user_route(
    access_token: str | None = Cookie(default=None)
) -> dict[str, AuthorizedUser | str]:
    if not access_token:
        return {"message": "Needs to login first"}

    authorized_user = await get_user_from_token(token=access_token)

    if not authorized_user:
        return {"message": "Invalid or expired token"}

    return {
        "user": authorized_user,
    }
