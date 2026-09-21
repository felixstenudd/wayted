import os

from psycopg_pool import AsyncConnectionPool

pool = AsyncConnectionPool(os.environ["DATABASE_URL"], open=False)
