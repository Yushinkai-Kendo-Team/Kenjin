# YSK Kenjin - Project Plan

## Vision

YSK Kenjin (Yushinkai Kenjin) is the AI assistant for **Yushinkai Kendo Team**. It helps members and the kendo community with:

1. **Deep kendo knowledge** — explains any term, technique, or concept with references to articles, books, and sensei teachings
2. **Kendo-aware video translation** — Japanese audio transcription with correct kendo terminology (not generic translation)
3. **Team intelligence** — understands Yushinkai's activities, events, and community through Facebook and social media data
4. **Technique encyclopedia** — categorized techniques with definitions, illustrations, and different styles from different sensei

The core philosophy: **accuracy over breadth**. Better to answer 100 kendo questions perfectly with citations than 1000 questions with hallucinations. Every phase prioritizes RAG quality and retrieval accuracy before adding new features.

## Why RAG (not fine-tuning, not custom LLM)

| Approach | Verdict | Why |
|----------|---------|-----|
| **RAG** | **Use this** | Retrieves curated sources, feeds them to Claude as context. Answers are grounded with citations. Adding new knowledge = just index a new document. No retraining. |
| **Fine-tuning** | Wrong fit | Doesn't solve hallucination. Can't cite sources. Costs hundreds per training run. Must retrain when knowledge changes. ~12MB of text is too small. |
| **Custom LLM** | Overkill | Requires billions of tokens and massive GPU. Claude already understands Japanese, English, and martial arts. |

**Key insight:** The value is in the *curated knowledge base* (glossary, articles, sensei teachings). RAG lets Claude use that knowledge precisely, with references.

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.12 | Best AI/ML ecosystem |
| Backend | FastAPI | Async, auto-docs, good for APIs |
| LLM | Claude Code (Phase 1), Claude API (future) | Handles Japanese/English well |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, local, no API cost |
| Vector DB | ChromaDB | Zero config, pip install |
| Structured DB | SQLite | Zero config, file-based |
| Doc Parsing | pdfplumber (PDF), python-docx (DOCX) | Reliable extraction |
| Metadata | PyYAML | Per-folder metadata.yaml for source categorization |
| Frontend (MVP) | Streamlit | One Python file, instant UI for rapid prototyping |
| Frontend (later) | Next.js + Tailwind | Proper web app (deferred until core RAG is mature) |
| Video (Phase 4) | OpenAI Whisper | Best open-source Japanese transcription |
| Japanese NLP | Custom dictionary + Whisper fine-tune | Kendo-specific pronunciation mapping |

---

## Phased Roadmap

### Phase 1 - Foundation: Knowledge Base + RAG [COMPLETE]

Everything below has been built and tested:

- [x] Parse Glossary.pdf into 395 structured term entries (character-level extraction)
- [x] Parse .docx articles into chunked passages (EN/VN separation)
- [x] ChromaDB vector store with 435 embedded chunks (cosine similarity)
- [x] SQLite for structured glossary terms + document metadata
- [x] RAG pipeline: query -> embed -> retrieve -> formatted prompt with citations
- [x] Term extraction from natural-language questions
- [x] Kendo system prompt with terminology rules
- [x] FastAPI API endpoints (search, terms, health)
- [x] Streamlit UI (question search + glossary browser + copy-paste prompt)
- [x] Claude Code CLI integration (auto-generate answers from Streamlit/FastAPI)
- [x] CLI tool for testing

**Phase 1 stats:**
- 395 glossary entries from Glossary.pdf
- .docx articles with EN/VN sections
- 435 total chunks in vector store
- 3 categories: general (357), shiai (24), dojo_commands (14)

**Phase 1 verification results:**
- Exact term lookup: "What is Zanshin?" -> glossary match + 8 semantic results
- Semantic question: "How does [sensei] approach mental preparation?" -> 8 relevant article chunks
- Cross-reference: "chiisai men vs ooki men" -> related glossary terms found
- Unknown topic: "history of naginata" -> only 4 low-relevance results (proper filtering)

### Phase 1.5 - Refactor: Source Structure + Reference Optimization [COMPLETE]

**Why:** Before expanding the knowledge base, we needed a scalable foundation.

**Part A: Restructure source documents**
- [x] Reorganize `KENDO_THEORY_DIR` into subfolders: `glossary/`, `articles/`, (future: `kata/`, `videos/`)
- [x] Add `metadata.yaml` per folder — defines category, per-file metadata (title, subject, tags)
- [x] Create `metadata_loader.py` — reads metadata.yaml, resolves per-file overrides
- [x] Update `ingest_pipeline.py` — walk subdirs, read metadata.yaml instead of hardcoded logic

