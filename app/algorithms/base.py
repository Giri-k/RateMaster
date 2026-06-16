from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: int
    retry_after: int | None


class RateLimiter(ABC):
    @abstractmethod
    async def check(self, key: str, limit: int, window: int) -> RateLimitResult:
        pass
