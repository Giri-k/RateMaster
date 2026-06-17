import time

from app.algorithms.base import RateLimiter, RateLimitResult
from app.redis_client import get_redis, load_script

LUA_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
local tokens_to_add = elapsed * refill_rate
tokens = math.min(capacity, tokens + tokens_to_add)
last_refill = now

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after = (1 - tokens) / refill_rate
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, ttl)

return {allowed, math.floor(tokens), math.ceil(retry_after)}
"""


class TokenBucketLimiter(RateLimiter):
    def __init__(self):
        self._sha: str | None = None

    async def _ensure_script(self) -> str:
        if self._sha is None:
            self._sha = await load_script(LUA_SCRIPT)
        return self._sha

    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        sha = await self._ensure_script()
        r = await get_redis()

        capacity = limit
        refill_rate = limit / window
        now = time.time()
        ttl = int((capacity / refill_rate) * 2)

        redis_key = f"ratelimit:token_bucket:{key}"
        allowed, remaining, retry_after = await r.evalsha(
            sha, 1, redis_key, capacity, refill_rate, now, ttl
        )

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=remaining,
            reset_at=int(now) + (0 if allowed else retry_after),
            retry_after=retry_after if not allowed else None,
        )
