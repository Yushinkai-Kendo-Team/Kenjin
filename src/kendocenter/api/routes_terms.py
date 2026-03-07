"""Glossary terms API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from kendocenter.storage.database import Database

router = APIRouter()
_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


@router.get("/api/terms")
def list_terms(
    query: str = "",
    category: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List or search glossary terms."""
    db = get_db()
    terms = db.search_terms(query=query, category=category, limit=limit, offset=offset)
    total = db.count_terms()
    categories = db.get_categories()

    return {
        "items": terms,
        "total": total,
        "categories": categories,
    }


@router.get("/api/terms/{term_romaji}")
def get_term(term_romaji: str) -> dict:
    """Get a specific glossary term."""
    db = get_db()
    term = db.lookup_term(term_romaji)
    if not term:
        return {"error": "Term not found", "term": term_romaji}
    return term


@router.get("/api/health")
def health_check() -> dict:
    """System health check."""
    db = get_db()
    from kendocenter.storage.vector_store import VectorStore

    vs = VectorStore()
    return {
        "status": "healthy",
        "glossary_terms": db.count_terms(),
        "documents": db.count_documents(),
        "sources": db.count_sources(),
        "source_categories": db.get_source_stats(),
        "vector_store_entries": vs.count,
    }
