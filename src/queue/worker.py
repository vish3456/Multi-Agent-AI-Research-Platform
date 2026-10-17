"""
Background worker — Redis Stream consumer that drives the full pipeline:

  Embed → Redis cache check → pgvector exact → pgvector related →
  LangGraph pipeline → output guardrail → evaluate → store.

Uses a consumer group so multiple workers can share the load.  Messages
are acknowledged (``XACK``) only after successful processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from src.config import Settings
from src.memory.embedder import Embedder
from src.memory.redis_cache import RedisSemanticCache
from src.memory.pgvector_store import PgVectorStore
from src.memory.session import SessionMemory
from src.security.guardrails import BedrockGuardrails
from src.agents.graph import build_research_graph
from src.evaluation.judge import evaluate_report
from src.llm.gateway import TensorZeroClient
from src.models import JobStatus

logger = logging.getLogger(__name__)


class JobWorker:
    """Async consumer that reads from the ``research_jobs`` Redis Stream."""

    STREAM = "research_jobs"
    GROUP = "research_workers"

    def __init__(
        self,
        redis_client: aioredis.Redis,
        embedder: Embedder,
        redis_cache: RedisSemanticCache,
        pgvector_store: PgVectorStore,
        session_memory: SessionMemory,
        guardrails: BedrockGuardrails,
        tz_client: TensorZeroClient,
        settings: Settings,
        consumer_name: str = "worker-1",
    ) -> None:
        self.redis = redis_client
        self.embedder = embedder
        self.redis_cache = redis_cache
        self.pgvector_store = pgvector_store
        self.session_memory = session_memory
        self.guardrails = guardrails
        self.tz_client = tz_client
        self.settings = settings
        self.consumer_name = consumer_name
        self.graph = build_research_graph()

    # ------------------------------------------------------------------ #
    # Consumer loop
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        """Main consumer loop — create group, then read-process-ack."""
        # Ensure the consumer group exists
        try:
            await self.redis.xgroup_create(
                self.STREAM, self.GROUP, id="0", mkstream=True
            )
            logger.info("Created consumer group '%s'.", self.GROUP)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.info("Consumer group '%s' already exists.", self.GROUP)
            else:
                raise

        logger.info("Worker '%s' listening on stream '%s' …", self.consumer_name, self.STREAM)

        while True:
            try:
                streams = await self.redis.xreadgroup(
                    groupname=self.GROUP,
                    consumername=self.consumer_name,
                    streams={self.STREAM: ">"},
                    count=1,
                    block=5000,
                )

                if not streams:
                    continue

                for _stream_key, messages in streams:
                    for message_id, data in messages:
                        await self._process_job(message_id, data)

            except asyncio.CancelledError:
                logger.info("Worker '%s' shutting down …", self.consumer_name)
                break
            except Exception:
                logger.exception("Unhandled error in worker loop")
                await asyncio.sleep(2)

    # ------------------------------------------------------------------ #
    # Per-job processing
    # ------------------------------------------------------------------ #

    async def _process_job(self, message_id: str, data: dict) -> None:
        """Process a single research job from the stream."""
        job_id = data.get("job_id", "unknown")
        query = data.get("query", "")
        session_id = data.get("session_id", "")

        logger.info("Processing job %s: '%s…'", job_id, query[:80])

        try:
            # Mark as processing
            await self._set_status(job_id, JobStatus.PROCESSING)

            # ----------------------------------------------------------
            # 1. Embed the query
            # ----------------------------------------------------------
            embedding = self.embedder.encode(query)

            # ----------------------------------------------------------
            # 2. Redis semantic cache check (cosine ≥ 0.85)
            # ----------------------------------------------------------
            cached = await self.redis_cache.search(embedding)
            if cached is not None:
                logger.info("Job %s: Redis cache HIT — returning cached report.", job_id)
                await self._finish_job(job_id, query, session_id, cached, message_id, cached=True)
                return

            # ----------------------------------------------------------
            # 3. pgvector exact match (cosine ≥ 0.88)
            # ----------------------------------------------------------
            ltm_exact = await self.pgvector_store.exact_search(
                embedding, threshold=self.settings.ltm_exact_threshold
            )
            if ltm_exact is not None:
                logger.info("Job %s: pgvector EXACT HIT (sim=%.4f).", job_id, ltm_exact["similarity"])
                report = ltm_exact["report"]
                # Cache in Redis for faster future hits
                await self.redis_cache.store(query, embedding, report)
                await self._finish_job(job_id, query, session_id, report, message_id, cached=True)
                return

            # ----------------------------------------------------------
            # 4. pgvector related memories (0.50 ≤ sim < 0.88)
            # ----------------------------------------------------------
            related = await self.pgvector_store.related_search(
                embedding,
                low=self.settings.ltm_related_threshold,
                high=self.settings.ltm_exact_threshold,
            )

            # ----------------------------------------------------------
            # 5. Session history
            # ----------------------------------------------------------
            session_history: list[dict] = []
            if session_id:
                session_history = await self.session_memory.get_history(session_id)

            # ----------------------------------------------------------
            # 6. Run LangGraph pipeline
            # ----------------------------------------------------------
            initial_state = {
                "query": query,
                "session_history": session_history,
                "related_memories": related,
                "search_results": [],
                "summary_bullets": [],
                "draft_report": "",
                "critic_feedback": "",
                "critic_passed": False,
                "retry_count": 0,
                "final_report": "",
                "sources": [],
            }

            result_state = await self.graph.ainvoke(initial_state)

            report_text = result_state.get("final_report", result_state.get("draft_report", ""))
            sources = result_state.get("sources", [])

            # ----------------------------------------------------------
            # 7. Output guardrail
            # ----------------------------------------------------------
            is_safe, safe_text = await self.guardrails.check(report_text, source="OUTPUT")
            if not is_safe:
                logger.warning("Job %s: output blocked by guardrail.", job_id)
                await self._set_result(job_id, {
                    "job_id": job_id,
                    "query": query,
                    "report": safe_text,
                    "sources": [],
                    "evaluation": {},
                    "cached": False,
                    "status": JobStatus.COMPLETED.value,
                })
                await self.redis.xack(self.STREAM, self.GROUP, message_id)
                return

            # ----------------------------------------------------------
            # 8. LLM-as-judge evaluation
            # ----------------------------------------------------------
            eval_scores = await evaluate_report(query, report_text, self.tz_client)

            # ----------------------------------------------------------
            # 9. Store results
            # ----------------------------------------------------------
            report_dict = {
                "report": report_text,
                "sources": sources,
            }

            # Redis cache
            await self.redis_cache.store(query, embedding, report_dict)

            # pgvector long-term memory
            await self.pgvector_store.store(
                query=query,
                report=report_dict,
                embedding=embedding,
                sources=sources,
                evaluation=eval_scores,
            )

            # Session memory
            if session_id:
                await self.session_memory.add_entry(session_id, {"role": "user", "content": query})
                await self.session_memory.add_entry(session_id, {"role": "assistant", "content": report_text})

            # ----------------------------------------------------------
            # 10. Finalise
            # ----------------------------------------------------------
            result = {
                "job_id": job_id,
                "query": query,
                "report": report_text,
                "sources": sources,
                "evaluation": eval_scores,
                "cached": False,
                "status": JobStatus.COMPLETED.value,
            }
            await self._set_result(job_id, result)
            await self.redis.xack(self.STREAM, self.GROUP, message_id)
            logger.info("Job %s completed successfully.", job_id)

        except Exception:
            logger.exception("Job %s failed.", job_id)
            await self._set_status(job_id, JobStatus.FAILED, error=traceback.format_exc())
            await self.redis.xack(self.STREAM, self.GROUP, message_id)

    # ------------------------------------------------------------------ #
    # Shortcut: finish with a cached/LTM hit
    # ------------------------------------------------------------------ #

    async def _finish_job(
        self,
        job_id: str,
        query: str,
        session_id: str,
        report: dict,
        message_id: str,
        cached: bool = False,
    ) -> None:
        """Wrap up a job that was served from cache or LTM."""
        report_text = report.get("report", str(report))

        # Output guardrail
        is_safe, safe_text = await self.guardrails.check(report_text, source="OUTPUT")
        if not is_safe:
            report_text = safe_text

        result = {
            "job_id": job_id,
            "query": query,
            "report": report_text,
            "sources": report.get("sources", []),
            "evaluation": report.get("evaluation", {}),
            "cached": cached,
            "status": JobStatus.COMPLETED.value,
        }
        await self._set_result(job_id, result)

        if session_id:
            await self.session_memory.add_entry(session_id, {"role": "user", "content": query})
            await self.session_memory.add_entry(session_id, {"role": "assistant", "content": report_text})

        await self.redis.xack(self.STREAM, self.GROUP, message_id)

    # ------------------------------------------------------------------ #
    # Status helpers
    # ------------------------------------------------------------------ #

    async def _set_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> None:
        data: dict = {"status": status.value}
        if error:
            data["error"] = error
        await self.redis.hset(f"job:{job_id}", mapping=data)
        await self.redis.expire(f"job:{job_id}", 3600)

    async def _set_result(self, job_id: str, result: dict) -> None:
        await self.redis.hset(
            f"job:{job_id}",
            mapping={
                "status": result.get("status", JobStatus.COMPLETED.value),
                "result": json.dumps(result),
            },
        )
        await self.redis.expire(f"job:{job_id}", 3600)
