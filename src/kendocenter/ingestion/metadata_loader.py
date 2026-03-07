"""Load metadata.yaml files from source directories."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FileMetadata:
    """Metadata for a single source file."""

    filename: str
    file_path: str  # full path to file
    category: str  # from folder or metadata.yaml
    doc_type: str  # glossary, article, etc.
    title: str = ""
    subject: str = ""
    author: str = ""
    publication: str = ""
    date: str = ""
    translator: str = ""
    default_language: str = "en"
    tags: list[str] = field(default_factory=list)


def load_metadata_yaml(yaml_path: Path) -> dict[str, Any]:
    """Load and parse a metadata.yaml file."""
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def discover_sources(theory_dir: str | Path) -> list[FileMetadata]:
    """Walk Theory/ subdirectories, read metadata.yaml, return FileMetadata list.

    Searches recursively for metadata.yaml files, so nested structures work:
        theory_dir/
        ├── glossary/
        │   ├── metadata.yaml
        │   └── Glossary.pdf
        ├── articles/
        │   ├── metadata.yaml
        │   └── *.docx
        └── blogs/
            ├── kendo3ka/
            │   ├── metadata.yaml
            │   └── *.docx
            └── kenshi247/
                ├── metadata.yaml
                └── *.docx

    Files without a metadata.yaml entry get defaults from the folder-level fields.
    """
    theory_path = Path(theory_dir)
    sources: list[FileMetadata] = []

    for yaml_path in sorted(theory_path.rglob("metadata.yaml")):
        subdir = yaml_path.parent

        meta = load_metadata_yaml(yaml_path)
        folder_category = meta.get("category", subdir.name)
        folder_doc_type = meta.get("doc_type", subdir.name)
        folder_language = meta.get("default_language", "en")
        file_entries = meta.get("files", {})

        # Scan all files in the directory (skip non-document files)
        skip_files = {"metadata.yaml", "urls.yaml"}
        doc_extensions = {".pdf", ".docx", ".doc", ".txt"}
        for file_path in sorted(subdir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.name in skip_files:
                continue
            if file_path.suffix.lower() not in doc_extensions:
                continue

            # Get per-file overrides from metadata.yaml, or empty dict
            file_meta = file_entries.get(file_path.name, {})

            sources.append(FileMetadata(
                filename=file_path.name,
                file_path=str(file_path),
                category=file_meta.get("category", folder_category),
                doc_type=file_meta.get("doc_type", folder_doc_type),
                title=file_meta.get("title", ""),
                subject=file_meta.get("subject", ""),
                author=file_meta.get("author", ""),
                publication=file_meta.get("publication", ""),
                date=file_meta.get("date", ""),
                translator=file_meta.get("translator", ""),
                default_language=file_meta.get("default_language", folder_language),
                tags=file_meta.get("tags", []),
            ))

    return sources
