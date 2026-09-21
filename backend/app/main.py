from contextlib import asynccontextmanager

from app.db.pool import pool
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(title="wayted", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "API is running"}


@app.get("/health")
async def health():
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}
