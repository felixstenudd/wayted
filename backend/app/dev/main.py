from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db
from app.config import API_ROLE, API_ROLE_PASSWORD
from app.dev.router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.open_pool(API_ROLE, API_ROLE_PASSWORD)
    try:
        yield
    finally:
        await db.close_pools()


app = FastAPI(title="wayted dev", lifespan=lifespan)
app.include_router(router)
