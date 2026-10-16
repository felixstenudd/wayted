"""Application settings loaded from environment variables"""

import os

JWT_SECRET: str = os.environ["JWT_SECRET"]
ACCESS_TOKEN_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_TTL_DAYS: int = 30
# Browsers drop Secure cookies sent over plain http, except on localhost in most browsers.
# Set to "false" only in development.
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "true") == "true"
API_ROLE: str = "wayted_api"
DOWNLOADER_ROLE: str = "wayted_downloader"
MAPPER_ROLE: str = "wayted_mapper"
API_ROLE_PASSWORD: str = os.environ["WAYTED_API_PASSWORD"]
DOWNLOADER_ROLE_PASSWORD: str = os.environ["WAYTED_DOWNLOADER_PASSWORD"]
MAPPER_ROLE_PASSWORD: str = os.environ["WAYTED_MAPPER_PASSWORD"]
