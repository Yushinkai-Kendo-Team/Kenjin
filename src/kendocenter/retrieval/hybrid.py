"""Hybrid search: BM25 keyword + vector semantic, merged via Reciprocal Rank Fusion.

Phase 2B: Combines SQLite FTS5 keyword search with ChromaDB vector search.
RRF formula: score = w_vec/(k + rank_vec) + w_kw/(k + rank_kw)
Optional source quality weighting multiplies RRF scores by category weight.
"""

from __future__ import annotations

import logging
from typing import Any

from kendocenter.config import settings
from kendocenter.ingestion.embedder import Embedder
from kendocenter.storage.vector_store import VectorStore
from kendocenter.storage.database import Database
from kendocenter.storage.models import SearchResult

logger = logging.getLogger(__name__)


class HybridSearcher:
    """Combines vector and keyword search via Reciprocal Rank Fusion."""

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        database: Database,
        source_cache: dict[str, dict],
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.database = database
        self.source_cache = source_cache
        self._quality_weights: dict[str, float] | None = None

    @property
    def quality_weights(self) -> dict[str, float]:
        if self._quality_weights is None:
            self._quality_weights = settings.parsed_source_quality_weights
        return self._quality_weights

    def _get_quality_weight(self, source_key: str) -> float:
        """Get quality weight for a source by its key."""
        source_info = self.source_cache.get(source_key, {})
        category = source_info.get("category", "")
        return self.quality_weights.get(category, 1.0)

    def search(
        self,
        query: str,
        n_results: int = 8,
        language: str | None = None,
        fetch_k: int = 20,
    ) -> list[SearchResult]:
        """Hybrid search: vector + keyword, merged via RRF.

        Args:
            query: Search query text.
            n_results: Final number of results to return.
            language: Optional language filter ("en" or "vn").
            fetch_k: Number of candidates to fetch from each source.

        Returns:
            Ranked list of SearchResult with rrf_score set.
        """
        k = settings.hybrid_rrf_k
        w_vec = settings.hybrid_vector_weight
        w_kw = settings.hybrid_keyword_weight

        # 1. Vector search
        query_embedding = self.embedder.embed_query(query)
        where = {"lang": language} if language else None
        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=fetch_k,
            where=where,
        )

        # Build vector rank map: chunk_id -> (rank, SearchResult)
        vector_map: dict[str, tuple[int, SearchResult]] = {}
        for rank, r in enumerate(vector_results, 1):
            # Apply similarity threshold
            if r.distance <= settings.similarity_threshold:
                vector_map[r.chunk_id] = (rank, r)

        # 2. Keyword search (FTS5 BM25)
        try:
            keyword_results = self.database.keyword_search(
                query, n_results=fetch_k, language=language,
            )
        except Exception as e:
            logger.warning("Keyword search failed, using vector-only: %s", e)
            keyword_results = []

        # Build keyword rank map: chroma_id -> (rank, row_data)
        keyword_map: dict[str, tuple[int, dict]] = {}
        for rank, row in enumerate(keyword_results, 1):
            chroma_id = row.get("chroma_id", "")
            if chroma_id:
                keyword_map[chroma_id] = (rank, row)

        # 3. Merge via RRF
        all_ids = set(vector_map.keys()) | set(keyword_map.keys())
        scored: list[tuple[str, float, SearchResult | None, dict | None]] = []

        for chunk_id in all_ids:
            rrf_score = 0.0
            vec_entry = vector_map.get(chunk_id)
            kw_entry = keyword_map.get(chunk_id)

            if vec_entry:
                rrf_score += w_vec / (k + vec_entry[0])
            if kw_entry:
                rrf_score += w_kw / (k + kw_entry[0])

            # Apply source quality weight
            src_key = ""
            if vec_entry:
                src_key = vec_entry[1].metadata.get("src", "")
            elif kw_entry:
                src_key = kw_entry[1].get("source_key", "")
            rrf_score *= self._get_quality_weight(src_key)

            scored.append((chunk_id, rrf_score, vec_entry, kw_entry))

        # Sort by RRF score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # 4. Build final SearchResult list
        results: list[SearchResult] = []
        for chunk_id, rrf_score, vec_entry, kw_entry in scored[:n_results]:
            if vec_entry:
                # Use the vector search result (has distance, metadata)
                result = vec_entry[1]
                result.rrf_score = rrf_score
            elif kw_entry:
                # Keyword-only result — create SearchResult from FTS5 data
                result = SearchResult(
                    chunk_id=chunk_id,
                    text=kw_entry[1].get("chunk_text", ""),
                    metadata={
                        "src": kw_entry[1].get("source_key", ""),
                        "lang": kw_entry[1].get("lang", "en"),
                    },
                    distance=1.0,  # placeholder — no vector distance available
                    rrf_score=rrf_score,
                )
            else:
                continue
            results.append(result)

        return results
