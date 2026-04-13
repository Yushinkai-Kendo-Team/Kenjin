"""SQLite database for structured kendo data (glossary terms, documents).

Phase 2B: FTS5 full-text search index for BM25 keyword search,
fuzzy glossary matching via rapidfuzz.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from kendocenter.config import settings
from kendocenter.ingestion.pdf_parser import GlossaryEntry

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS glossary_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_romaji TEXT NOT NULL,
    term_kanji TEXT DEFAULT '',
    definition TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    source_document TEXT DEFAULT 'Glossary.pdf',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    title TEXT DEFAULT '',
    subject_name TEXT DEFAULT '',
    source_publication TEXT DEFAULT '',
    date TEXT DEFAULT '',
    translator TEXT DEFAULT '',
    doc_type TEXT DEFAULT 'article',
    english_paragraphs INTEGER DEFAULT 0,
    vietnamese_paragraphs INTEGER DEFAULT 0,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_filename TEXT,
    chunk_index INTEGER,
    chunk_text TEXT NOT NULL,
    chroma_id TEXT,
    language TEXT DEFAULT 'en',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    category TEXT NOT NULL,
    doc_type TEXT DEFAULT 'article',
    title TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    publication TEXT DEFAULT '',
    date TEXT DEFAULT '',
    tags TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_glossary_romaji ON glossary_terms(term_romaji);
CREATE INDEX IF NOT EXISTS idx_glossary_category ON glossary_terms(category);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_chunks_filename ON document_chunks(document_filename);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_key ON sources(source_key);
"""

# Prefix map for generating source_keys by doc_type
_KEY_PREFIX = {
    "glossary": "G",
    "article": "A",
    "kata": "K",
    "grading": "R",
    "video": "V",
}


