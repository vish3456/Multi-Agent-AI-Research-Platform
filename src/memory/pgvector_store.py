"""
pgvector long-term memory (LTM) — stores research reports alongside their
384-dim embeddings in PostgreSQL with the ``pgvector`` extension.

Supports two search modes:
* **Exact match** (cosine similarity ≥ 0.88) — returns the stored report
  directly, skipping the LangGraph pipeline.
* **Related search** (0.50 ≤ similarity < 0.88) — returns contextually
  relevant prior reports that are passed to the Writer agent as background.

An HNSW index on the embedding column accelerates cosine lookups.
"""

from __future__ import annotations

import json
import logging

import asyncpg
from pgvector.asyncpg import register_vector

logger = logging.getLogger(__name__)


class PgVectorStore:
    """Async pgvector-backed long-term memory store."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    # --------------------------------------------------------------------- #
    # Schema bootstrap
    # --------------------------------------------------------------------- #

    async def init_schema(self) -> None:
        """
        Create the ``vector`` extension, the ``long_term_memory`` table, and
        an HNSW index if they don't already exist.

        Safe to call on every startup (idempotent).
        """
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await register_vector(conn)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id          BIGSERIAL   PRIMARY KEY,
                    query       TEXT        NOT NULL,
                    report      JSONB       NOT NULL,
                    embedding   vector(384) NOT NULL,
                    sources     JSONB       DEFAULT '[]'::jsonb,
                    evaluation  JSONB       DEFAULT '{}'::jsonb,
                    created_at  TIMESTAMPTZ DEFAULT now()
                );
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ltm_hnsw_cosine_idx
                    ON long_term_memory
                 USING hnsw (embedding vector_cosine_ops);
                """
            )
            logger.info("pgvector schema initialised.")

    # --------------------------------------------------------------------- #
    # Search
    # --------------------------------------------------------------------- #

    async def exact_search(
        self,
        embedding: list[float],
        threshold: float = 0.88,
    ) -> dict | None:
        """
        Find a stored report whose cosine similarity with *embedding* is
        **≥ threshold** (default 0.88).

        Returns
        -------
        dict | None
            ``{"query": …, "report": …, "similarity": …}`` or ``None``.
        """
        async with self.pool.acquire() as conn:
            await register_vector(conn)
            row = await conn.fetchrow(
                """
                SELECT query,
                       report,
                       sources,
                       evaluation,
                       1 - (embedding <=> $1) AS similarity
                  FROM long_term_memory
                 WHERE 1 - (embedding <=> $1) >= $2
                 ORDER BY embedding <=> $1
                 LIMIT 1
                """,
                embedding,
                threshold,
            )
            if row is None:
                return None

            logger.info("pgvector EXACT HIT (similarity=%.4f)", row["similarity"])
            return {
                "query": row["query"],
                "report": json.loads(row["report"]) if isinstance(row["report"], str) else dict(row["report"]),
                "sources": json.loads(row["sources"]) if isinstance(row["sources"], str) else list(row["sources"]),
                "evaluation": json.loads(row["evaluation"]) if isinstance(row["evaluation"], str) else dict(row["evaluation"]),
                "similarity": float(row["similarity"]),
            }

    async def related_search(
        self,
        embedding: list[float],
        low: float = 0.50,
        high: float = 0.88,
        limit: int = 5,
    ) -> list[dict]:
        """
        Return up to *limit* reports whose cosine similarity falls within
        [*low*, *high*).  These are passed to the Writer as context.
        """
        async with self.pool.acquire() as conn:
            await register_vector(conn)
            rows = await conn.fetch(
                """
                SELECT query,
                       report,
                       1 - (embedding <=> $1) AS similarity
                  FROM long_term_memory
                 WHERE 1 - (embedding <=> $1) >= $2
                   AND 1 - (embedding <=> $1) <  $3
                 ORDER BY embedding <=> $1
                 LIMIT $4
                """,
                embedding,
                low,
                high,
                limit,
            )
            result = [
                {
                    "query": r["query"],
                    "report": json.loads(r["report"]) if isinstance(r["report"], str) else dict(r["report"]),
                    "similarity": float(r["similarity"]),
                }
                for r in rows
            ]
            if result:
                logger.info("pgvector RELATED hits: %d (best=%.4f)", len(result), result[0]["similarity"])
            return result

    # --------------------------------------------------------------------- #
    # Store
    # --------------------------------------------------------------------- #

    async def store(
        self,
        query: str,
        report: dict,
        embedding: list[float],
        sources: list[str] | None = None,
        evaluation: dict | None = None,
    ) -> int:
        """
        Persist a report and its embedding in long-term memory.

        Returns
        -------
        int
            The auto-generated primary key of the new row.
        """
        async with self.pool.acquire() as conn:
            await register_vector(conn)
            row_id: int = await conn.fetchval(
                """
                INSERT INTO long_term_memory (query, report, embedding, sources, evaluation)
                VALUES ($1, $2::jsonb, $3, $4::jsonb, $5::jsonb)
                RETURNING id
                """,
                query,
                json.dumps(report),
                embedding,
                json.dumps(sources or []),
                json.dumps(evaluation or {}),
            )
            logger.info("Stored LTM entry id=%d for query '%s…'", row_id, query[:60])
            return row_id
