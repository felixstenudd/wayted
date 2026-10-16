"""
HTTP endpoints for handling user accounts
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.auth import service
from app.auth.dependencies import UserId
from app.auth.schemas import AccessTokenOut, ChangePasswordIn, LoginIn, RegisterIn, UserOut
from app.config import COOKIE_SECURE, REFRESH_TOKEN_TTL_DAYS
from app.dependencies import Conn

router = APIRouter(prefix="/auth", tags=["auth"])

_STATUS_CODES: dict[type[service.AuthError], int] = {
    service.InvalidInput: status.HTTP_400_BAD_REQUEST,
    service.EmailTaken: status.HTTP_409_CONFLICT,
    service.InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
}

_REFRESH_COOKIE = "refresh_token"
# httponly: page scripts cannot read it, so an XSS bug cannot steal it.
# samesite=strict: the browser only sends it on requests from this site, which blocks CSRF.
# secure: only sent over https.
_COOKIE_OPTIONS: dict[str, Any] = {
    "httponly": True,
    "samesite": "strict",
    "secure": COOKIE_SECURE,
}

RefreshCookie = Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)]


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate service errors into HTTP responses."""
    try:
        yield
    except service.AuthError as e:
        raise HTTPException(_STATUS_CODES[type(e)], str(e)) from None


def _tokens(pair: tuple[str, str], response: Response) -> AccessTokenOut:
    """Set the refresh token as an httpOnly cookie and return the access token."""
    access_token, refresh_token = pair
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        max_age=int(timedelta(days=REFRESH_TOKEN_TTL_DAYS).total_seconds()),
        **_COOKIE_OPTIONS,
    )
    return AccessTokenOut(access_token=access_token)


@router.post("/register")
async def register(body: RegisterIn, response: Response, db_conn: Conn) -> AccessTokenOut:
    """Create an user account."""
    with _http_errors():
        res = await service.create_account(body.email, body.name, body.password, db_conn)
    return _tokens(res, response)


@router.post("/login")
async def login(body: LoginIn, response: Response, db_conn: Conn) -> AccessTokenOut:
    """Login as an existing user."""
    with _http_errors():
        res = await service.login(body.email, body.password, db_conn)
    return _tokens(res, response)


@router.post("/refresh")
async def refresh(
    response: Response, db_conn: Conn, refresh_token: RefreshCookie = None
) -> AccessTokenOut:
    """Exchange the refresh token cookie for a new access token. Rotates the cookie."""
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    with _http_errors():
        res = await service.refresh(refresh_token, db_conn)
    return _tokens(res, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, db_conn: Conn, refresh_token: RefreshCookie = None) -> None:
    """Revoke the refresh token and clear its cookie."""
    if refresh_token is not None:
        await service.logout(refresh_token, db_conn)
    response.delete_cookie(_REFRESH_COOKIE, **_COOKIE_OPTIONS)


@router.get("/me")
async def me(user_id: UserId, db_conn: Conn) -> UserOut:
    """Return the logged-in user."""
    with _http_errors():
        email, name = await service.get_user(user_id, db_conn)
    return UserOut(email=email, name=name)


@router.post("/me/password")
async def change_password(
    user_id: UserId, body: ChangePasswordIn, response: Response, db_conn: Conn
) -> AccessTokenOut:
    """Change password. Requires the current password."""
    with _http_errors():
        res = await service.change_password(
            user_id, body.current_password, body.new_password, db_conn
        )
    return _tokens(res, response)
