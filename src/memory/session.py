"""
Redis-backed session memory — maintains per-conversation history.

Each session is a Redis list capped at ``max_history`` entries with an
auto-expiring TTL so idle sessions are garbage-collected.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SessionMemory:
    """Lightweight per-session conversation memory stored in Redis lists."""

    _PREFIX = "session:"

    def __init__(
        self,
        redis_client: redis.Redis,
        max_history: int = 20,
        ttl: int = 3600,
    ) -> None:
        self.redis = redis_client
        self.max_history = max_history
        self.ttl = ttl  # seconds

    async def get_history(self, session_id: str) -> list[dict]:
        """
        Retrieve the conversation history for *session_id*.

        Returns
        -------
        list[dict]
            Ordered list of ``{"role": …, "content": …}`` entries, oldest
            first.  Returns an empty list if the session doesn't exist.
        """
        key = f"{self._PREFIX}{session_id}"
        raw_items = await self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in raw_items]

    async def add_entry(
        self,
        session_id: str,
        entry: dict,
    ) -> None:
        """
        Append an entry to the session history, trim to ``max_history``,
        and refresh the TTL.

        Parameters
        ----------
        session_id : str
            The session identifier.
        entry : dict
            Typically ``{"role": "user"|"assistant", "content": "…"}``.
        """
        key = f"{self._PREFIX}{session_id}"
        await self.redis.rpush(key, json.dumps(entry))
        await self.redis.ltrim(key, -self.max_history, -1)
        await self.redis.expire(key, self.ttl)

    async def clear(self, session_id: str) -> None:
        """Delete the entire session history."""
        await self.redis.delete(f"{self._PREFIX}{session_id}")
