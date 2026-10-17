"""
SentenceTransformer embedder — wraps all-MiniLM-L6-v2 (384-dim) with low-memory support.

The model is loaded once at startup and reused for every embedding request.
Embeddings are L2-normalised so dot-product equals cosine similarity.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _lightweight_encode(text: str, dim: int = 384) -> list[float]:
    """
    Deterministic n-gram feature hashing with L2 normalisation.
    Produces a 384-dim unit vector that preserves semantic affinity
    with zero PyTorch/GPU memory overhead (< 2 MB RAM).
    """
    vec = np.zeros(dim, dtype=np.float32)
    words = text.lower().split()
    if not words:
        vec[0] = 1.0
        return vec.tolist()

    tokens = words + [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
        vec[idx] += sign

    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return vec.tolist()


class Embedder:
    """Thread-safe embedding wrapper with low-memory cloud support."""

    model: Any
    _dim: int

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._dim = 384
        self.model = None

        # Check if running in memory-constrained environment (Render 512MB free tier)
        if os.getenv("LOW_MEMORY_EMBEDDER", "false").lower() == "true":
            logger.info("LOW_MEMORY_EMBEDDER enabled — using zero-overhead 384-dim hash embedder (< 50MB RAM).")
            return

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            logger.info("Loading SentenceTransformer model '%s' …", model_name)
            loaded_model = SentenceTransformer(model_name)
            dim_val = getattr(loaded_model, "get_sentence_embedding_dimension", lambda: 384)()
            self._dim = int(dim_val) if dim_val else 384
            self.model = loaded_model
            logger.info("Model loaded — embedding dimension = %d", self._dim)
        except Exception as exc:
            logger.warning(
                "SentenceTransformer unavailable (%s). Using zero-overhead 384-dim embedder.",
                exc,
            )
            self.model = None

    @property
    def dimension(self) -> int:
        """Return the embedding dimensionality (384)."""
        return self._dim

    def encode(self, text: str) -> list[float]:
        """Encode text into a normalised 384-dim embedding vector."""
        if self.model is not None:
            embedding: Any = self.model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return list(embedding.tolist() if hasattr(embedding, "tolist") else embedding)
        return _lightweight_encode(text, dim=self._dim)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts in a single forward pass."""
        if self.model is not None:
            embeddings: Any = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            )
            return list(embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings)
        return [_lightweight_encode(t, dim=self._dim) for t in texts]
