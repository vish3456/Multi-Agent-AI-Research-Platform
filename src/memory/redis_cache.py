"""
Redis semantic cache — stores query embeddings alongside their reports and
performs brute-force cosine similarity search for cache hits.

A cache hit (cosine similarity ≥ 0.85) returns the stored report immediately,
skipping the entire LangGraph pipeline and saving LLM cost.

Notes
-----
* For production scale (> 1 000 cached queries) migrate to Redis VSS with
  RediSearch ``FT.SEARCH`` for O(log n) vector lookups.
* Embeddings are L2-normalised, so ``dot(a, b)`` = cosine similarity.
"""

from __future__ import annotations

import hashlib
import json
import logging

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)


def _query_hash(query: str) -> str:
    """Deterministic, collision-resistant hash of a query string."""
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]


class RedisSemanticCache:
    """Brute-force cosine semantic cache backed by Redis strings."""

    # Redis key prefixes
    _EMB_PREFIX = "cache:emb:"
    _REPORT_PREFIX = "cache:report:"

    def __init__(
        self,
        redis_client: redis.Redis,
        threshold: float = 0.85,
        ttl: int = 3600,
    ) -> None:
        self.redis = redis_client
        self.threshold = threshold
        self.ttl = ttl  # seconds

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    async def search(self, embedding: list[float]) -> dict | None:
        """
        Find the best-matching cached report whose cosine similarity with
        *embedding* is ≥ ``self.threshold``.

        Returns
        -------
        dict | None
            The cached report as a dictionary, or ``None`` on a miss.
        """
        keys: list[bytes] = await self.redis.keys(f"{self._EMB_PREFIX}*")
        if not keys:
            return None

        query_vec = np.array(embedding, dtype=np.float32)
        best_score: float = 0.0
        best_hash: str | None = None

        for key in keys:
            raw = await self.redis.get(key)
            if raw is None:
                continue
            data = json.loads(raw)
            stored_vec = np.array(data["embedding"], dtype=np.float32)

            # Normalised vectors → dot product == cosine similarity
            score = float(np.dot(query_vec, stored_vec))

            if score >= self.threshold and score > best_score:
                best_score = score
                best_hash = data["query_hash"]

        if best_hash is None:
            return None

        report_raw = await self.redis.get(f"{self._REPORT_PREFIX}{best_hash}")
        if report_raw is None:
            return None

        logger.info("Redis cache HIT (similarity=%.4f, hash=%s)", best_score, best_hash)
        return json.loads(report_raw)

    async def store(
        self,
        query: str,
        embedding: list[float],
        report: dict,
    ) -> None:
        """
        Cache a query's embedding and its report with an auto-expiring TTL.

        Parameters
        ----------
        query : str
            The original user query (hashed for the key).
        embedding : list[float]
            The 384-dim normalised embedding of *query*.
        report : dict
            The serialisable research report.
        """
        qhash = _query_hash(query)

        # Store embedding + hash mapping
        await self.redis.set(
            f"{self._EMB_PREFIX}{qhash}",
            json.dumps({"embedding": embedding, "query_hash": qhash}),
            ex=self.ttl,
        )

        # Store the full report
        await self.redis.set(
            f"{self._REPORT_PREFIX}{qhash}",
            json.dumps(report),
            ex=self.ttl,
        )

        logger.info("Cached report for hash=%s (TTL=%ds)", qhash, self.ttl)

    async def invalidate(self, query: str) -> None:
        """Remove a cached entry by query string."""
        qhash = _query_hash(query)
        await self.redis.delete(
            f"{self._EMB_PREFIX}{qhash}",
            f"{self._REPORT_PREFIX}{qhash}",
        )
