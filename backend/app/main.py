import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import auth, db, logbook, routing
from app.config import API_ROLE, API_ROLE_PASSWORD


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.open_pool(API_ROLE, API_ROLE_PASSWORD)
    try:
        yield
    finally:
        await db.close_pools()


# Docs and the OpenAPI spec are opt-in so production never exposes the API surface by accident.
docs_enabled = os.environ.get("API_DOCS_ENABLED") == "true"

app = FastAPI(
    title="wayted",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.include_router(auth.router)
app.include_router(logbook.router)
app.include_router(routing.router)


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/health")
async def health():
    async with db.connection(API_ROLE) as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}
