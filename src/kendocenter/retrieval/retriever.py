"""Retrieval logic: query -> relevant chunks from vector store + database.

Phase 1.5: Resolves compact source_key metadata back to full source info
via a cached lookup from the sources table.

Phase 2A: Optional cross-encoder re-ranking for two-stage retrieval.
"""

from __future__ import annotations

import re
from typing import Any

from kendocenter.config import settings
from kendocenter.ingestion.embedder import Embedder
from kendocenter.storage.vector_store import VectorStore
from kendocenter.storage.database import Database
from kendocenter.storage.models import SearchResult
from kendocenter.retrieval.reranker import Reranker

_QUESTION_PREFIXES = re.compile(
    r"^(?:what\s+is|define|explain|tell\s+me\s+about|"
    r"what\s+does|what\s+are|meaning\s+of)\s+",
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
        """Try exact glossary match in SQLite.

        First tries the raw query, then extracts potential terms from questions.
        """
        result = self.database.lookup_term(query)
        if result:
            return result

        extracted = self._extract_term(query)
        if extracted:
            return self.database.lookup_term(extracted)

        return None

    def semantic_search(
        self,
        query: str,
        n_results: int | None = None,
        language: str | None = None,
    ) -> list[SearchResult]:
        """Semantic search in ChromaDB.

        Args:
            query: The search query text.
            n_results: Max results (default from settings).
            language: Filter by language ("en" or "vn").

        Returns:
            Ranked list of SearchResult with resolved metadata.
        """
        n_results = n_results or settings.retrieval_top_k

        # Two-stage retrieval: fetch more candidates when re-ranking is enabled
        fetch_k = n_results
        if self.reranker is not None:
            fetch_k = max(n_results, settings.reranker_candidate_count)

        query_embedding = self.embedder.embed_query(query)

        where = None
        if language:
            where = {"lang": language}

        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=fetch_k,
            where=where,
        )

        # Resolve compact metadata and filter by similarity threshold
        # When re-ranking, use a relaxed threshold so the cross-encoder
        # sees more candidates — it can rescue borderline results that
        # cosine distance would discard.
        threshold = settings.similarity_threshold
        if self.reranker is not None:
            threshold = min(threshold * 2, 1.4)
        resolved = []
        for r in results:
            if r.distance <= threshold:
                r.metadata = self._resolve_metadata(r.metadata)
                resolved.append(r)

        # Re-rank if enabled (graceful fallback on failure)
        if self.reranker is not None and resolved:
            try:
                resolved = self.reranker.rerank(query, resolved, top_n=n_results)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Re-ranking failed, using vector search order: %s", e)

        return resolved[:n_results]

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
