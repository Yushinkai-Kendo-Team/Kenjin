"""Embedding model wrapper using sentence-transformers.

Phase 2A: Automatic instruction prefix detection for E5/BGE model families.
Models like intfloat/multilingual-e5-* require "query: " and "passage: " prefixes.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from kendocenter.config import settings

# Model families that require query/passage instruction prefixes.
# Detected automatically from model name — no extra config needed.
_PREFIX_MODELS: dict[str, dict[str, str]] = {
    "e5": {"query": "query: ", "passage": "passage: "},
    "bge": {"query": "Represent this sentence: ", "passage": ""},
}


class Embedder:
    """Wraps a sentence-transformers model for text embedding.

    Automatically applies instruction prefixes for E5 and BGE model families.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None
        self._prefixes = self._detect_prefixes(self.model_name)

    @staticmethod
    def _detect_prefixes(model_name: str) -> dict[str, str]:
        """Detect if model requires query/passage prefixes based on name."""
        name_lower = model_name.lower()
        for family, prefixes in _PREFIX_MODELS.items():
            if family in name_lower:
                return prefixes
        return {"query": "", "passage": ""}

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (with query prefix if needed)."""
        prefixed = self._prefixes["query"] + text
        return self.model.encode(prefixed, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts (with passage prefix if needed)."""
        prefixed = [self._prefixes["passage"] + t for t in texts]
        embeddings = self.model.encode(
            prefixed, normalize_embeddings=True, show_progress_bar=True
        )
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()
