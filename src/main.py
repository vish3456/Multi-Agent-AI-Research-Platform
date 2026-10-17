"""
FastAPI application entry point.

Lifecycle:
  * **Startup** — initialises Redis, PostgreSQL (with pgvector schema),
    SentenceTransformer embedder, security components, LLM gateway client,
    and starts the background job worker.
  * **Shutdown** — closes Redis, PostgreSQL, and HTTP client connections.

Run locally with::

    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.config import get_settings
from src.api.routes import router as research_router
from src.security.rate_limiter import RateLimiter
from src.security.guardrails import BedrockGuardrails
from src.memory.embedder import Embedder
from src.memory.redis_cache import RedisSemanticCache
from src.memory.pgvector_store import PgVectorStore
from src.memory.session import SessionMemory
from src.queue.producer import JobProducer
from src.queue.worker import JobWorker
from src.llm.gateway import TensorZeroClient
from src.agents import search_agent, summarize_agent, writer_agent, critic_agent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup; tear down on shutdown."""
    settings = get_settings()

    # --- LangSmith environment ---
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
        logger.info("LangSmith tracing enabled (project=%s).", settings.langsmith_project)

    # --- Redis ---
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    app.state.redis = redis_client
    logger.info("Redis connected: %s", settings.redis_url)

    # --- PostgreSQL + pgvector ---
    db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
    )
    app.state.db_pool = db_pool

    pgvector_store = PgVectorStore(db_pool)
    await pgvector_store.init_schema()
    app.state.pgvector_store = pgvector_store
    logger.info("PostgreSQL + pgvector initialised.")

    # --- Embedder ---
    embedder = Embedder(model_name=settings.embedding_model)
    app.state.embedder = embedder

    # --- Security ---
    rate_limiter = RateLimiter(
        redis_client=redis_client,
        max_requests=settings.rate_limit_max,
        window_seconds=settings.rate_limit_window,
    )
    app.state.rate_limiter = rate_limiter

    guardrails = BedrockGuardrails(
        guardrail_id=settings.guardrail_id,
        guardrail_version=settings.guardrail_version,
        region=settings.aws_region,
    )
    app.state.guardrails = guardrails

    # --- Memory ---
    redis_cache = RedisSemanticCache(
        redis_client=redis_client,
        threshold=settings.cache_similarity_threshold,
    )
    app.state.redis_cache = redis_cache

    session_memory = SessionMemory(redis_client=redis_client)
    app.state.session_memory = session_memory

    # --- LLM Gateway ---
    tz_client = TensorZeroClient(base_url=settings.tensorzero_url)
    app.state.tz_client = tz_client

    # Inject the TZ client into all agent modules
    search_agent.set_tz_client(tz_client)
    summarize_agent.set_tz_client(tz_client)
    writer_agent.set_tz_client(tz_client)
    critic_agent.set_tz_client(tz_client)

    # --- Queue ---
    producer = JobProducer(redis_client=redis_client)
    app.state.producer = producer

    worker = JobWorker(
        redis_client=redis_client,
        embedder=embedder,
        redis_cache=redis_cache,
        pgvector_store=pgvector_store,
        session_memory=session_memory,
        guardrails=guardrails,
        tz_client=tz_client,
        settings=settings,
    )
    app.state.worker = worker

    # Start the background worker
    worker_task = asyncio.create_task(worker.run())
    logger.info("Background worker started.")

    yield  # ---- Application is running ----

    # --- Shutdown ---
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    await tz_client.close()
    await db_pool.close()
    await redis_client.close()
    logger.info("All resources cleaned up. Goodbye.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Multi-Agent AI Research Platform",
    description=(
        "Four-agent LangGraph pipeline (Search → Summarize → Writer → Critic) "
        "with semantic caching, Bedrock Guardrails, TensorZero LLM gateway, "
        "and LLM-as-judge evaluation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(research_router, tags=["Research"])

STATIC_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_frontend() -> HTMLResponse:
    """Serve the NexusResearch interactive dashboard."""
    if STATIC_INDEX.exists():
        return HTMLResponse(content=STATIC_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NexusResearch Dashboard</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")
