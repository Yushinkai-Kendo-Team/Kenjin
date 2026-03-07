"""Embedding model wrapper using sentence-transformers."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from kendocenter.config import settings


class Embedder:
    """Wraps a sentence-transformers model for text embedding."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts."""
        embeddings = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=True
        )
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()
