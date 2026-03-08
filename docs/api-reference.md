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
      "distance": 0.45
    }
  ],
  "formatted_prompt": "System prompt + context + question...",
  "ai_answer": ""
}
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
