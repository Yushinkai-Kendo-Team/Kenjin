"""ChromaDB vector store for kendo knowledge chunks."""

from __future__ import annotations

from pathlib import Path

import chromadb

from kendocenter.config import settings
from kendocenter.storage.models import DocumentChunk, SearchResult


COLLECTION_NAME = "kendo_knowledge"


class VectorStore:
    """ChromaDB-backed vector store for semantic search."""

    def __init__(self, persist_dir: str | Path | None = None):
        self.persist_dir = str(persist_dir or settings.chroma_path)
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Add document chunks with pre-computed embeddings."""
        if not chunks:
            return

        # ChromaDB has a batch limit, process in batches
        batch_size = 500
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            self.collection.upsert(
                ids=[c.id for c in batch_chunks],
                embeddings=batch_embeddings,
                documents=[c.text for c in batch_chunks],
                metadatas=[c.metadata for c in batch_chunks],
            )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 8,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query_embedding: The query vector.
            n_results: Max number of results.
            where: Optional metadata filter (e.g., {"language": "en"}).

        Returns:
            List of SearchResult sorted by relevance.
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        search_results = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                search_results.append(
                    SearchResult(
                        chunk_id=meta.get("term", ""),
                        text=doc,
                        metadata=meta,
                        distance=dist,
                    )
                )

        return search_results

    @property
    def count(self) -> int:
        """Number of chunks in the collection."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # Collection may not exist yet
        self._collection = None
