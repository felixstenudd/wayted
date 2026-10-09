## Environment variables

Copy `.env.example` to `.env` and fill in the values.

```
POSTGRES_USER=wayted
POSTGRES_PASSWORD=change-me
POSTGRES_DB=wayted
WAYTED_DOWNLOADER_PASSWORD=change-me
WAYTED_MAPPER_PASSWORD=change-me
WAYTED_API_PASSWORD=change-me
JWT_SECRET=change-me
HTTP_PORT=80
DB_PORT=5432
```

## Running with Docker

The frontend reaches the backend through `/api`, which is proxied to FastAPI with the prefix stripped (`/api/health` → `/health`).

### Development

```
docker compose -f docker-compose.dev.yml up --build
```

- Frontend (Vite, hot reload): http://localhost:5173
- Backend (uvicorn `--reload`): http://localhost:8000, docs at http://localhost:8000/docs
- Postgres: `localhost:${DB_PORT:-5432}`
- Worker: fetches and maps the tiles queued in `raw.pending_tiles`. It does not reload; run `docker compose -f docker-compose.dev.yml restart worker` after changing backend code.

Source code is bind-mounted, so edits apply without rebuilding. After changing `frontend/package.json` or `backend/pyproject.toml`, rebuild and renew the `node_modules` volume:

```
docker compose -f docker-compose.dev.yml up --build -V
```

The frontend can also run outside Docker with `npm run dev` in `frontend/`; it proxies `/api` to `http://localhost:8000` by default.

### Production

```
docker compose -f docker-compose.prod.yml up -d --build
```

nginx serves the built frontend on `HTTP_PORT` (default 80) and proxies `/api` to the backend. The backend and database are not exposed on the host.

A `worker` container fetches and maps queued tiles; it needs outbound access to the Overpass API.

API docs (`/docs`, `/redoc`, `/openapi.json`) are only served when `API_DOCS_ENABLED=true`, which the dev compose file sets and production does not.
