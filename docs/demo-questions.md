# Demo Questions

Quick reference for demonstrating YSK Kenjin's RAG capabilities. Questions are grouped by what they showcase.

## Glossary Lookup (exact term match + semantic results)

These trigger both a glossary definition and related passages:

```
What is zanshin?
```
- Glossary match + blog article about zanshin + glossary chunks
- Shows dual-store design: SQLite exact match + ChromaDB semantic search

```
What is kamae?
```
- Glossary match + related glossary entries (chudan-no-kamae, jodan, etc.)

```
What is debana waza?
```
- Glossary match for compound technique term

```
What is maai?
```
- Glossary match + related distance/timing entries

## Semantic Search (article retrieval)

These find relevant passages from kendo article translations:

```
How does Uchimura approach mental preparation?
```
- Retrieves from Uchimura Ryoichi interview articles (articles category)
- Shows article metadata: title, subject, publication, file path

```
How to improve footwork in kendo?
```
- Retrieves from Uchimura articles (training routine sections) + glossary terms

```
What is the role of kiai in kendo?
```
- Cross-references glossary definition with article passages about kiai in practice

## Blog Content (5 blog sources)

These demonstrate retrieval from scraped blog articles across 5 sources:

```
What is seme in kendo?
```
- Top results from kenshi247: "Imagining seme" (65%) and "The reality of seme" (60%)
- Also returns glossary definition of seme
- Best demo of English blog content retrieval

```
How to improve suburi?
```
- Retrieves from kenshi247 "Suburi: a brief discussion" (61 paragraphs)

```
What is shugyo?
```
- Retrieves from kenshi247 "Shugyo" and "The shugyo spiral" articles
- Also matches glossary definition

```
What is shu ha ri?
```
- Retrieves from Vietnamese blog article (kendo3ka) and kendoinfo "Explain shu ha ri"
- Shows blog category metadata and file path

```
What is ki ken tai ichi?
```
- Retrieves from blog article + glossary entries
- No exact glossary match (compound term), but semantic search finds relevant content

```
How to improve kendo footwork?
```
- Retrieves from nanseikan "Ashi sabaki - footwork" and kendoinfo articles
- Shows Blogspot content alongside WordPress content

```
What is the history of kendo?
```
- Retrieves from kendophilosophy "The history of kendo" (98 paragraphs)
- Long-form historical content from philosophy-focused blog

```
What is tenouchi?
```
- Retrieves from nanseikan "Tenouchi - the grip" and kendoinfo grip articles
- Shows cross-blog retrieval for the same topic

## Cross-Source Retrieval

These pull results from multiple source categories simultaneously:

```
Explain zanshin in kendo practice
```
- Returns results from kenshi247 ("Zanshin confusion, sutemi, and hikiage"), articles, AND glossary
- Best demo of cross-source retrieval across 3 categories

```
Explain seme in kendo
```
- Glossary entries + kenshi247 seme articles + contextual usage from various sources

```
What is the kendo lifecycle?
```
- Retrieves from kenshi247 "The kendo lifecycle" article
- Shows how long-form English articles are chunked and retrieved

## Language Filter

Test the Vietnamese content filter via API:

```bash
# API call with language filter
curl -X POST http://localhost:8001/api/search \
  -H "Content-Type: application/json" \
  -d '{"question": "Uchimura Ryoichi kendo", "n_results": 5, "language": "vn"}'
```
- Returns only Vietnamese-tagged chunks (lang=vn)
- Articles have both EN and VN sections, filter isolates Vietnamese content

## CLI Quick Test

```bash
# Single query
python scripts/query_cli.py "What is zanshin?"

# With full prompt output (shows the formatted prompt for Claude)
python scripts/query_cli.py --prompt "Explain zanshin in kendo practice"

# Interactive mode
python scripts/query_cli.py --interactive
```

## API Quick Test

```bash
# Start server (set PYTHONPATH first — see README for OS-specific syntax)
set PYTHONPATH=src            & REM Windows
# export PYTHONPATH=src       # macOS / Linux
python -m uvicorn kendocenter.main:app --port 8001

# Health check
curl http://localhost:8001/api/health

# Search
curl -X POST http://localhost:8001/api/search \
  -H "Content-Type: application/json" \
  -d '{"question": "What is zanshin?", "n_results": 5}'

# Browse glossary
curl "http://localhost:8001/api/terms?query=kamae&limit=5"

# Term detail
curl http://localhost:8001/api/terms/Zanshin
```

## What to Highlight During Demo

1. **Dual-store design**: "What is zanshin?" shows both exact glossary match AND semantic search results
2. **Source citations**: Every result includes source file, category, and file path
3. **Cross-source**: A single query can retrieve from glossary, articles, and blogs
4. **Formatted prompts**: The system builds ready-to-paste prompts with kendo-specific instructions (preserves Japanese terms, includes citations)
5. **Language filter**: Vietnamese content can be isolated with `language: "vn"`
6. **Knowledge base stats**: 395 glossary terms, 139 sources (1 glossary + 4 articles + 14 kendo3ka + 47 kenshi247 + 52 kendoinfo + 11 nanseikan + 10 kendophilosophy blogs), 693 chunks across 4 categories
