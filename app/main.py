from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.middleware import RateLimitMiddleware
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


app.add_middleware(RateLimitMiddleware)


@app.get("/health")
async def health():
    r = await get_redis()
    redis_ok = await r.ping()
    return {"status": "ok", "redis": "connected" if redis_ok else "disconnected"}


@app.get("/api/status", tags=["demo"])
async def status():
    return {"endpoint": "status", "algorithm": "fixed_window", "limit": "100/min"}


@app.get("/api/search", tags=["demo"])
async def search():
    return {"endpoint": "search", "algorithm": "token_bucket", "limit": "20/min"}


@app.post("/api/login", tags=["demo"])
async def login():
    return {"endpoint": "login", "algorithm": "sliding_window", "limit": "5/min"}
