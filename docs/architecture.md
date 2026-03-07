# Architecture

YKC Kenjin has two main pipelines: **Ingestion** (offline, when you add new documents) and **Retrieval** (online, when you ask questions).

## Ingestion Pipeline

Transforms raw documents into searchable knowledge. Run once after adding or changing source files.

```
$KENDO_THEORY_DIR/
  glossary/metadata.yaml + Glossary.pdf
  articles/metadata.yaml + *.docx
        |
        v
  metadata_loader.py         -- Discovers files, reads metadata.yaml
        |
        v
  pdf_parser.py / docx_parser.py  -- Extracts text from PDF/DOCX
        |
        v
  chunker.py                 -- Splits into chunks (glossary terms = atomic,
        |                       articles = ~800 tokens with overlap)
        |                       Attaches compact metadata: {src, type, lang, idx}
        v
  database.py                -- Registers each source file with a short key
        |                       (G1, A1, A2...) in the sources table.
        |                       Stores glossary terms + document records.
        v
  embedder.py                -- Converts chunks to vectors
        |                       (all-MiniLM-L6-v2, runs locally)
        v
  vector_store.py            -- Stores vectors + compact metadata in ChromaDB
```

## Retrieval Pipeline

Handles user queries. Runs in real-time when you ask a question.

```
"What is zanshin?"
        |
        v
  retriever.py
    |-- Term Extraction       -- Pulls "zanshin" from the question
    |     |
    |     v
    |   SQLite Exact Lookup   -- Finds glossary definition (if term exists)
    |
    |-- Embed Query            -- Converts question to vector
          |
          v
        ChromaDB Search       -- Finds top-K similar chunks by cosine distance
          |
          v
        Resolve Metadata      -- Maps compact keys (src="A3") to full info
                                  (filename, title, subject, file_path)
                                  via cached sources table lookup
        |
        v
  prompt_builder.py           -- Combines:
    |                             - Kendo system prompt (terminology rules)
    |                             - Glossary match (if found)
    |                             - Semantic search results with citations
    |                             - Original question
    v
  Formatted Prompt            -- Ready for Claude Code (copy-paste or auto-call)
```

## Dual-Store Design

The system uses two data stores, each serving a different purpose:

| Store | Purpose | What it holds |
|-------|---------|---------------|
| **ChromaDB** (vector) | Semantic search ("how to improve seme?") | 435 embedded chunks with compact metadata |
| **SQLite** (structured) | Exact lookups + registry | 395 glossary terms, 5 document records, 5 source records with file paths |

**Why two stores?** Kendo questions come in two flavors:
- **"What is zanshin?"** -- needs exact term lookup (SQLite)
- **"How should I approach mental preparation for shiai?"** -- needs semantic similarity search (ChromaDB)

The retriever runs both lookups in parallel and merges the results.

## Source Registry

Each source file is registered once in SQLite with a short key. ChromaDB chunks only store the key, not full metadata strings.

```
Ingestion:  "my-article.docx" --> registered as "A1" in sources table
            Each chunk stores: {src: "A1", type: "article_en", lang: "en", idx: 3}

Retrieval:  chunk.src = "A1" --> lookup sources table --> resolves to:
              filename: "my-article.docx"
              title: "Article Title"
              subject: "Sensei Name"
              file_path: "...\articles\my-article.docx"
```

This saves ~78% metadata storage and scales linearly with more documents.

## Kendo-Aware Features

- **Atomic glossary chunks**: Each term is one chunk, never split mid-definition
- **Article chunking**: ~800 tokens per chunk, 100 token overlap, respects section boundaries
- **Terminology rules**: System prompt enforces correct kendo terms (Men != "face", Kote != "wrist guard")
- **Source citations**: Every answer includes `[Source: filename (file_path)]` references

## Project Structure

```
YKC-Kenjin/
├── .env                          # Config: paths, model, thresholds
├── pyproject.toml                # Python package definition + dependencies
│
├── src/kendocenter/
│   ├── config.py                 # Pydantic settings (reads from .env)
│   ├── main.py                   # FastAPI app entry point
│   │
│   ├── ingestion/                # --- Offline: document processing ---
│   │   ├── metadata_loader.py    # Walks KENDO_THEORY_DIR, reads metadata.yaml per folder
│   │   ├── pdf_parser.py         # Glossary.pdf parser (character-level, two-column extraction)
│   │   ├── docx_parser.py        # Article .docx parser (separates EN/VN sections)
│   │   ├── chunker.py            # Splits text into chunks with compact metadata
│   │   ├── embedder.py           # sentence-transformers wrapper (text -> vectors)
│   │   └── ingest_pipeline.py    # Orchestrates: discover -> parse -> chunk -> embed -> store
│   │
│   ├── storage/                  # --- Data layer ---
│   │   ├── database.py           # SQLite: glossary_terms, documents, sources tables
│   │   ├── vector_store.py       # ChromaDB: add/query/count vectors
│   │   └── models.py             # Dataclasses: Source, GlossaryEntry, Article, DocumentChunk
│   │
│   ├── retrieval/                # --- Online: query processing ---
│   │   ├── retriever.py          # Term extraction + SQLite lookup + ChromaDB search + source resolution
│   │   ├── prompt_builder.py     # Kendo system prompt + context + citations formatting
│   │   └── pipeline.py           # Orchestrates: retrieve -> format -> (optional) generate
│   │
│   ├── generation/
│   │   └── claude_cli.py         # Claude Code CLI wrapper (auto-generate answers)
│   │
│   ├── api/                      # --- REST API ---
│   │   ├── routes_search.py      # POST /api/search
│   │   └── routes_terms.py       # GET /api/terms, GET /api/terms/{term}, GET /api/health
│   │
│   └── ui/
│       └── app.py                # Streamlit frontend
│
├── scripts/                      # See docs/api-reference.md for details
│   ├── ingest_all.py
│   ├── query_cli.py
│   ├── verify_pipeline.py
│   ├── verify_api.py
│   └── stop_servers.py
│
├── docs/                         # Documentation
│   ├── architecture.md           # This file
│   ├── adding-content.md         # How to add new documents
│   └── api-reference.md          # API endpoints, scripts, configuration
│
└── data/                         # Generated at runtime, gitignored
    ├── chroma/                   # ChromaDB vector store files
    └── kendocenter.db            # SQLite database
```
