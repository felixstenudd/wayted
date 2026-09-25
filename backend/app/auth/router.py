"""
HTTP endpoints for handling user accounts
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register():
    """Create an user account."""
    pass


@router.post("/login")
def login():
    """Login as an existing user."""
    pass


@router.post("/refresh")
def refresh():
    """Exchange a valid refresh token for a new access token."""
    pass


@router.post("/logout")
def logout():
    """Revoke the refresh token."""
    pass


@router.get("/me")
def me():
    """Return the logged-in user."""
    pass


@router.post("/me/password")
def change_password():
    """Change password. Requires the current password."""
    pass
