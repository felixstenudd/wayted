import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from psycopg import AsyncConnection

from app.auth.security import create_token, hash_password, verify_password
from app.config import REFRESH_TOKEN_TTL_DAYS

_DUMMY_HASH = hash_password("dummy-password-for-timing")


class AuthError(Exception):
    """Base for errors the router turns into HTTP responses."""


class InvalidInput(AuthError):
    pass


class EmailTaken(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


async def create_account(
    email: str, name: str, password: str, db_conn: AsyncConnection
) -> tuple[str, str]:
    """
    Creates account from specified credentials and returns JWT and refresh token.
    Throws error on already used email.
    """
    email = email.strip().lower()
    name = name.strip()
    _valid_email(email)
    _valid_name(name)
    _valid_password(password)

    user_id = await _insert_account(email, name, hash_password(password), db_conn)
    tokens = await _issue_tokens(user_id, db_conn)

    return tokens


async def login(email: str, password: str, db_conn: AsyncConnection) -> tuple[str, str]:
    """
    Logs in on an existing user.
    Throws error on email not in use or incorrect password.
    """
    email = email.strip().lower()
    cur = await db_conn.execute(
        """
        SELECT id, password_hash FROM app.users WHERE email = %s
        """,
        (email,),
    )
    row = await cur.fetchone()

    if row is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials("Invalid email or password")

    user_id, password_hash = row
    if not verify_password(password, password_hash):
        raise InvalidCredentials("Invalid email or password")

    return await _issue_tokens(user_id, db_conn)


async def get_user(user_id: UUID, db_conn: AsyncConnection) -> tuple[str, str]:
    cur = await db_conn.execute(
        """
        SELECT email, name FROM app.users WHERE id = %s
        """,
        (user_id,),
    )
    user = await cur.fetchone()
    if user is None:
        raise InvalidCredentials("User no longer exists.")
    email, name = user
    return email, name


async def logout(refresh_token: str, db_conn: AsyncConnection) -> None:
    await db_conn.execute(
        """
        UPDATE app.refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = %s AND revoked_at IS NULL
        """,
        (_hash_refresh_token(refresh_token),),
    )


async def refresh(refresh_token: str, db_conn: AsyncConnection) -> tuple[str, str]:
    token_hash = _hash_refresh_token(refresh_token)
    cur = await db_conn.execute(
        """
        UPDATE app.refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > now()
        RETURNING user_id
        """,
        (token_hash,),
    )
    row = await cur.fetchone()
    if row is not None:
        return await _issue_tokens(row[0], db_conn)

    await _revoke_all_if_used(token_hash, db_conn)
    raise InvalidCredentials("Invalid refresh token")


async def change_password(
    user_id: UUID, current_password: str, new_password: str, db_conn: AsyncConnection
) -> tuple[str, str]:
    cur = await db_conn.execute(
        """
        SELECT password_hash FROM app.users WHERE id = %s
        """,
        (user_id,),
    )
    row = await cur.fetchone()
    if row is None or not verify_password(current_password, row[0]):
        raise InvalidCredentials("Current password is incorrect")
    _valid_password(new_password)

    await db_conn.execute(
        "UPDATE app.users SET password_hash = %s WHERE id = %s",
        (hash_password(new_password), user_id),
    )

    await db_conn.execute(
        """
        UPDATE app.refresh_tokens
        SET revoked_at = now()
        WHERE user_id = %s AND revoked_at IS NULL
        """,
        (user_id,),
    )
    return await _issue_tokens(user_id, db_conn)


def _valid_email(email: str) -> None:
    local, sep, domain = email.partition("@")
    if (
        not sep
        or not local
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or " " in email
        or len(email) > 254
    ):
        raise InvalidInput("Invalid email.")


def _valid_name(name: str) -> None:
    if not name:
        raise InvalidInput("Name must not be empty.")


def _valid_password(password: str) -> None:
    if len(password) < 8:
        raise InvalidInput("Password must be at least 8 characters.")


def _create_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _insert_account(
    email: str, name: str, password_hash: str, db_conn: AsyncConnection
) -> UUID:
    """
    Insert account in database. Returns user id.
    Raises EmailTaken if email already exists in database.
    """
    cur = await db_conn.execute(
        """
        INSERT INTO app.users (email, name, password_hash)
        VALUES (%s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        (email, name, password_hash),
    )
    row = await cur.fetchone()
    if row is None:
        raise EmailTaken("Email already registered")
    user_id: UUID = row[0]
    return user_id


async def _insert_refresh_token(
    user_id: UUID,
    token_hash: str,
    issued_at: datetime,
    expires_at: datetime,
    db_conn: AsyncConnection,
) -> None:
    """
    Insert refresh token in database.
    Assumes refresh token is created directly before insert.
    """
    await db_conn.execute(
        """
        INSERT INTO app.refresh_tokens (user_id, token_hash, issued_at, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (user_id, token_hash, issued_at, expires_at),
    )
    return


async def _issue_tokens(user_id: UUID, db_conn: AsyncConnection) -> tuple[str, str]:
    """Create access token and refresh token for user id"""
    access_token = create_token(user_id)
    refresh_token = _create_refresh_token()
    refresh_token_hash = _hash_refresh_token(refresh_token)
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

    await _insert_refresh_token(user_id, refresh_token_hash, now, expires_at, db_conn)

    return (access_token, refresh_token)


async def _revoke_all_if_used(token_hash: str, db_conn: AsyncConnection) -> None:
    await db_conn.execute(
        """
        UPDATE app.refresh_tokens
        SET revoked_at = now()
        WHERE revoked_at IS NULL
          AND user_id = (
              SELECT user_id FROM app.refresh_tokens
              WHERE token_hash = %s AND revoked_at IS NOT NULL
          )
        """,
        (token_hash,),
    )
    await db_conn.commit()
