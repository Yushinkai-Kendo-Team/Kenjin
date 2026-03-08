"""Application configuration."""

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
    similarity_threshold: float = 0.7

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


settings = Settings()
