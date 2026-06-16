import pytest_asyncio
from app.redis_client import get_redis, close_redis


@pytest_asyncio.fixture(autouse=True)
async def flush_redis():
    r = await get_redis()
    await r.flushdb()
    yield
    await r.flushdb()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_pool():
    yield
    await close_redis()
