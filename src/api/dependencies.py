"""
FastAPI dependency injection — provides shared resources (Redis, rate limiter,
guardrails, embedder, etc.) to route handlers via ``Depends()``.
"""

from __future__ import annotations

from fastapi import Depends, Request

from src.config import Settings, get_settings
from src.security.auth import verify_api_key
from src.security.rate_limiter import RateLimiter


# -----------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------

async def get_redis(request: Request):
    """Return the shared ``redis.asyncio.Redis`` client from app state."""
    return request.app.state.redis


async def get_rate_limiter(request: Request) -> RateLimiter:
    """Return the shared ``RateLimiter`` instance from app state."""
    return request.app.state.rate_limiter


# -----------------------------------------------------------------------
# Combined security dependency: auth + rate-limit in one call
# -----------------------------------------------------------------------

async def require_auth_and_rate_limit(
    request: Request,
    _api_key: str = Depends(verify_api_key),
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Composite dependency that first validates the API key and then
    checks the IP-based rate limiter.

    Injected on every ``/research`` endpoint call.
    """
    rate_limiter: RateLimiter = request.app.state.rate_limiter
    await rate_limiter.check(request)
