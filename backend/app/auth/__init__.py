"""
Handles user accounts: registration, login, password hashing and tokens. Provides
the current user dependency for the other modules' endpoints.
"""

from .router import router

__all__ = ["router"]  # defines public API for module
