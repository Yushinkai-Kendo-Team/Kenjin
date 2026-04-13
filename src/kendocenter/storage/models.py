"""Data models used across the application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Source:
    """A registered source file in the knowledge base."""

    source_key: str  # short key: "G1", "A1", "A2"
    filename: str
    file_path: str
    category: str
    doc_type: str
    title: str = ""
    subject: str = ""
    publication: str = ""
    date: str = ""
    tags: str = ""  # JSON array


@dataclass
class DocumentChunk:
    """A chunk of text ready for embedding and storage."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    # Compact metadata keys (Phase 1.5):
    # - src: source_key (resolve via sources table)
    # - type: "glossary_term" | "article_en" | "article_vn"
    # - lang: "en" | "vn"
    # - idx: chunk_index (for articles)
    # - term: romaji term (for glossary)
    # - kanji: Japanese characters (for glossary)


@dataclass
class SearchResult:
    """A single result from a retrieval query."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    distance: float  # lower = more similar
    rerank_score: float | None = None  # cross-encoder score (higher = better)
    rrf_score: float | None = None  # hybrid RRF fusion score (higher = better)

    @property
    def source(self) -> str:
        return self.metadata.get("source", "unknown")

    @property
    def chunk_type(self) -> str:
        return self.metadata.get("type", "unknown")


@dataclass
class RetrievalResult:
    """Complete result from the retrieval pipeline."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    glossary_match: dict[str, Any] | None = None
    formatted_prompt: str = ""
    ai_answer: str = ""

    @property
    def has_results(self) -> bool:
        return bool(self.results) or self.glossary_match is not None
