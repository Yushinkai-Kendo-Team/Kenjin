"""Orchestrates the full ingestion pipeline: parse -> chunk -> embed -> store.

Phase 1.5: Walks Theory/ subdirectories, reads metadata.yaml, registers sources,
and uses compact source_key references in chunk metadata.
"""

from __future__ import annotations

import json
from pathlib import Path

from kendocenter.config import settings
from kendocenter.ingestion.metadata_loader import discover_sources
from kendocenter.ingestion.pdf_parser import parse_glossary
from kendocenter.ingestion.docx_parser import parse_docx
from kendocenter.ingestion.chunker import chunk_glossary, chunk_article
from kendocenter.ingestion.embedder import Embedder
from kendocenter.storage.vector_store import VectorStore
from kendocenter.storage.database import Database
from kendocenter.storage.models import DocumentChunk


def run_ingestion(
    theory_dir: str | Path | None = None,
    reset: bool = False,
) -> dict:
    """Run the full ingestion pipeline.

    Args:
        theory_dir: Directory containing source documents.
        reset: If True, wipe existing data before ingesting.

    Returns:
        Statistics dict with counts.
    """
    theory_dir = Path(theory_dir or settings.kendo_theory_dir)
    stats = {
        "glossary_entries": 0,
        "articles": 0,
        "glossary_chunks": 0,
        "article_chunks": 0,
        "total_chunks": 0,
        "sources_registered": 0,
    }

    print("=== YSK Kenjin Ingestion Pipeline ===")
    print(f"Source directory: {theory_dir}")
    print()

    # Initialize stores
    db = Database()
    db.initialize()
    vector_store = VectorStore()

    if reset:
        print("Resetting existing data...")
        vector_store.reset()
        db.reset()

    # Step 1: Discover sources from metadata.yaml files
    print("[1/6] Discovering sources from metadata.yaml files...")
    file_sources = discover_sources(theory_dir)
    print(f"       Found {len(file_sources)} source files")
    for src in file_sources:
        print(f"       - [{src.category}] {src.filename}")

    # Step 2: Register sources and process files
    print(f"\n[2/6] Registering sources and parsing files...")
    all_chunks: list[DocumentChunk] = []

    for file_meta in file_sources:
        # Register source in DB and get short key
        source_key = db.register_source(
            filename=file_meta.filename,
            file_path=file_meta.file_path,
            category=file_meta.category,
            doc_type=file_meta.doc_type,
            title=file_meta.title,
            subject=file_meta.subject,
            publication=file_meta.publication,
            date=file_meta.date,
            tags=json.dumps(file_meta.tags),
        )
        stats["sources_registered"] += 1
        print(f"       [{source_key}] {file_meta.filename}")

        # Parse and chunk based on doc_type
        if file_meta.doc_type == "glossary" and file_meta.filename.endswith(".pdf"):
            entries = parse_glossary(file_meta.file_path)
            stats["glossary_entries"] = len(entries)
            print(f"              Parsed {len(entries)} glossary entries")

            # Insert glossary entries into SQLite
            count = db.insert_glossary_entries(entries)
            print(f"              Inserted {count} entries into database")

            # Insert document record
            db.insert_document(
                filename=file_meta.filename,
                title=file_meta.title or "Glossary of Terms in Kendo",
                source_publication=file_meta.publication or file_meta.author,
                doc_type="glossary",
            )

            # Chunk glossary entries with source_key
            glossary_chunks = chunk_glossary(entries, source_key=source_key)
            stats["glossary_chunks"] = len(glossary_chunks)
            all_chunks.extend(glossary_chunks)
            print(f"              {len(glossary_chunks)} chunks")

        elif file_meta.filename.endswith(".docx"):
            article = parse_docx(file_meta.file_path)

            # Override metadata from metadata.yaml (more accurate than parsed)
            if file_meta.title:
                article.title = file_meta.title
            if file_meta.subject:
                article.subject_name = file_meta.subject
            if file_meta.publication:
                article.source_publication = file_meta.publication
            if file_meta.date:
                article.date = file_meta.date
            if file_meta.translator:
                article.translator = file_meta.translator

            stats["articles"] += 1
            print(f"              {len(article.english_paragraphs)} EN, "
                  f"{len(article.vietnamese_paragraphs)} VN paragraphs")

            db.insert_document(
                filename=article.filename,
                title=article.title,
                subject_name=article.subject_name,
                source_publication=article.source_publication,
                date=article.date,
                translator=article.translator,
                doc_type="article",
                english_paragraphs=len(article.english_paragraphs),
                vietnamese_paragraphs=len(article.vietnamese_paragraphs),
            )

            # Chunk article with source_key and configurable params
            article_chunks = chunk_article(
                article,
                max_chunk_tokens=settings.chunking_max_tokens,
                overlap_tokens=settings.chunking_overlap_tokens,
                source_key=source_key,
                prepend_title=settings.chunking_prepend_title,
            )
            stats["article_chunks"] += len(article_chunks)
            all_chunks.extend(article_chunks)
            print(f"              {len(article_chunks)} chunks")

            # Record chunks in SQLite
            db.insert_chunks(
                document_filename=article.filename,
                chunks=[
                    {
                        "chunk_index": c.metadata.get("idx", 0),
                        "text": c.text,
                        "chroma_id": c.id,
                        "language": c.metadata.get("lang", "en"),
                        "metadata": c.metadata,
                    }
                    for c in article_chunks
                ],
            )

    stats["total_chunks"] = len(all_chunks)

    # Step 3: Embed all chunks
    print(f"\n[3/6] Embedding {len(all_chunks)} chunks...")
    embedder = Embedder()
    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed_documents(texts)
    print(f"       Embedding dimension: {len(embeddings[0])}")

    # Step 4: Store in ChromaDB
    print(f"\n[4/6] Storing in vector database...")
    vector_store.add_chunks(all_chunks, embeddings)
    print(f"       Total vectors in store: {vector_store.count}")

    # Step 5: Build FTS5 keyword index (Phase 2B)
    print(f"\n[5/6] Building keyword search index...")
    fts_count = db.populate_fts()
    print(f"       FTS5 indexed: {fts_count} chunks")

    # Step 6: Summary
    print(f"\n[6/6] Verifying...")
    print("\n=== Ingestion Complete ===")
    print(f"  Sources registered: {stats['sources_registered']}")
    print(f"  Glossary entries: {stats['glossary_entries']}")
    print(f"  Articles: {stats['articles']}")
    print(f"  Glossary chunks: {stats['glossary_chunks']}")
    print(f"  Article chunks: {stats['article_chunks']}")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Database terms: {db.count_terms()}")
    print(f"  Database documents: {db.count_documents()}")
    print(f"  Database sources: {db.count_sources()}")
    print(f"  Vector store entries: {vector_store.count}")

    db.close()
    return stats
