"""Cross-encoder re-ranker for two-stage retrieval (Phase 2A).

Retrieves more candidates from ChromaDB, then re-ranks with a cross-encoder
for higher precision in the final top-k results.
"""

from __future__ import annotations

from kendocenter.config import settings
from kendocenter.storage.models import SearchResult


class Reranker:
    """Cross-encoder re-ranker using sentence-transformers."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.reranker_model
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int | None = None,
    ) -> list[SearchResult]:
        """Re-rank search results using cross-encoder scores.

        Args:
            query: Original query text.
            results: Results from initial vector search.
            top_n: Return top N after re-ranking (default: settings.retrieval_top_k).

        Returns:
            Re-ranked list of SearchResult, sorted by cross-encoder score (descending).
        """
        if not results:
            return results

        top_n = top_n or settings.retrieval_top_k
        pairs = [[query, r.text] for r in results]
        scores = self.model.predict(pairs)

        scored = list(zip(results, scores))
        scored.sort(key=lambda x: float(x[1]), reverse=True)

        reranked = []
        for result, score in scored[:top_n]:
            result.rerank_score = float(score)
            reranked.append(result)
        return reranked
