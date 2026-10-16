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
VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/positron
DEV_PANEL_BIND=127.0.0.1
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
- Dev API (internal tools, no login): http://localhost:8001, docs at http://localhost:8001/docs. Lists fetched and queued tiles, returns the graph of an area, and queues the area inside a circle for the worker.
- Dev panel (internal tools, no login): http://localhost:5174. A map of what the pipeline has stored: fetched and queued tiles, the graph of a view, and a circle tool that queues an area for the worker. It uses the dev API.

Source code is bind-mounted, so edits apply without rebuilding. After changing `frontend/package.json` or `backend/pyproject.toml`, rebuild and renew the `node_modules` volume:

```
docker compose -f docker-compose.dev.yml up --build -V
```

The frontend can also run outside Docker with `npm run dev` in `frontend/`; it proxies `/api` to `http://localhost:8000` by default.

The dev panel runs outside Docker with `npm run dev:panel` in `frontend/`; it proxies `/api` to `http://localhost:8001` and reads `VITE_MAP_STYLE_URL` from the repository's `.env`. After changing the dev API, regenerate the panel's types with `npm run api:dev-panel` while the dev API runs.

### Production

```
docker compose -f docker-compose.prod.yml up -d --build
```

nginx serves the built frontend on `HTTP_PORT` (default 80) and proxies `/api` to the backend. The backend and database are not exposed on the host.

A `worker` container fetches and maps queued tiles; it needs outbound access to the Overpass API.

A `dev-api` container serves the internal tools. It has no login, so it is published on `127.0.0.1:8001` only: use it from the server, or through `ssh -L 8001:localhost:8001 <server>`. Never forward the public nginx to it.

A `dev-panel` container serves the dev panel on `127.0.0.1:8002` and forwards its `/api` to `dev-api`. It has no login either: use it through `ssh -L 8002:localhost:8002 <server>`, or set `DEV_PANEL_BIND` to an address on an internal network. `VITE_MAP_STYLE_URL` is read when the image is built.

API docs (`/docs`, `/redoc`, `/openapi.json`) are only served when `API_DOCS_ENABLED=true`, which the dev compose file sets and production does not.