class Database:
    """SQLite database for structured kendo knowledge."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or settings.db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def initialize(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def reset(self) -> None:
        """Drop all tables and recreate them."""
        self.conn.executescript("""
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS glossary_terms;
            DROP TABLE IF EXISTS documents;
            DROP TABLE IF EXISTS document_chunks;
            DROP TABLE IF EXISTS sources;
        """)
        self.conn.commit()
        self._term_cache = None
        self.initialize()

    def insert_glossary_entries(self, entries: list[GlossaryEntry]) -> int:
        """Insert glossary entries, replacing existing ones from the same source."""
        if not entries:
            return 0
        # Clear existing entries from same source to avoid duplicates
        source = entries[0].source if entries else "Glossary.pdf"
        self.conn.execute(
            "DELETE FROM glossary_terms WHERE source_document = ?", (source,)
        )
        count = 0
        for entry in entries:
            self.conn.execute(
                """INSERT INTO glossary_terms
                   (term_romaji, term_kanji, definition, category, source_document)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    entry.term_romaji,
                    entry.term_kanji,
                    entry.definition,
                    entry.category,
                    entry.source,
                ),
            )
            count += 1
        self.conn.commit()
        return count

    def insert_document(
        self,
        filename: str,
        title: str = "",
        subject_name: str = "",
        source_publication: str = "",
        date: str = "",
        translator: str = "",
        doc_type: str = "article",
        english_paragraphs: int = 0,
        vietnamese_paragraphs: int = 0,
    ) -> None:
        """Insert or update a document record."""
        self.conn.execute(
            """INSERT OR REPLACE INTO documents
               (filename, title, subject_name, source_publication, date,
                translator, doc_type, english_paragraphs, vietnamese_paragraphs)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                filename,
                title,
                subject_name,
                source_publication,
                date,
                translator,
                doc_type,
                english_paragraphs,
                vietnamese_paragraphs,
            ),
        )
        self.conn.commit()

    def insert_chunks(
        self,
        document_filename: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        """Insert chunk records for a document, replacing existing ones."""
        # Remove old chunks for this document first to avoid duplicates
        self.conn.execute(
            "DELETE FROM document_chunks WHERE document_filename = ?",
            (document_filename,),
        )
        for chunk in chunks:
            self.conn.execute(
                """INSERT INTO document_chunks
                   (document_filename, chunk_index, chunk_text, chroma_id, language, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    document_filename,
                    chunk.get("chunk_index", 0),
                    chunk["text"],
                    chunk.get("chroma_id", ""),
                    chunk.get("language", "en"),
                    json.dumps(chunk.get("metadata", {})),
                ),
            )
        self.conn.commit()

    def lookup_term(self, query: str) -> dict | None:
        """Look up a glossary term by exact or partial match.

        Tries exact match first, then case-insensitive, then partial.
        """
        # Exact match
        row = self.conn.execute(
            "SELECT * FROM glossary_terms WHERE term_romaji = ?", (query,)
        ).fetchone()
        if row:
            return dict(row)

        # Case-insensitive match
        row = self.conn.execute(
            "SELECT * FROM glossary_terms WHERE LOWER(term_romaji) = LOWER(?)",
            (query,),
        ).fetchone()
        if row:
            return dict(row)

        # Partial match (term contains query)
        row = self.conn.execute(
            "SELECT * FROM glossary_terms WHERE LOWER(term_romaji) LIKE LOWER(?)",
            (f"%{query}%",),
        ).fetchone()
        if row:
            return dict(row)

        return None

    def search_terms(
        self,
        query: str = "",
        category: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Search glossary terms with optional filters."""
        conditions = []
        params: list[Any] = []

        if query:
            conditions.append(
                "(LOWER(term_romaji) LIKE LOWER(?) OR LOWER(definition) LIKE LOWER(?))"
            )
            params.extend([f"%{query}%", f"%{query}%"])

        if category:
            conditions.append("category = ?")
            params.append(category)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        rows = self.conn.execute(
            f"SELECT * FROM glossary_terms {where} ORDER BY term_romaji LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        return [dict(r) for r in rows]

    def count_terms(self) -> int:
        """Count total glossary terms."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM glossary_terms").fetchone()
        return row["cnt"] if row else 0

    def count_documents(self) -> int:
        """Count total documents."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"] if row else 0

    def get_categories(self) -> list[dict]:
        """Get categories with counts."""
        rows = self.conn.execute(
            """SELECT category, COUNT(*) as count
               FROM glossary_terms
               GROUP BY category
               ORDER BY count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Source registry methods (Phase 1.5) ---

    def register_source(
        self,
        filename: str,
        file_path: str,
        category: str,
        doc_type: str = "article",
        title: str = "",
        subject: str = "",
        publication: str = "",
        date: str = "",
        tags: str = "[]",
    ) -> str:
        """Register a source file and return its short source_key.

        Key format: prefix + sequential number (e.g., G1, A1, A2).
        If the filename is already registered, returns the existing key.
        """
        # Check if already registered
        row = self.conn.execute(
            "SELECT source_key FROM sources WHERE filename = ?", (filename,)
        ).fetchone()
        if row:
            return row["source_key"]

        # Generate next key for this doc_type
        prefix = _KEY_PREFIX.get(doc_type, "X")
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM sources WHERE source_key LIKE ?",
            (f"{prefix}%",),
        ).fetchone()
        next_num = (row["cnt"] if row else 0) + 1
        source_key = f"{prefix}{next_num}"

        self.conn.execute(
            """INSERT INTO sources
               (source_key, filename, file_path, category, doc_type,
                title, subject, publication, date, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_key, filename, file_path, category, doc_type,
             title, subject, publication, date, tags),
        )
        self.conn.commit()
        return source_key

    def get_source(self, source_key: str) -> dict | None:
        """Look up a source by its short key."""
        row = self.conn.execute(
            "SELECT * FROM sources WHERE source_key = ?", (source_key,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_sources(self) -> dict[str, dict]:
        """Return all sources keyed by source_key. Used as a lookup cache."""
        rows = self.conn.execute("SELECT * FROM sources").fetchall()
        return {row["source_key"]: dict(row) for row in rows}

    def count_sources(self) -> int:
        """Count total registered sources."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM sources").fetchone()
        return row["cnt"] if row else 0

    def get_source_stats(self) -> list[dict]:
        """Get source counts grouped by category."""
        rows = self.conn.execute(
            """SELECT category, COUNT(*) as count
               FROM sources
               GROUP BY category
               ORDER BY count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    # --- FTS5 full-text search (Phase 2B) ---

    def populate_fts(self) -> int:
        """Rebuild FTS5 index from document_chunks table.

        Call after ingestion to make keyword search available.
        Returns the number of indexed rows.
        """
        self.conn.execute("DROP TABLE IF EXISTS chunks_fts")
        self.conn.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_text,
                source_key UNINDEXED,
                lang,
                chroma_id UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        # Index all document_chunks (articles, blogs)
        cursor = self.conn.execute("""
            SELECT dc.chunk_text, dc.chroma_id, dc.language,
                   json_extract(dc.metadata_json, '$.src') as source_key
            FROM document_chunks dc
            WHERE dc.chunk_text != ''
        """)
        count = 0
        for row in cursor:
            self.conn.execute(
                "INSERT INTO chunks_fts (chunk_text, source_key, lang, chroma_id) VALUES (?, ?, ?, ?)",
                (row["chunk_text"], row["source_key"] or "", row["language"], row["chroma_id"] or ""),
            )
            count += 1
        self.conn.commit()
        logger.info("FTS5 index populated with %d chunks", count)
        return count

    def keyword_search(
        self,
        query: str,
        n_results: int = 20,
        language: str | None = None,
    ) -> list[dict]:
        """BM25 keyword search using FTS5.

        Returns dicts with keys: chunk_text, source_key, lang, chroma_id, bm25_rank.
        Lower rank = better match (FTS5 rank is negative, more negative = better).
        """
        # Sanitize query for FTS5: remove special chars that break MATCH syntax
        safe_query = re.sub(r'[^\w\s]', ' ', query, flags=re.UNICODE).strip()
        if not safe_query:
            return []

        if language:
            rows = self.conn.execute(
                """SELECT chunk_text, source_key, lang, chroma_id, rank as bm25_rank
                   FROM chunks_fts
                   WHERE chunks_fts MATCH ? AND lang = ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, language, n_results),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT chunk_text, source_key, lang, chroma_id, rank as bm25_rank
                   FROM chunks_fts
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, n_results),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Fuzzy glossary matching (Phase 2B) ---

    _term_cache: list[tuple[str, int]] | None = None

    @staticmethod
    def _normalize_romaji(text: str) -> str:
        """Normalize romaji for fuzzy matching.

        Lowercases, strips macrons (ō→o, ū→u), removes hyphens/spaces.
        """
        text = text.lower()
        # Decompose unicode, strip combining marks (handles ō → o, etc.)
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        # Strip hyphens and spaces
        text = text.replace("-", "").replace(" ", "")
        return text

    def _get_term_cache(self) -> list[tuple[str, int]]:
        """Lazy-load all glossary terms for fuzzy matching."""
        if self._term_cache is None:
            rows = self.conn.execute(
                "SELECT id, term_romaji FROM glossary_terms"
            ).fetchall()
            self._term_cache = [(row["term_romaji"], row["id"]) for row in rows]
        return self._term_cache

    def fuzzy_lookup_term(self, query: str, threshold: float = 70.0) -> dict | None:
        """Fuzzy match a query against glossary terms using rapidfuzz.

        Tries normalized romaji first, then kanji matching for CJK queries.
        Returns the best match above the threshold, or None.
        """
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            logger.warning("rapidfuzz not installed, skipping fuzzy matching")
            return None

        terms = self._get_term_cache()
        if not terms:
            return None

        # Normalize query and all terms for comparison
        norm_query = self._normalize_romaji(query)
        choices = {i: self._normalize_romaji(term) for i, (term, _) in enumerate(terms)}

        result = process.extractOne(
            norm_query,
            choices,
            scorer=fuzz.ratio,
            score_cutoff=threshold,
        )

        if result:
            _, score, idx = result
            _, term_id = terms[idx]
            row = self.conn.execute(
                "SELECT * FROM glossary_terms WHERE id = ?", (term_id,)
            ).fetchone()
            if row:
                return dict(row)

        # For CJK queries, try matching against kanji column
        if any(ord(c) > 0x3000 for c in query):
            rows = self.conn.execute(
                "SELECT * FROM glossary_terms WHERE term_kanji = ?", (query,)
            ).fetchone()
            if rows:
                return dict(rows)

        return None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
