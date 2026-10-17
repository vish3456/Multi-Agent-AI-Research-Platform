import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from src.api.routes import router
from src.models import JobStatus
from src.config import Settings, get_settings


@pytest.fixture
def test_settings():
    return Settings(
        api_key="valid-test-key",
        database_url="postgresql://postgres:postgres@localhost:5432/research_platform",
        guardrail_id="test-guardrail",
    )


@pytest.fixture
def test_app(test_settings):
    app = FastAPI()
    app.include_router(router)

    # Provide overrides and mocked state
    app.dependency_overrides[get_settings] = lambda: test_settings

    app.state.redis = AsyncMock()
    app.state.producer = AsyncMock()
    app.state.rate_limiter = AsyncMock()
    app.state.guardrails = AsyncMock()

    return app


@pytest.mark.anyio
async def test_health_endpoint(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy", "service": "multi-agent-research-platform"}


@pytest.mark.anyio
async def test_research_missing_api_key(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/research", json={"query": "test"})
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_research_invalid_api_key(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/research",
            headers={"X-API-Key": "wrong-key"},
            json={"query": "test"},
        )
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_research_blocked_by_guardrail(test_app):
    test_app.state.guardrails.check.return_value = (False, "Harmful prompt detected")

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/research",
            headers={"X-API-Key": "valid-test-key"},
            json={"query": "malicious query"},
        )
        assert resp.status_code == 400
        assert "Input blocked: Harmful prompt detected" in resp.json()["detail"]


@pytest.mark.anyio
async def test_research_success_enqueued(test_app):
    test_app.state.guardrails.check.return_value = (True, "clean query")

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/research",
            headers={"X-API-Key": "valid-test-key"},
            json={"query": "clean query", "session_id": "sess-1"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"

        test_app.state.producer.enqueue.assert_called_once()
        test_app.state.redis.hset.assert_called_once()


@pytest.mark.anyio
async def test_get_status_not_found(test_app):
    test_app.state.redis.hgetall.return_value = {}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/status/non-existent-id")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_status_completed_with_result(test_app):
    mock_result = {
        "job_id": "test-id",
        "query": "clean query",
        "report": "Final synthesized research report",
        "sources": ["https://arxiv.org/1"],
        "evaluation": {
            "relevance": 9.0,
            "completeness": 8.5,
            "hallucination": 9.5,
            "quality": 8.0,
        },
        "cached": False,
    }
    test_app.state.redis.hgetall.return_value = {
        b"status": b"completed",
        b"result": json.dumps(mock_result).encode(),
    }

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/status/test-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "test-id"
        assert data["status"] == "completed"
        assert data["result"]["report"] == "Final synthesized research report"
        assert data["result"]["evaluation"]["relevance"] == 9.0
