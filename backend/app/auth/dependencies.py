"""FastAPI dependencies that authenticate the current user from a bearer token."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .security import decode_token

_bearer = HTTPBearer(auto_error=False)
AuthCreds = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )


def current_user(creds: AuthCreds) -> UUID | None:
    """Return the authenticated user's id, or respond 401."""
    if creds is None:
        raise _unauthorized()
    claims = decode_token(creds.credentials)
    if claims is None:
        raise _unauthorized()
    try:
        return UUID(claims["sub"])
    except ValueError:
        raise _unauthorized() from None


def current_user_optional(creds: AuthCreds) -> UUID:
    """
    Return the authenticated user's id, None if no token was sent,
    or respond 401 if the token is invalid.
    """
    if creds is None:
        return None
    return current_user(creds)


UserId = Annotated[UUID, Depends(current_user)]
