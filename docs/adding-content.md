# Adding Content to YSK Kenjin

This guide explains how to add new documents to the knowledge base.

## Source Directory Layout

All source documents live in the `KENDO_THEORY_DIR` directory (configured in `.env`), organized by type with a `metadata.yaml` in each subfolder:

```
$KENDO_THEORY_DIR/
├── glossary/
│   ├── metadata.yaml
│   └── Glossary.pdf              # 395 kendo terms (G1)
├── articles/
│   ├── metadata.yaml
│   └── *.docx                    # Your kendo article files
└── blogs/
    ├── kendo3ka/                  # Vietnamese blog articles
    │   ├── metadata.yaml
    │   ├── urls.yaml
    │   └── *.docx
    ├── kenshi247/                 # English blog articles (kenshi247.net)
    │   ├── metadata.yaml
    │   ├── urls.yaml
    │   └── *.docx
    ├── kendoinfo/                 # English articles (Geoff Salmon)
    │   ├── metadata.yaml
    │   ├── urls.yaml
    │   └── *.docx
    ├── nanseikan/                 # English articles (Nanseikan blog)
    │   ├── metadata.yaml
    │   ├── urls.yaml
    │   └── *.docx
    └── kendophilosophy/           # Kendo history and philosophy
        ├── metadata.yaml
        ├── urls.yaml
        └── *.docx
```

## metadata.yaml Format

Each subfolder has a `metadata.yaml` that describes its files. The ingestion pipeline reads this to know how to categorize and tag each document.

```yaml
# articles/metadata.yaml
category: articles
description: "Kendo article translations"
doc_type: article                   # determines source key prefix (A1, A2...)
default_language: en

files:
  My-Kendo-Article.docx:
    title: "Title of the Article"
    subject: "Sensei Name"
    publication: "Source Publication"
    date: "2025.1"
    translator: "Translator Name"
    tags: [interview, 7dan, technique]

  Another-Article.docx:
    title: "Another Article Title"
    subject: "Another Sensei"
    date: "2024.11"
    tags: [philosophy, 8dan]
```

```yaml
# glossary/metadata.yaml
category: glossary
description: "Kendo terminology reference"
doc_type: glossary                  # determines source key prefix (G1)
default_language: en

files:
  Glossary.pdf:
    title: "Glossary of Terms in Kendo"
    author: "Stephen Quinlan"
    tags: [terminology, reference, glossary]
```

### Field Reference

| Field | Level | Required | Description |
|-------|-------|----------|-------------|
| `category` | folder | yes | Content category (articles, glossary, kata, etc.) |
| `doc_type` | folder | yes | Determines source key prefix: `glossary` -> G, `article` -> A |
| `default_language` | folder | no | Default language for files (default: en) |
| `description` | folder | no | Human-readable folder description |
| `title` | file | no | Document title for citations |
| `subject` | file | no | Main subject (e.g., sensei name) |
| `publication` | file | no | Source publication |
| `date` | file | no | Publication date |
| `translator` | file | no | Translator name(s) |
| `tags` | file | no | List of tags for categorization |

## Adding a New Article

When you have a new translated article (e.g., a kendo magazine interview):

### Step 1: Place the file

Copy your `.docx` file into the appropriate subfolder:

```
$KENDO_THEORY_DIR/articles/My-New-Article.docx
```

### Step 2: Update metadata.yaml

Add an entry for the new file in `articles/metadata.yaml`:

```yaml
files:
  # ... existing entries ...

  My-New-Article.docx:
    title: "The New Article Title"
    subject: "Sensei Name"
    publication: "Source Magazine"
    date: "2026.3"
    translator: "Translator Name"
    tags: [interview, technique]
```

### Step 3: Re-run ingestion

Rebuild the entire knowledge base (glossary + all articles):

```bash
python scripts/ingest_all.py --reset
```

The `--reset` flag clears ChromaDB and rebuilds everything. This ensures clean, consistent data. With 5-10 sources, full re-ingestion takes only a few seconds.

### Step 4: Verify

```bash
# Check database, vector store, and retrieval pipeline
python scripts/verify_pipeline.py

# Check all API endpoints
python scripts/verify_api.py
```

Both scripts should show all checks passed. The pipeline check will confirm the new source was registered and chunks were created.

### Step 5: Test a query

```bash
python scripts/query_cli.py "topic from your new article"
```

