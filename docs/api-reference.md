# API Reference

## REST API Endpoints

Start the FastAPI server (with venv activated):

```bash
set PYTHONPATH=src            & REM Windows
# export PYTHONPATH=src       # macOS / Linux
python -m uvicorn kendocenter.main:app --port 8001
```

Interactive API docs available at `http://localhost:8001/docs`.

### POST /api/search

Search the knowledge base with a natural-language question.

**Request body:**
```json
{
  "question": "What is zanshin?",
  "n_results": 8,
  "language": "en",
  "generate": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question` | string | required | The kendo question to search for |
| `n_results` | int | 8 | Maximum number of semantic search results |
| `language` | string | null | Filter by language: `"en"`, `"vn"`, or null for all |
| `generate` | bool | false | If true, auto-call Claude Code CLI for an AI answer |

**Response:**
```json
{
  "query": "What is zanshin?",
  "glossary_match": {
    "term_romaji": "Zanshin",
    "term_kanji": "残心",
    "definition": "Remaining mind. In the context of kendo...",
    "category": "general"
  },
  "results": [
    {
      "text": "Chunk text content...",
      "metadata": {
        "src": "A1",
        "type": "article_en",
        "lang": "en",
        "source": "my-article.docx",
        "title": "Article Title...",
        "file_path": "...\\articles\\my-article.docx",
        "source_key": "A1"
      },
      "distance": 0.45,
      "rerank_score": 2.31
    }
  ],
  "formatted_prompt": "System prompt + context + question...",
  "ai_answer": ""
}
```

The `rerank_score` field is only present when re-ranking is enabled (`RERANKER_ENABLED=true`). Higher scores = more relevant.

```json
// Without re-ranking (default):
{ "text": "...", "metadata": {...}, "distance": 0.45 }

// With re-ranking enabled:
{ "text": "...", "metadata": {...}, "distance": 0.45, "rerank_score": 2.31 }
```

### GET /api/terms

List or search glossary terms.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | "" | Search filter (matches term name) |
| `category` | string | "" | Filter by category: `general`, `shiai`, `dojo_commands` |
| `limit` | int | 50 | Max results per page |
| `offset` | int | 0 | Pagination offset |

**Examples:**
```
GET /api/terms                          # First 50 terms
GET /api/terms?query=kamae              # Terms matching "kamae"
GET /api/terms?category=shiai&limit=10  # First 10 shiai terms
```

**Response:**
```json
{
  "items": [
    {
      "term_romaji": "Kamae",
      "term_kanji": "構え",
      "definition": "Posture/stance...",
      "category": "general"
    }
  ],
  "total": 395,
  "categories": ["general", "shiai", "dojo_commands"]
}
```

### GET /api/terms/{term_romaji}

Get a specific glossary term by its romaji name.

**Example:**
```
GET /api/terms/Zanshin
```

**Response:**
```json
{
  "term_romaji": "Zanshin",
  "term_kanji": "残心",
  "definition": "Remaining mind...",
  "category": "general"
}
```

Returns `{"error": "Term not found", "term": "..."}` if the term doesn't exist.

### GET /api/health

System health check with data counts.

**Response:**
```json
{
  "status": "healthy",
  "glossary_terms": 395,
  "documents": 5,
  "vector_store_entries": 435
}
```

## Scripts

| Script | Description | Usage |
|--------|-------------|-------|
| `ingest_all.py` | Run full ingestion pipeline | `--reset` to rebuild from scratch |
| `query_cli.py` | CLI for testing queries | `--interactive` for REPL, `--prompt` to show full prompt |
| `verify_pipeline.py` | Verify database + vector store + retrieval (7 checks) | `--verbose` for details |
| `verify_api.py` | Start server, run 9 API checks, stop server | `--verbose` for details |
| `run_eval.py` | Run RAG evaluation on 50+ question dataset | `--verbose`, `--category <name>`, `--output results.json` |
| `compare_models.py` | Compare two eval result JSON files | `compare_models.py baseline.json current.json` |
| `scrape_blog.py` | Scrape blog articles from URLs defined in `urls.yaml` | `--dry-run` to preview, `--source` to filter |
| `stop_servers.py` | Kill running uvicorn/streamlit processes | No arguments |

### scrape_blog.py

Scrapes WordPress blog articles and saves them as `.docx` files for ingestion:

1. Reads `urls.yaml` from each subfolder in `KENDO_THEORY_DIR`
2. Crawls category pages with pagination to discover all article links
3. Fetches each article's content (title, date, paragraphs)
4. Saves as `.docx` files and auto-generates `metadata.yaml` entries
5. Skips already-scraped articles (checks if `.docx` exists)

**urls.yaml format:**
```yaml
category: blogs
description: "Vietnamese kendo blog articles"
doc_type: article
default_language: vi
default_tags: [blog, vietnamese]
delay: 1.5
urls:
  - url: https://example.com/category/kendo/
    type: category
```

### run_eval.py

Runs the RAG evaluation dataset (50 Q&A pairs) through the retrieval pipeline and reports metrics:

```bash
python scripts/run_eval.py                          # Quick overview
python scripts/run_eval.py --verbose                 # Per-question detail + failures
python scripts/run_eval.py --category semantic_blog  # Run one category only
python scripts/run_eval.py --output results.json     # Save for later comparison
python scripts/run_eval.py --compare baseline.json   # Compare against saved baseline
```

