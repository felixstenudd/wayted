from psycopg_pool import AsyncConnectionPool

# An empty conninfo makes libpq read PGHOST, PGUSER, PGPASSWORD etc. from the environment.
pool = AsyncConnectionPool("", open=False)
