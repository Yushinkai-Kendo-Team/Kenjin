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
| Embeddings | sentence-transformers (BAAI/bge-m3, 1024d) | Free, local, multilingual (EN+VN+JP) |
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

*Why these changes:* Phase 1 had no way to measure retrieval accuracy — we couldn't tell if changes helped or hurt. The embedding model (all-MiniLM-L6-v2) is English-only, which degrades Vietnamese content retrieval. Vector search alone ranks by cosine distance, which is a rough approximation — a cross-encoder re-ranker reads query+passage together for much better relevance judgment. Chunking parameters were hardcoded, making experimentation impossible.

- [x] **Evaluation framework first** — built before making any changes, so every optimization is measured. 50 Q&A pairs across 6 categories (glossary, semantic, cross-source, multilingual, negative). Metrics: Recall@k, MRR, Glossary Hit Rate, Keyword Recall. *Why:* You can't improve what you can't measure. Baseline: Recall@8=0.727, MRR=0.677.
- [x] **Cross-encoder re-ranking** — two-stage retrieval: vector search fetches 20 candidates, cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-ranks to top 8. Relaxed similarity threshold when re-ranking to avoid discarding borderline candidates before the cross-encoder sees them. *Why:* Cosine similarity is a weak proxy for relevance. Cross-encoders read query and passage together, catching semantic matches that embedding distance misses. Result: MRR +5.5%, Recall@3 +5.3%.
- [x] **E5/BGE embedding prefix support** — auto-detects model family and prepends instruction prefixes (`query: ` / `passage: `). *Why:* Modern multilingual models (E5, BGE) require these prefixes for optimal asymmetric retrieval. Without them, switching models silently degrades quality. This unblocks the embedding model upgrade in Part B.
- [x] **Configurable chunking** — `CHUNKING_MAX_TOKENS`, `CHUNKING_OVERLAP_TOKENS`, `CHUNKING_PREPEND_TITLE` as env vars. *Why:* Chunk size directly affects retrieval — too large dilutes relevance, too small loses context. Making these configurable enables A/B testing with the eval framework.

**Part B: Hybrid search + retrieval improvements** ✓

*Why this before Claude API:* Retrieval quality improvements compound — better retrieval means better answers regardless of which LLM layer is used. Hybrid search is the single highest-impact missing feature: pure vector search misses exact Japanese/romanji term matches that BM25 catches. Claude Code CLI is fully sufficient as the LLM layer for now.

- [x] **Hybrid search** — SQLite FTS5 for BM25 keyword search + ChromaDB vector search, merged via Reciprocal Rank Fusion (`hybrid.py`). Toggle via `HYBRID_ENABLED` env var. *Why:* Kendo terminology (romanji like "tsuki", "zanshin") needs exact keyword matching that cosine similarity often misses. Result: with reranker, Recall@3 +11.3%, MRR +8.6%.
- [x] **Fuzzy glossary matching** — rapidfuzz-based fuzzy matching with romaji normalization (strip macrons, hyphens, case). Kanji matching for CJK queries. Toggle via `FUZZY_ENABLED` env var. *Why:* Exact matching misses spelling variants and kanji queries. Result: Glossary Hit Rate +8.3%.
- [x] **Source quality weighting** — configurable per-category weights applied during RRF fusion (glossary=1.5, articles=1.2, blogs=1.0). *Why:* Glossary definitions are authoritative; weighting prevents blog noise from outranking them.
- [x] **Embedding model upgrade support** — bge-m3 prefix detection (no prefix for dense retrieval), dimension validation in vector_store. `EMBEDDING_MODEL=BAAI/bge-m3` in .env + re-ingest. *Why:* all-MiniLM-L6-v2 is English-only; bge-m3 supports EN+VN natively.
- [x] **chunk_id fix** — vector_store now returns actual ChromaDB document IDs instead of empty strings for non-glossary chunks. *Why:* Required for hybrid search RRF to join vector and keyword results.
- [ ] Expanded DB schema: techniques, waza categories, sensei profiles — deferred to Phase 3.

**Phase 2B evaluation results (bge-m3 + hybrid + reranker + fuzzy, n=50 questions):**

| Metric | Phase 1 Baseline | Phase 2B | Change |
|--------|-----------------|----------|--------|
| Recall@3 | 0.580 | 0.689 | +10.9pp |
| Recall@5 | 0.696 | 0.756 | +6.0pp |
| Recall@8 | 0.727 | 0.775 | +4.8pp |
| MRR | 0.677 | 0.753 | +7.6pp |
| Glossary Hit Rate | 0.375 | 0.458 | +8.3pp |
| Keyword Recall | 0.855 | 0.908 | +5.3pp |

*What improved:* Precision at top ranks (Recall@3, MRR) benefited most from the bge-m3 multilingual embeddings combined with cross-encoder reranking. Hybrid search (BM25 + vector) catches exact romanji term matches that pure vector search misses. Fuzzy matching helps with spelling variants.

*What's still weak:*
- Cross-source retrieval (Recall@3=0.379) — queries needing results from multiple source types remain the hardest category. This likely needs better chunking or query decomposition, not more retrieval features.
- Glossary Hit Rate at 0.458 means fuzzy matching only catches about half of glossary queries — the other half rely on vector search alone.
- bge-m3 is significantly slower on CPU (~270ms/query vs ~50ms for MiniLM; first query ~16s for model load). GPU acceleration recommended for production.
- Eval set is 50 questions — results are directional, not statistically conclusive. Some categories have only 5 samples.

*Saved baselines:* `data/eval/baseline-minilm.json`, `data/eval/reranker-minilm.json`, `data/eval/baseline-2b.json`, `data/eval/bge-m3-all-features.json`

**Part C: Claude API integration**

*Why deferred:* Claude Code CLI works well for the current single-user workflow. API integration adds complexity (key management, rate limits, cost) without improving retrieval quality. Worth adding when the UI needs streaming responses or multi-turn conversations.

- [ ] Add ANTHROPIC_API_KEY support — generate answers directly in the pipeline
- [ ] Streaming responses in Streamlit UI
- [ ] Conversation memory (multi-turn follow-up questions)
- [ ] Answer quality scoring: compare RAG-augmented vs. standalone Claude answers

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

4. **Embedding model:** Upgraded from all-MiniLM-L6-v2 (384d, English-only) to BAAI/bge-m3 (1024d, 100+ languages). Supports EN, VN, and JP natively. Slower on CPU but significantly better retrieval quality (+10.9pp Recall@3).

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
