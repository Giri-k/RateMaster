import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.algorithms.base import RateLimiter
from app.algorithms.fixed_window import FixedWindowLimiter
from app.algorithms.sliding_window import SlidingWindowLimiter
from app.algorithms.token_bucket import TokenBucketLimiter
from app.config import RATE_LIMIT_RULES, RuleConfig

logger = logging.getLogger("ratemaster")

ALGORITHMS: dict[str, RateLimiter] = {
    "fixed": FixedWindowLimiter(),
    "token": TokenBucketLimiter(),
    "sliding": SlidingWindowLimiter(),
}

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/metrics"}


def get_identifier(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    return request.client.host if request.client else "unknown"


def get_rule(path: str) -> RuleConfig:
    if path in RATE_LIMIT_RULES:
        return RATE_LIMIT_RULES[path]
    return RATE_LIMIT_RULES["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        identifier = get_identifier(request)
        rule = get_rule(request.url.path)
        limiter = ALGORITHMS[rule.algorithm]

        key = f"{identifier}:{request.url.path}"
        result = await limiter.check(key, rule.limit, rule.window)

        if not result.allowed:
            logger.warning(
                "Rate limited: identifier=%s path=%s", identifier, request.url.path
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "retry_after": result.retry_after,
                },
                headers={
                    "Retry-After": str(result.retry_after),
                    "X-RateLimit-Limit": str(rule.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_at),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rule.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)
        return response
