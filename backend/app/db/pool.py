import os

from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

# Host, port and database come from PGHOST, PGPORT and PGDATABASE; the role is chosen here
# so each part of the backend only gets the permissions it needs.
api_pool = AsyncConnectionPool(
    make_conninfo(user="wayted_api", password=os.environ["WAYTED_API_PASSWORD"]),
    open=False,
)

downloader_pool = AsyncConnectionPool(
    make_conninfo(user="wayted_downloader", password=os.environ["WAYTED_DOWNLOADER_PASSWORD"]),
    open=False,
)

mapper_pool = AsyncConnectionPool(
    make_conninfo(user="wayted_mapper", password=os.environ["WAYTED_MAPPER_PASSWORD"]),
    open=False,
)
