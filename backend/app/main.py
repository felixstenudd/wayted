import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.pool import api_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await api_pool.open()
    yield
    await api_pool.close()


# Docs and the OpenAPI spec are opt-in so production never exposes the API surface by accident.
docs_enabled = os.environ.get("API_DOCS_ENABLED") == "true"

app = FastAPI(
    title="wayted",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/health")
async def health():
    async with api_pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}
