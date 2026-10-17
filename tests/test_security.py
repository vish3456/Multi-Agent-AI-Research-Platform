import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from src.security.rate_limiter import RateLimiter
from src.security.guardrails import BedrockGuardrails


def test_rate_limiter_under_limit():
    async def _run():
        redis_mock = AsyncMock()
        redis_mock.incr.return_value = 1
        redis_mock.expire.return_value = True

        limiter = RateLimiter(redis_mock, max_requests=10, window_seconds=60)
        request_mock = MagicMock()
        request_mock.client.host = "127.0.0.1"

        await limiter.check(request_mock)
        redis_mock.incr.assert_called_once_with("rate_limit:127.0.0.1")
        redis_mock.expire.assert_called_once_with("rate_limit:127.0.0.1", 60)

    asyncio.run(_run())


def test_rate_limiter_over_limit():
    async def _run():
        redis_mock = AsyncMock()
        redis_mock.incr.return_value = 11

        limiter = RateLimiter(redis_mock, max_requests=10, window_seconds=60)
        request_mock = MagicMock()
        request_mock.client.host = "127.0.0.1"

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(request_mock)
        assert exc_info.value.status_code == 429

    asyncio.run(_run())


def test_guardrail_pass():
    async def _run():
        guardrail = BedrockGuardrails("dummy-id", "DRAFT", "us-east-1")
        guardrail.client = MagicMock()
        guardrail.client.apply_guardrail.return_value = {
            "action": "NONE",
            "outputs": [{"text": "Hello world"}],
        }

        is_safe, text = await guardrail.check("Hello world", source="INPUT")
        assert is_safe is True
        assert text == "Hello world"

    asyncio.run(_run())


def test_guardrail_blocked():
    async def _run():
        guardrail = BedrockGuardrails("dummy-id", "DRAFT", "us-east-1")
        guardrail.client = MagicMock()
        guardrail.client.apply_guardrail.return_value = {
            "action": "GUARDRAIL_INTERVENED",
            "outputs": [{"text": "Blocked by policy"}],
        }

        is_safe, text = await guardrail.check("Attack prompt", source="INPUT")
        assert is_safe is False
        assert "Blocked" in text

    asyncio.run(_run())
