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

API docs (`/docs`, `/redoc`, `/openapi.json`) are only served when `API_DOCS_ENABLED=true`, which the dev compose file sets and production does not.

## Authentication

Signing in returns a short-lived access token (15 min) in the JSON body, and sets a long-lived refresh token (30 days) as an `httpOnly`, `SameSite=Strict` cookie. The frontend keeps the access token in memory only; on page load and whenever it expires, it calls `/api/auth/refresh` and the browser sends the cookie by itself. Each refresh replaces the cookie, and reusing an old one ends the session everywhere.

The cookie is marked `Secure` (https only) unless `COOKIE_SECURE=false`, which only the dev compose file sets. Production must therefore be served over https, or browsers will drop the cookie and nobody stays signed in after a reload.
