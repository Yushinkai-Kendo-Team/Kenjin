"""Retrieval logic: query -> relevant chunks from vector store + database.

Phase 1.5: Resolves compact source_key metadata back to full source info
via a cached lookup from the sources table.

Phase 2A: Optional cross-encoder re-ranking for two-stage retrieval.
Phase 2B: Hybrid search (BM25 + vector), fuzzy glossary matching.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from kendocenter.config import settings
from kendocenter.ingestion.embedder import Embedder
from kendocenter.storage.vector_store import VectorStore
from kendocenter.storage.database import Database
from kendocenter.storage.models import SearchResult
from kendocenter.retrieval.reranker import Reranker
from kendocenter.retrieval.hybrid import HybridSearcher

logger = logging.getLogger(__name__)

_QUESTION_PREFIXES = re.compile(
    # Longer patterns first to avoid partial matches (e.g. "what is the meaning of"
    # must match before "what is").
    r"^(?:what\s+is\s+the\s+meaning\s+of|what\s+is\s+the|"
    r"can\s+you\s+explain|tell\s+me\s+about|how\s+do\s+you|"
    r"what\s+does|what\s+are|what\s+is|who\s+is|how\s+is|"
    r"meaning\s+of|what\s+about|how\s+to|"
    r"define|explain|describe)\s+",
    re.IGNORECASE,
)


class Retriever:
    """Combines exact glossary lookup with semantic vector search.

    Resolves compact source_key references in chunk metadata back to
    full source info (filename, title, subject, file_path, etc.).
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        database: Database | None = None,
        reranker: Reranker | None = None,
    ):
        self.embedder = embedder or Embedder()
        self.vector_store = vector_store or VectorStore()
        self.database = database or Database()
        self._source_cache: dict[str, dict] | None = None
        self.reranker = reranker
        if self.reranker is None and settings.reranker_enabled:
            self.reranker = Reranker()
        self._hybrid: HybridSearcher | None = None

    @property
    def source_cache(self) -> dict[str, dict]:
        """Lazy-loaded cache of all sources keyed by source_key."""
        if self._source_cache is None:
            self._source_cache = self.database.get_all_sources()
        return self._source_cache

    def _resolve_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Expand compact chunk metadata using source_cache.

        Compact format: {"src": "A1", "type": "article_en", "lang": "en", "idx": 3}
        Resolved format adds: source, title, subject, publication, file_path, language, chunk_index
        """
        resolved = dict(metadata)
        src_key = metadata.get("src", "")
        source_info = self.source_cache.get(src_key)

        if source_info:
            resolved["source"] = source_info["filename"]
            resolved["title"] = source_info.get("title", "")
            resolved["subject"] = source_info.get("subject", "")
            resolved["publication"] = source_info.get("publication", "")
            resolved["file_path"] = source_info.get("file_path", "")
            resolved["category"] = source_info.get("category", "")
            resolved["source_key"] = src_key
        else:
            # Fallback: src might already be a filename (pre-1.5 data)
            resolved["source"] = src_key

        # Normalize compact keys to full names for downstream consumers
        if "lang" in resolved:
            resolved["language"] = resolved["lang"]
        if "idx" in resolved:
            resolved["chunk_index"] = resolved["idx"]

        return resolved

    def _extract_term(self, query: str) -> str | None:
        """Extract a potential kendo term from a natural-language question."""
        stripped = _QUESTION_PREFIXES.sub("", query)
        stripped = stripped.strip(" ?.,!")
        if stripped and stripped.lower() != query.strip().lower():
            return stripped
        return None

    def lookup_term(self, query: str) -> dict | None:
        """Try glossary match in SQLite.

        Chain: raw exact → extracted exact → fuzzy (Phase 2B).
        """
        result = self.database.lookup_term(query)
        if result:
            return result

        extracted = self._extract_term(query)
        if extracted:
            result = self.database.lookup_term(extracted)
            if result:
                return result

        # Fuzzy fallback (Phase 2B)
        if settings.fuzzy_enabled:
            term_to_match = extracted or query
            return self.database.fuzzy_lookup_term(
                term_to_match, threshold=settings.fuzzy_threshold
            )

        return None

    def semantic_search(
        self,
        query: str,
        n_results: int | None = None,
        language: str | None = None,
    ) -> list[SearchResult]:
        """Search for relevant chunks.

        Uses hybrid search (BM25 + vector) when enabled, otherwise pure vector.
        Results are optionally re-ranked by cross-encoder.

        Args:
            query: The search query text.
            n_results: Max results (default from settings).
            language: Filter by language ("en" or "vn").

        Returns:
            Ranked list of SearchResult with resolved metadata.
        """
        n_results = n_results or settings.retrieval_top_k

        # Candidate pool size: larger when re-ranking or hybrid
        fetch_k = n_results
        if self.reranker is not None:
            fetch_k = max(n_results, settings.reranker_candidate_count)

        # Hybrid search (Phase 2B): BM25 + vector merged via RRF
        if settings.hybrid_enabled:
            resolved = self._hybrid_search(query, fetch_k, language)
        else:
            resolved = self._vector_search(query, fetch_k, language)

        # Resolve metadata for all results
        for r in resolved:
            if "source" not in r.metadata:
                r.metadata = self._resolve_metadata(r.metadata)

        # Re-rank if enabled (graceful fallback on failure)
        if self.reranker is not None and resolved:
            try:
                resolved = self.reranker.rerank(query, resolved, top_n=n_results)
            except Exception as e:
                logger.warning("Re-ranking failed, using search order: %s", e)

        return resolved[:n_results]

    def _vector_search(
        self,
        query: str,
        fetch_k: int,
        language: str | None,
    ) -> list[SearchResult]:
        """Pure vector search in ChromaDB with threshold filtering."""
        query_embedding = self.embedder.embed_query(query)

        where = None
        if language:
            where = {"lang": language}

        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=fetch_k,
            where=where,
        )

        # When re-ranking, use a relaxed threshold so the cross-encoder
        # sees more candidates.
        threshold = settings.similarity_threshold
        if self.reranker is not None:
            threshold = settings.reranker_threshold

        return [r for r in results if r.distance <= threshold]

    def _hybrid_search(
        self,
        query: str,
        fetch_k: int,
        language: str | None,
    ) -> list[SearchResult]:
        """Hybrid search: BM25 keyword + vector, merged via RRF."""
        if self._hybrid is None:
            self._hybrid = HybridSearcher(
                embedder=self.embedder,
                vector_store=self.vector_store,
                database=self.database,
                source_cache=self.source_cache,
            )
        return self._hybrid.search(
            query, n_results=fetch_k, language=language, fetch_k=fetch_k,
        )

    def retrieve(
        self,
        query: str,
        n_results: int | None = None,
        language: str | None = None,
    ) -> tuple[dict | None, list[SearchResult]]:
        """Full retrieval: exact match + semantic search.

        Returns:
            Tuple of (glossary_match_or_None, search_results).
        """
        glossary_match = self.lookup_term(query)
        search_results = self.semantic_search(
            query, n_results=n_results, language=language
        )
        return glossary_match, search_results