Categories: `glossary_lookup`, `semantic_article`, `semantic_blog`, `cross_source`, `multilingual`, `negative`

### compare_models.py

Compares two saved evaluation result files (from `run_eval.py --output`):

```bash
python scripts/compare_models.py data/eval/baseline-minilm.json data/eval/e5-results.json
```

### verify_pipeline.py

Checks the data layer and retrieval pipeline without starting a server:

1. **Database check**: Terms >= 395, documents >= 5, sources >= 5
2. **Vector store check**: Vectors >= 435
3. **Glossary retrieval**: "What is zanshin?" returns glossary match + resolved metadata
4. **Article retrieval**: Uchimura query returns article chunks with file paths
5. **Blog retrieval**: "What is maai in kendo?" returns blog article from blogs/ category
6. **Vietnamese content**: "ki ken tai ichi" returns the ki-ken-tai-ichi blog article
7. **Cross-source**: "Explain zanshin" returns results from articles, blogs, and glossary

### verify_api.py

Starts a FastAPI server, tests all endpoints, then stops the server:

1. **GET /**: App name and version
2. **GET /api/health**: Term, document, vector counts
3. **GET /api/terms?query=kamae**: Term list search
4. **GET /api/terms/Zanshin**: Specific term detail
5. **POST /api/search** (glossary): Metadata resolution + prompt generation
6. **POST /api/search** (article): File path in results + article retrieval
7. **POST /api/search** (blog): Blog content retrieval from blogs/ category
8. **POST /api/search** (cross-source): Zanshin returns results from articles, blogs, glossary
9. **POST /api/search** (language filter): Vietnamese filter returns only VN-tagged chunks

## Configuration (.env)

All settings are loaded from `.env` via Pydantic settings. The `.env` file is the single source of truth for paths and tuning parameters.

```env
KENDO_THEORY_DIR=/path/to/your/theory/folder   # Root directory for kendo source documents
CHROMA_PERSIST_DIR=data/chroma                  # ChromaDB storage location
SQLITE_DB_PATH=data/kendocenter.db              # SQLite database file
EMBEDDING_MODEL=all-MiniLM-L6-v2                # Sentence-transformers model name
RETRIEVAL_TOP_K=8                               # Number of semantic search results
SIMILARITY_THRESHOLD=0.7                        # ChromaDB cosine distance cutoff (0-2, lower = more similar)
ANTHROPIC_API_KEY=                              # Optional, for future Claude API integration
```

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `KENDO_THEORY_DIR` | (required) | Where your source documents live |
| `RETRIEVAL_TOP_K` | 8 | More results = more context but slower + more noise |
| `SIMILARITY_THRESHOLD` | 0.7 | Lower = stricter matching. Range 0-2 (cosine distance). Was 0.3 originally (too strict), 0.7 works well |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | Fast, English-focused. Can upgrade to `multilingual-e5-large` for better Japanese support |

### Phase 2A: Retrieval Optimization

| Setting | Default | Description |
|---------|---------|-------------|
| `RERANKER_ENABLED` | false | Enable cross-encoder re-ranking (two-stage retrieval) |
| `RERANKER_MODEL` | cross-encoder/ms-marco-MiniLM-L-6-v2 | Cross-encoder model name (from sentence-transformers) |
| `RERANKER_CANDIDATE_COUNT` | 20 | Candidates fetched from ChromaDB before re-ranking |
| `CHUNKING_MAX_TOKENS` | 800 | Max tokens per chunk during ingestion (re-ingest required) |
| `CHUNKING_OVERLAP_TOKENS` | 100 | Overlap tokens between chunks (re-ingest required) |
| `CHUNKING_PREPEND_TITLE` | false | Prepend article title to each chunk (re-ingest required) |

**Re-ranking**: When enabled, the retriever fetches 20 candidates from ChromaDB, then re-ranks them with a cross-encoder to return the best 8. The cross-encoder model is lazy-loaded on first use (~22MB download). Falls back to vector search order if re-ranking fails.

**Embedding model upgrade**: Set `EMBEDDING_MODEL=intfloat/multilingual-e5-base` (or `multilingual-e5-large`) for better multilingual support. Instruction prefixes (`query: ` / `passage: `) are detected automatically. **Re-ingest required** after changing the embedding model (`python scripts/ingest_all.py --reset`).

### RAG Evaluation

Run the evaluation pipeline to measure retrieval quality:

```bash
# Baseline evaluation
python scripts/run_eval.py --verbose

# Save results for comparison
python scripts/run_eval.py --output data/eval/baseline.json

# Run a specific category
python scripts/run_eval.py --category glossary_lookup --verbose

# Compare two runs
python scripts/compare_models.py data/eval/baseline.json data/eval/new-results.json
```

The evaluation dataset (`data/eval/eval_dataset.yaml`) contains 50 Q&A pairs across 6 categories: glossary lookup, semantic article, semantic blog, cross-source, multilingual, and negative (out-of-scope).

Metrics reported: **Recall@k** (k=3,5,8), **MRR** (Mean Reciprocal Rank), **Glossary Hit Rate**, **Keyword Recall**.