**Part B: Source reference registry (memory-optimized)**
- [x] Add `sources` table in SQLite — stores filename, file_path, category, title, subject, tags
- [x] Each source gets a short key ("G1", "A1", "A2") instead of full filename
- [x] ChromaDB chunk metadata: `{"src": "A1", "type": "article_en", "lang": "en", "idx": 3}` instead of repeating full strings
- [x] Retriever resolves `src` keys via cached lookup at query time
- [x] ~78% metadata storage reduction (grows linearly with more documents)

**Part C: Source file path tracking**
- [x] Store full file paths in `sources` table
- [x] Prompt builder includes file path in citations
- [x] Streamlit UI shows source file location in results

**Phase 1.5 verification results:**
- Sources registered with correct file paths
- All data counts match Phase 1: 395 terms, 435 chunks
- Metadata resolution working: source keys -> filenames with title, subject, file_path
- FastAPI returns resolved metadata in search results
- `scripts/verify_pipeline.py` passes all 4/4 checks

### Phase 2 - RAG Optimization + Claude API [NEXT]

**Goal:** Make the retrieval pipeline significantly more accurate and integrate direct LLM generation.

**Part A: Retrieval quality** ✓
- [x] Upgrade embedding model: auto-prefix support for E5/BGE families (`embedder.py`), swap via `EMBEDDING_MODEL` env var
- [x] Implement re-ranking: cross-encoder two-stage retrieval (`reranker.py`), toggle via `RERANKER_ENABLED` env var
- [x] Improve chunking strategy: configurable chunk size/overlap + optional title prepend via settings
- [x] Add chunk overlap tuning: `CHUNKING_MAX_TOKENS` and `CHUNKING_OVERLAP_TOKENS` env vars
- [x] Build evaluation dataset: 52 Q&A pairs across 6 categories in `data/eval/eval_dataset.yaml`
- [x] Automated RAG evaluation pipeline: recall@k, MRR, glossary hit rate, keyword recall (`scripts/run_eval.py`)

**Part B: Claude API integration**
- [ ] Add ANTHROPIC_API_KEY support — generate answers directly in the pipeline
- [ ] Streaming responses in Streamlit UI
- [ ] Conversation memory (multi-turn follow-up questions)
- [ ] Answer quality scoring: compare RAG-augmented vs. standalone Claude answers

**Part C: Expanded knowledge + hybrid search**
- [ ] Expanded DB schema: techniques, waza categories, sensei profiles
- [ ] Hybrid search: BM25 keyword search + semantic vector search (weighted fusion)
- [ ] Better glossary matching: fuzzy matching, romaji/kanji normalization
- [ ] Source quality weighting: glossary > articles > blogs in ranking

### Phase 3 - Yushinkai Team Intelligence + YouTube Catalog

**Goal:** Make YSK Kenjin the team's AI assistant and build a searchable catalog of kendo video resources.

**Part A: Facebook data ingestion**
- [ ] Scrape/export Yushinkai Facebook page posts, photos, event announcements
- [ ] Parse Facebook group discussions and member Q&A
- [ ] Extract event schedules, training updates, tournament results
- [ ] Ingest team-specific terminology and inside references

**Part B: Team knowledge base**
- [ ] Team member profiles (with consent): dan grade, years training, specialties
- [ ] Training schedule and dojo information
- [ ] Team event history and tournament results
- [ ] Sensei teaching notes and team-specific guidance

**Part C: Team-facing features**
- [ ] "When is the next training?" — answers from team schedule data
- [ ] "What did sensei teach last week?" — summarizes recent training posts
- [ ] "Who in our team does jodan?" — member knowledge queries
- [ ] Event reminders and preparation guidance

**Part D: YouTube video catalog**
- [ ] Build curated list of kendo YouTube channels and playlists (seminars, 8-dan matches, instruction)
- [ ] Scrape video metadata: title, description, tags, duration, channel, publish date
- [ ] Parse video descriptions for technique mentions, sensei names, event context
- [ ] Ingest video metadata into RAG — queries now return relevant video URLs
- [ ] "Show me videos about seme" → returns YouTube links with context from descriptions
- [ ] Tag videos by topic: technique, seminar, shiai, kata, beginner, advanced

### Phase 4 - Japanese Kendo Terminology Engine

**Goal:** Build the foundation for accurate Japanese kendo audio processing.

**Part A: Kendo terminology dictionary**
- [ ] Build comprehensive JP-EN kendo term mapping (romaji, kanji, hiragana, English)
- [ ] Include variant pronunciations and regional differences
- [ ] Map compound terms (e.g., "ki-ken-tai-ichi", "seme-ai", "tsuba-zeriai")
- [ ] Cross-reference with existing glossary for consistency

