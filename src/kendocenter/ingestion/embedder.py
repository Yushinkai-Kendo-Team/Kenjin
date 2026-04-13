"""Embedding model wrapper using sentence-transformers.

Phase 2A: Automatic instruction prefix detection for E5/BGE model families.
Models like intfloat/multilingual-e5-* require "query: " and "passage: " prefixes.

Phase 2B+: Embedding cache support for fast re-ingestion. Embeddings are cached
to disk keyed by (model_name, text_hash). When chunks haven't changed, embeddings
are loaded from cache instead of recomputed (~100x faster).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from kendocenter.config import settings

# Model families that require query/passage instruction prefixes.
# Detected automatically from model name — no extra config needed.
# Order matters: more specific keys are checked first.
_PREFIX_MODELS: list[tuple[str, dict[str, str]]] = [
    ("bge-m3", {"query": "", "passage": ""}),  # bge-m3 needs no prefix for dense
    ("e5", {"query": "query: ", "passage": "passage: "}),
    ("bge", {"query": "Represent this sentence: ", "passage": ""}),
]


class Embedder:
    """Wraps a sentence-transformers model for text embedding.

    Automatically applies instruction prefixes for E5 and BGE model families.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None
        self._prefixes = self._detect_prefixes(self.model_name)

    @staticmethod
    def _detect_prefixes(model_name: str) -> dict[str, str]:
        """Detect if model requires query/passage prefixes based on name."""
        name_lower = model_name.lower()
        for family, prefixes in _PREFIX_MODELS:
            if family in name_lower:
                return prefixes
        return {"query": "", "passage": ""}

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (with query prefix if needed)."""
        prefixed = self._prefixes["query"] + text
        return self.model.encode(prefixed, normalize_embeddings=True).tolist()

    def embed_documents(
        self, texts: list[str], use_cache: bool = True,
    ) -> list[list[float]]:
        """Embed a batch of document texts (with passage prefix if needed).

        When use_cache=True, checks a disk cache keyed by (model, text_hash).
        Only uncached texts are sent through the model, then results are merged.
        """
        cache_dir = Path(settings.chroma_persist_dir).parent / "embedding_cache"
        cache_file = cache_dir / f"{self.model_name.replace('/', '_')}.npz"

        # Load existing cache
        cache: dict[str, np.ndarray] = {}
        if use_cache and cache_file.exists():
            try:
                data = np.load(str(cache_file), allow_pickle=True)
                cache = dict(data["cache"].item())
            except Exception:
                cache = {}

        # Compute hashes and find uncached
        hashes = [hashlib.md5(t.encode()).hexdigest() for t in texts]
        uncached_indices = [i for i, h in enumerate(hashes) if h not in cache]

        if uncached_indices:
            uncached_texts = [
                self._prefixes["passage"] + texts[i] for i in uncached_indices
            ]
            print(f"       Embedding {len(uncached_texts)} new chunks "
                  f"({len(texts) - len(uncached_texts)} cached)...")
            new_embeddings = self.model.encode(
                uncached_texts, normalize_embeddings=True, show_progress_bar=True,
                batch_size=16,
            )
            # Store in cache
            for idx, emb in zip(uncached_indices, new_embeddings):
                cache[hashes[idx]] = emb

            # Save updated cache
            if use_cache:
                cache_dir.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(str(cache_file), cache=cache)
                print(f"       Cache updated: {len(cache)} embeddings "
                      f"({cache_file.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            print(f"       All {len(texts)} chunks cached — skipping embedding")

        # Assemble results in order
        return [cache[h].tolist() for h in hashes]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()
