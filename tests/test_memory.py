import json
import pytest
from unittest.mock import AsyncMock
from src.memory.redis_cache import RedisSemanticCache
from src.memory.session import SessionMemory


@pytest.mark.anyio
async def test_session_memory_operations():
    redis_mock = AsyncMock()
    redis_mock.lrange.return_value = [
        json.dumps({"role": "user", "content": "hello"}),
        json.dumps({"role": "assistant", "content": "hi"}),
    ]

    session = SessionMemory(redis_client=redis_mock, max_history=10)
    history = await session.get_history("test-session")
    assert len(history) == 2
    assert history[0]["content"] == "hello"

    await session.add_entry("test-session", {"role": "user", "content": "new message"})
    redis_mock.rpush.assert_called_once()
    redis_mock.ltrim.assert_called_once_with("session:test-session", -10, -1)
    redis_mock.expire.assert_called_once_with("session:test-session", 3600)


@pytest.mark.anyio
async def test_redis_cache_search_miss():
    redis_mock = AsyncMock()
    redis_mock.keys.return_value = []

    cache = RedisSemanticCache(redis_client=redis_mock, threshold=0.85)
    result = await cache.search([0.1, 0.2, 0.3])
    assert result is None


@pytest.mark.anyio
async def test_redis_cache_search_hit():
    redis_mock = AsyncMock()
    redis_mock.keys.return_value = ["cache:embedding:hash1"]
    # Identical unit vector -> cosine similarity = 1.0
    vec = [1.0, 0.0, 0.0]
    redis_mock.get.side_effect = [
        json.dumps({"embedding": vec, "query_hash": "hash1"}),
        json.dumps({"report": "Cached AI report", "sources": []}),
    ]

    cache = RedisSemanticCache(redis_client=redis_mock, threshold=0.85)
    result = await cache.search(vec)
    assert result is not None
    assert result["report"] == "Cached AI report"
