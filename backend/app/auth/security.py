"""Password hashing and JWT creation and verification."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from ..config import ACCESS_TOKEN_MINUTES, JWT_SECRET

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def create_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


def user_id_from_token(token: str) -> UUID | None:
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