**Part B: Japanese pronunciation training data**
- [ ] Collect kendo-specific audio samples (sensei commands, technique names, shiai calls)
- [ ] Build pronunciation guide dataset: audio clip -> romaji -> English term
- [ ] Annotate common mispronunciations and accent patterns in kendo context
- [ ] Create custom Whisper vocabulary/dictionary for kendo terms

**Part C: Whisper fine-tuning preparation**
- [ ] Evaluate base Whisper models (small, medium, large) on kendo audio
- [ ] Measure baseline accuracy on kendo terminology transcription
- [ ] Identify failure patterns: which terms does Whisper get wrong?
- [ ] Prepare fine-tuning dataset: aligned audio + corrected transcriptions

### Phase 5 - Kendo Video Processing

**Goal:** Transcribe and translate kendo videos with correct terminology. Builds on Phase 3's video catalog (metadata already indexed) and Phase 4's terminology engine.

- [ ] Whisper integration for Japanese audio transcription
- [ ] Custom post-processing: Whisper output -> kendo term correction using Phase 4 dictionary
- [ ] Kendo-aware translation (RAG ensures "men" stays as "Men", not "face")
- [ ] YouTube URL download + audio extraction pipeline
- [ ] Timestamp-linked technique annotations
- [ ] Transcriptions ingested into RAG — full-text video search alongside articles and glossary
- [ ] Subtitle generation (.srt) with kendo terminology preserved

### Phase 6 - Rich Content + Web Frontend + Multi-user

**Goal:** Build the proper web experience once the core is mature.

- [ ] Next.js frontend replacing Streamlit
- [ ] Technique encyclopedia pages with sensei variations
- [ ] Cross-referencing: terms <-> techniques <-> videos <-> articles
- [ ] Browse glossary by category, individual term pages
- [ ] Admin interface for adding/curating knowledge
- [ ] User authentication, PostgreSQL migration
- [ ] Personal bookmarks, training notes
- [ ] Multi-team support (other kendo teams can deploy their own instance)

---

## Key Design Decisions

1. **No API key needed for Phase 1.** Claude Code serves as the LLM. The retrieval system outputs formatted prompts for copy-paste. When an API key is added, the same pipeline feeds Claude API directly.

2. **Dual-store (ChromaDB + SQLite):** Vector search for semantic questions + exact lookup for term queries. Both are needed for a terminology-heavy domain like kendo.

3. **Kendo-aware chunking:** Glossary terms are atomic units (never split). Articles split by paragraphs (~800 tokens, 100 token overlap) respecting section boundaries.

4. **Embedding model:** Started with all-MiniLM-L6-v2 (fast, English-focused). Can upgrade to multilingual-e5-large for better Japanese support.

5. **Character-level PDF extraction:** The Glossary.pdf is LaTeX-generated with two columns and concatenated words. Standard text extraction fails. Solution: character-level extraction with gap analysis (>2px gap = space), column split at x=305.

6. **Similarity threshold = 0.7:** ChromaDB cosine distance range is 0-2 (lower = more similar). Threshold of 0.7 filters noise while keeping relevant results. Originally 0.3 was too strict.

7. **Source registry with compact metadata (Phase 1.5):** Each source file gets a short key (G1, A1). ChromaDB stores only the key per chunk. Full metadata is resolved at query time via a cached SQLite lookup. Saves ~78% on metadata storage and scales linearly.

8. **metadata.yaml per folder:** New source files only need a metadata.yaml entry to be ingested. No code changes needed for new content types — just create a new subfolder with its own metadata.yaml.

---

## Knowledge Sources

### Current

Sources organized in `KENDO_THEORY_DIR` (configured in `.env`) with per-folder `metadata.yaml`:

| Category | Location | Content |
|----------|----------|---------|
| Glossary | `glossary/` | 395 kendo terms with romaji, kanji, definitions, categories |
| Articles | `articles/` | Kendo article translations (EN/VN) |
| Blogs | `blogs/kendo3ka/` | Vietnamese blog articles (14) |
| Blogs | `blogs/kenshi247/` | English blog articles from kenshi247.net (47) |
| Blogs | `blogs/kendoinfo/` | English articles by Geoff Salmon (52) |
| Blogs | `blogs/nanseikan/` | English articles from Nanseikan blog (11) |
| Blogs | `blogs/kendophilosophy/` | Kendo history and philosophy (10) |

### Future Sources
- More kendo article translations
- Technique breakdowns and analysis
- Kata guides (`kata/` subfolder)
- Grading criteria (`grading/` subfolder)
- Yushinkai Facebook posts and event data (Phase 3)
- YouTube video metadata — titles, descriptions, tags (Phase 3)
- Japanese-English kendo terminology dictionary (Phase 4)
- Video transcriptions (`videos/` subfolder, Phase 5)
- Sensei teaching notes
- Tournament reports and analyses
- Team training session summaries
