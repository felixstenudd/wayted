"""
HTTP endpoints for handling user accounts
"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, status

from app.auth import service
from app.auth.dependencies import UserId
from app.auth.schemas import ChangePasswordIn, LoginIn, RefreshIn, RegisterIn, TokensOut, UserOut
from app.dependencies import Conn

router = APIRouter(prefix="/auth", tags=["auth"])

_STATUS_CODES: dict[type[service.AuthError], int] = {
    service.InvalidInput: status.HTTP_400_BAD_REQUEST,
    service.EmailTaken: status.HTTP_409_CONFLICT,
    service.InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
}


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate service errors into HTTP responses."""
    try:
        yield
    except service.AuthError as e:
        raise HTTPException(_STATUS_CODES[type(e)], str(e)) from None


def _tokens(pair: tuple[str, str]) -> TokensOut:
    access_token, refresh_token = pair
    return TokensOut(access_token=access_token, refresh_token=refresh_token)


@router.post("/register")
async def register(body: RegisterIn, db_conn: Conn) -> TokensOut:
    """Create an user account."""
    with _http_errors():
        res = await service.create_account(body.email, body.name, body.password, db_conn)
    return _tokens(res)


@router.post("/login")
async def login(body: LoginIn, db_conn: Conn) -> TokensOut:
    """Login as an existing user."""
    with _http_errors():
        res = await service.login(body.email, body.password, db_conn)
    return _tokens(res)


@router.post("/refresh")
async def refresh(body: RefreshIn, db_conn: Conn) -> TokensOut:
    """Exchange a valid refresh token for a new access token."""
    with _http_errors():
        res = await service.refresh(body.refresh_token, db_conn)
    return _tokens(res)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshIn, db_conn: Conn) -> None:
    """Revoke the refresh token."""
    await service.logout(body.refresh_token, db_conn)


@router.get("/me")
async def me(user_id: UserId, db_conn: Conn) -> UserOut:
    """Return the logged-in user."""
    with _http_errors():
        email, name = await service.get_user(user_id, db_conn)
    return UserOut(email=email, name=name)


@router.post("/me/password")
async def change_password(user_id: UserId, body: ChangePasswordIn, db_conn: Conn) -> TokensOut:
    """Change password. Requires the current password."""
    with _http_errors():
        res = await service.change_password(
            user_id, body.current_password, body.new_password, db_conn
        )
    return _tokens(res)
