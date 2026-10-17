"""
Redis-backed IP rate limiter — 10 requests per 60 seconds per client IP.

Uses a simple INCR + EXPIRE strategy (fixed-window counter).  The window
size and max-request count are configurable via ``Settings``.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

from fastapi import HTTPException, Request


class RateLimiter:
    """Fixed-window rate limiter backed by a Redis counter."""

    def __init__(
        self,
        redis_client: Any,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds

    async def check(self, request: Request) -> None:
        """
        Increment the counter for the caller's IP and raise 429 if the
        configured limit has been exceeded.

        Parameters
        ----------
        request : Request
            The current FastAPI request (used to read ``client.host``).

        Raises
        ------
        HTTPException
            429 Too Many Requests when the caller exceeds the limit.
        """
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        current = await self.redis.incr(key)

        # Set the TTL only on the first request inside a new window
        if current == 1:
            await self.redis.expire(key, self.window)

        if current > self.max_requests:
            ttl = await self.redis.ttl(key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
            )
