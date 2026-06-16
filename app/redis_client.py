import redis.asyncio as redis

from app.config import settings

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def load_script(script: str) -> str:
    """Register a Lua script with Redis and return its SHA hash.

    The SHA is used with EVALSHA to execute the script without
    re-transmitting it on every call.
    """
    r = await get_redis()
    sha: str = await r.script_load(script)
    return sha
