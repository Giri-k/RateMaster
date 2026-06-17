import pytest
from app.algorithms.sliding_window import SlidingWindowLimiter


@pytest.fixture
def limiter():
    return SlidingWindowLimiter()


async def test_first_request_is_allowed(limiter):
    result = await limiter.check("user1", limit=5, window=60)
    assert result.allowed is True
    assert result.remaining == 4
    assert result.retry_after is None


async def test_requests_within_limit(limiter):
    for i in range(5):
        result = await limiter.check("user2", limit=5, window=60)
        assert result.allowed is True
    assert result.remaining == 0


async def test_request_over_limit_is_denied(limiter):
    for _ in range(5):
        await limiter.check("user3", limit=5, window=60)

    result = await limiter.check("user3", limit=5, window=60)
    assert result.allowed is False
    assert result.remaining == 0
    assert result.retry_after is not None
    assert result.retry_after > 0


async def test_old_requests_are_evicted(limiter):
    """Use a 1-second window. After it passes, old requests don't count."""
    for _ in range(3):
        await limiter.check("user4", limit=3, window=1)

    result = await limiter.check("user4", limit=3, window=1)
    assert result.allowed is False

    import asyncio
    await asyncio.sleep(1.1)

    result = await limiter.check("user4", limit=3, window=1)
    assert result.allowed is True
    assert result.remaining == 2


async def test_different_keys_are_independent(limiter):
    for _ in range(5):
        await limiter.check("userA", limit=5, window=60)

    result = await limiter.check("userB", limit=5, window=60)
    assert result.allowed is True
    assert result.remaining == 4
