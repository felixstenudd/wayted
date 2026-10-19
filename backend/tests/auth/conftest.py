import os

# app.config reads these at import time; the auth tests never reach a database.
for name in (
    "JWT_SECRET",
    "WAYTED_API_PASSWORD",
    "WAYTED_DOWNLOADER_PASSWORD",
    "WAYTED_MAPPER_PASSWORD",
    "WAYTED_ENRICHER_PASSWORD",
):
    os.environ.setdefault(name, "test")
