"""
Job producer — enqueues research requests into a Redis Stream.

The stream name is ``research_jobs``.  Each message carries:
  * ``job_id``    — UUID for tracking
  * ``query``     — the user's research question
  * ``session_id`` — optional conversational context handle
"""

from __future__ import annotations

import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class JobProducer:
    """Pushes research requests into the Redis Stream job queue."""

    STREAM = "research_jobs"

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def enqueue(
        self,
        job_id: str,
        query: str,
        session_id: str | None = None,
    ) -> str:
        """
        Add a job to the stream.

        Returns
        -------
        str
            The Redis-generated stream message ID.
        """
        msg_id: bytes = await self.redis.xadd(
            self.STREAM,
            {
                "job_id": job_id,
                "query": query,
                "session_id": session_id or "",
            },
        )
        logger.info("Enqueued job %s → stream ID %s", job_id, msg_id)
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
