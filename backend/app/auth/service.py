from uuid import UUID

from security import create_token, hash_password, user_id_from_token, verify_password

from app.config import API_ROLE
from app.db import connection


async def create_account(email: str, password: str) -> str:
    """
    Creates account from specified credentials and returns JWT.
    Throws error on already used email.
    """
    email = email.lower()
    valid_email(email)
    valid_password(password)

    # Insert account if email is unique
    c = connection(API_ROLE)
    cur = await c.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES (%s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        (email, hash_password(password)),
    )
    row = await cur.fetchone()
    if row is None:
        raise ValueError("Email already registered")

    user_id: UUID = row[0]
    return create_token(user_id)


def login(email: str, password: str) -> str:
    """
    Logs in on an existing user.
    Throws error on email not in use or incorrect password.
    """
    c = connection(API_ROLE)
    # Look for existing email (in lowercase)

    # Hash password

    # Match

    # Return JWT
    pass


def valid_email(email: str) -> bool:
    pass


def valid_password(password: str) -> bool:
    pass
