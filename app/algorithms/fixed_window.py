import time

from app.algorithms.base import RateLimiter, RateLimitResult
from app.redis_client import get_redis, load_script

LUA_SCRIPT = """
local counter = redis.call('INCR', KEYS[1])
if counter == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return counter
"""


class FixedWindowLimiter(RateLimiter):
    def __init__(self):
        self._sha: str | None = None

    async def _ensure_script(self) -> str:
        if self._sha is None:
            self._sha = await load_script(LUA_SCRIPT)
            print("sha after loading lua script -> ", self._sha)
        return self._sha

    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        sha = await self._ensure_script()
        r = await get_redis()

        now = time.time()
        window_epoch = int(now) // window
        redis_key = f"ratelimit:fixed:{key}:{window_epoch}"

        counter = await r.evalsha(sha, 1, redis_key, window)

        allowed = counter <= limit
        remaining = max(0, limit - counter)
        reset_at = (window_epoch + 1) * window
        retry_after = None if allowed else reset_at - int(now)

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )
