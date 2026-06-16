from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import get_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    yield
    await close_redis()


app = FastAPI(
    title="RateMaster",
    description="Distributed rate limiter with Token Bucket, Sliding Window, and Fixed Window algorithms",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    r = await get_redis()
    redis_ok = await r.ping()
    return {"status": "ok", "redis": "connected" if redis_ok else "disconnected"}
