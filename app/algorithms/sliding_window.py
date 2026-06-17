import time
import uuid

from app.algorithms.base import RateLimiter, RateLimitResult
from app.redis_client import get_redis, load_script

# Memory: O(requests_per_window) per identifier — each request stored as a sorted set member.
LUA_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, ttl)
    return {1, limit - count - 1, 0}
end

local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry_after = 0
if oldest and #oldest >= 2 then
    retry_after = tonumber(oldest[2]) + window - now
end

return {0, 0, math.ceil(retry_after)}
"""


class SlidingWindowLimiter(RateLimiter):
    def __init__(self):
        self._sha: str | None = None

    async def _ensure_script(self) -> str:
        if self._sha is None:
            self._sha = await load_script(LUA_SCRIPT)
        return self._sha

    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        sha = await self._ensure_script()
        r = await get_redis()

        now = time.time()
        member = str(uuid.uuid4())
        redis_key = f"ratelimit:sliding:{key}"
        ttl = window + 1

        allowed, remaining, retry_after = await r.evalsha(
            sha, 1, redis_key, window, limit, now, member, ttl
        )

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=remaining,
            reset_at=int(now) + (0 if allowed else retry_after),
            retry_after=retry_after if not allowed else None,
        )