## Adding a New Content Type

To add an entirely new category (e.g., kata guides, grading criteria):

1. Create a new subfolder: `$KENDO_THEORY_DIR/kata/`
2. Add a `metadata.yaml`:
   ```yaml
   category: kata
   description: "Kata reference guides"
   doc_type: article
   default_language: en

   files:
     Nihon-Kata.docx:
       title: "Nihon Kendo Kata Guide"
       tags: [kata, reference]
   ```
3. Place the `.docx` files in the folder
4. Run `scripts/ingest_all.py --reset` and verify

No code changes needed. The ingestion pipeline automatically discovers new subfolders with `metadata.yaml`.

## Adding Blog Articles (Scraping)

For WordPress blogs, use the blog scraper instead of manually creating `.docx` files:

### Step 1: Create urls.yaml

Create a subfolder under `KENDO_THEORY_DIR/blogs/` with a `urls.yaml`:

```yaml
# blogs/kenshi247/urls.yaml
category: kenshi247
description: "English kendo theory articles from kenshi247.net"
doc_type: article
default_language: en
default_tags: [blog, english, kenshi247, theory]
delay: 2.0
urls:
  - url: https://kenshi247.net/blog/category/theory/
    type: category
```

The scraper crawls WordPress category pages with pagination and extracts all article links.

### Step 2: Run the scraper

Each blog source has its own scraper script in `scripts/scraping/`:

```bash
# Scrape kendo3ka (Vietnamese)
python scripts/scraping/scrape_kendo3ka.py --dry-run
python scripts/scraping/scrape_kendo3ka.py

# Scrape kenshi247 (English)
python scripts/scraping/scrape_kenshi247.py --dry-run
python scripts/scraping/scrape_kenshi247.py

# Scrape kendoinfo (English, Geoff Salmon)
python scripts/scraping/scrape_kendoinfo.py --dry-run
python scripts/scraping/scrape_kendoinfo.py

# Scrape nanseikan (English, Blogspot)
python scripts/scraping/scrape_nanseikan.py --dry-run
python scripts/scraping/scrape_nanseikan.py

# Scrape kendophilosophy (English, history & philosophy)
python scripts/scraping/scrape_kendophilosophy.py --dry-run
python scripts/scraping/scrape_kendophilosophy.py
```

The scraper:
- Crawls category pages, following pagination links
- Extracts article content (title, date, paragraphs)
- Saves each article as a `.docx` file
- Auto-generates/updates `metadata.yaml` with entries for each article
- Skips articles that already have a `.docx` file

### Step 3: Ingest and verify

```bash
python scripts/ingest_all.py --reset
python scripts/verify_pipeline.py
```

## Article Format Requirements

The `.docx` parser expects articles with English and Vietnamese sections. It detects language boundaries automatically by looking for Vietnamese diacritics. If your article is English-only, it will work fine (Vietnamese section will simply be empty).

The PDF parser is specialized for the Glossary.pdf format (LaTeX-generated, two-column layout with character-level extraction). Other PDFs would need a new parser.

## What Happens During Ingestion

When you run `ingest_all.py --reset`:

1. **ChromaDB is cleared** (all vectors deleted)
2. **SQLite database is deleted** and recreated with fresh tables
3. **Source discovery**: Walks all subfolders in `KENDO_THEORY_DIR`, reads each `metadata.yaml`
4. **Source registration**: Each file gets a short key (G1, A1, A2...) in the `sources` table
5. **Parsing**: PDF parser extracts glossary terms; DOCX parser extracts article text
6. **Chunking**: Glossary terms become atomic chunks; articles split into ~800 token chunks
7. **Embedding**: All chunks converted to vectors using the `all-MiniLM-L6-v2` model
8. **Storage**: Vectors + compact metadata stored in ChromaDB; terms + docs stored in SQLite

### Without `--reset`

Running without `--reset` adds new data on top of existing data. The pipeline has deduplication built in:
- **ChromaDB**: Uses `upsert()` so identical chunks (same content hash) are updated, not duplicated
- **SQLite glossary**: Deletes and re-inserts entries from the same source document
- **SQLite chunks**: Deletes old chunks for a document before inserting new ones
- **Sources**: Existing filenames return their existing source_key

This means re-running ingestion on the same files is safe. Use `--reset` for a guaranteed clean rebuild.
