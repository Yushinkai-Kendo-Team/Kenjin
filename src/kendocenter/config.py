"""Application configuration."""

import json
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """YSK Kenjin settings loaded from .env file."""

    # Paths
    kendo_theory_dir: str = ""
    chroma_persist_dir: str = "data/chroma"
    sqlite_db_path: str = "data/kendocenter.db"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    retrieval_top_k: int = 8
    similarity_threshold: float = 0.7  # cosine distance (0=identical, 2=opposite); lower=stricter

    # Re-ranking (Phase 2A)
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_candidate_count: int = 20
    reranker_threshold: float = 1.4  # relaxed threshold when re-ranking (wider candidate net)

    # Chunking (Phase 2A)
    chunking_max_tokens: int = 800
    chunking_overlap_tokens: int = 100
    chunking_prepend_title: bool = False

    # Evaluation (Phase 2A)
    eval_dataset_path: str = "data/eval/eval_dataset.yaml"

    # Hybrid search (Phase 2B)
    hybrid_enabled: bool = False
    hybrid_rrf_k: int = 60  # RRF constant (standard value)
    hybrid_vector_weight: float = 1.0
    hybrid_keyword_weight: float = 1.0
    source_quality_weights: str = '{"glossary": 1.5, "articles": 1.2}'

    # Fuzzy glossary (Phase 2B)
    fuzzy_enabled: bool = False
    fuzzy_threshold: float = 70.0  # rapidfuzz score 0-100

    # Optional: Claude API (for future use)
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def theory_path(self) -> Path:
        return Path(self.kendo_theory_dir)

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_persist_dir)

    @property
    def db_path(self) -> Path:
        return Path(self.sqlite_db_path)

    @property
    def parsed_source_quality_weights(self) -> dict[str, float]:
        """Parse source_quality_weights JSON string."""
        return json.loads(self.source_quality_weights)


settings = Settings()
