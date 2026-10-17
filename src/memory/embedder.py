"""
SentenceTransformer embedder — wraps all-MiniLM-L6-v2 (384-dim).

The model is loaded once at startup and reused for every embedding request.
Embeddings are L2-normalised so dot-product equals cosine similarity.
"""

from __future__ import annotations

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """Thread-safe, in-process embedding wrapper."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        logger.info("Loading SentenceTransformer model '%s' …", model_name)
        self.model = SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()
        logger.info("Model loaded — embedding dimension = %d", self._dim)

    @property
    def dimension(self) -> int:
        """Return the embedding dimensionality (384 for MiniLM-L6-v2)."""
        return self._dim

    def encode(self, text: str) -> list[float]:
        """
        Encode *text* into a normalised embedding vector.

        Returns
        -------
        list[float]
            A list of floats with length equal to ``self.dimension``.
        """
        embedding: np.ndarray = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts in a single forward pass."""
        embeddings: np.ndarray = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return embeddings.tolist()
