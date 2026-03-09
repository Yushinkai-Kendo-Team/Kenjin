"""Kendo-aware text chunking.

Glossary terms are kept as atomic chunks (never split).
Article text is chunked by paragraphs with overlap.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from kendocenter.ingestion.pdf_parser import GlossaryEntry
from kendocenter.ingestion.docx_parser import ArticleDocument
from kendocenter.storage.models import DocumentChunk


def _make_id(text: str, prefix: str = "") -> str:
    """Generate a deterministic ID from text content."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{h}" if prefix else h


def chunk_glossary_entry(
    entry: GlossaryEntry, source_key: str = "",
) -> DocumentChunk:
    """Convert a glossary entry into a single chunk.

    Each glossary term is an atomic unit -- never split.
    Uses compact metadata with source_key reference.
    """
    text = entry.to_chunk_text()
    return DocumentChunk(
        id=_make_id(text, "gloss"),
        text=text,
        metadata={
            "src": source_key or entry.source,
            "type": "glossary_term",
            "term": entry.term_romaji,
            "kanji": entry.term_kanji,
            "category": entry.category,
            "lang": "en",
        },
    )


def chunk_glossary(
    entries: list[GlossaryEntry], source_key: str = "",
) -> list[DocumentChunk]:
    """Convert all glossary entries into chunks."""
    return [chunk_glossary_entry(e, source_key=source_key) for e in entries]


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate (1 token ~ 4 chars for English)."""
    return len(text) // 4


def chunk_article_paragraphs(
    paragraphs: list[str],
    article: ArticleDocument,
    language: str = "en",
    max_chunk_tokens: int = 800,
    overlap_tokens: int = 100,
    source_key: str = "",
    title: str = "",
) -> list[DocumentChunk]:
    """Chunk article paragraphs with overlap, respecting paragraph boundaries.

    Rules:
    - Never split mid-paragraph
    - Target ~800 tokens per chunk
    - ~100 token overlap for continuity
    - Each chunk gets compact metadata with source_key reference
    - Optional title prefix for better topic association
    """
    if not paragraphs:
        return []

    title_prefix = f"Title: {title}\n\n" if title else ""

    chunks: list[DocumentChunk] = []
    current_paras: list[str] = []
    current_tokens = 0
    chunk_index = 0

    def _save_chunk():
        nonlocal chunk_index
        if not current_paras:
            return
        text = title_prefix + "\n\n".join(current_paras)
        chunk = DocumentChunk(
            id=_make_id(text, f"art_{language}"),
            text=text,
            metadata={
                "src": source_key or article.filename,
                "type": f"article_{language}",
                "lang": language,
                "idx": chunk_index,
            },
        )
        chunks.append(chunk)
        chunk_index += 1

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        # If adding this paragraph exceeds the limit, save current and start new
        if current_tokens + para_tokens > max_chunk_tokens and current_paras:
            _save_chunk()

            # Overlap: keep last paragraph(s) up to overlap_tokens
            overlap_paras: list[str] = []
            overlap_count = 0
            for p in reversed(current_paras):
                p_tokens = _estimate_tokens(p)
                if overlap_count + p_tokens > overlap_tokens:
                    break
                overlap_paras.insert(0, p)
                overlap_count += p_tokens

            current_paras = overlap_paras
            current_tokens = overlap_count

        current_paras.append(para)
        current_tokens += para_tokens

    # Save final chunk
    _save_chunk()

    return chunks


def chunk_article(
    article: ArticleDocument,
    max_chunk_tokens: int = 800,
    overlap_tokens: int = 100,
    source_key: str = "",
    prepend_title: bool = False,
) -> list[DocumentChunk]:
    """Chunk an article's English and Vietnamese content."""
    title = article.title if prepend_title else ""
    chunks = []

    # English chunks
    en_chunks = chunk_article_paragraphs(
        article.english_paragraphs,
        article,
        language="en",
        max_chunk_tokens=max_chunk_tokens,
        overlap_tokens=overlap_tokens,
        source_key=source_key,
        title=title,
    )
    chunks.extend(en_chunks)

    # Vietnamese chunks
    vn_chunks = chunk_article_paragraphs(
        article.vietnamese_paragraphs,
        article,
        language="vn",
        max_chunk_tokens=max_chunk_tokens,
        overlap_tokens=overlap_tokens,
        source_key=source_key,
        title=title,
    )
    chunks.extend(vn_chunks)

    return chunks
