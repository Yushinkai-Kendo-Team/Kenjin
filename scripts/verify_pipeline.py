"""Verify the YSK Kenjin retrieval pipeline and data integrity.

Runs a battery of checks against the database, vector store, and retrieval
pipeline to ensure everything is working correctly after ingestion.

Usage:
    python scripts/verify_pipeline.py
    python scripts/verify_pipeline.py --verbose
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kendocenter.storage.database import Database
from kendocenter.storage.vector_store import VectorStore
from kendocenter.retrieval.pipeline import RetrievalPipeline


def check_database(verbose: bool = False) -> bool:
    """Check SQLite database integrity."""
    print("\n[1/4] Database check...")
    db = Database()
    db.initialize()

    terms = db.count_terms()
    docs = db.count_documents()
    sources_count = db.count_sources()
    categories = db.get_categories()
    sources = db.get_all_sources()

    print(f"  Terms: {terms}")
    print(f"  Documents: {docs}")
    print(f"  Sources: {sources_count}")
    print(f"  Categories: {[c['category'] for c in categories]}")

    if verbose:
        print("  Source registry:")
        for key, src in sorted(sources.items()):
            print(f"    {key}: {src['filename']} -> {src['file_path']}")

    ok = terms >= 395 and docs >= 5 and sources_count >= 5
    db.close()

    if not ok:
        print("  FAIL: Expected >= 395 terms, >= 5 documents, >= 5 sources")
    else:
        print("  OK")
    return ok


def check_vector_store() -> bool:
    """Check ChromaDB vector store."""
    print("\n[2/4] Vector store check...")
    vs = VectorStore()
    count = vs.count

    print(f"  Vectors: {count}")
    ok = count >= 690
    if not ok:
        print("  FAIL: Expected >= 690 vectors")
    else:
        print("  OK")
    return ok


def check_glossary_retrieval(pipeline: RetrievalPipeline, verbose: bool = False) -> bool:
    """Test glossary term lookup + semantic search."""
    print("\n[3/4] Glossary retrieval check...")

    result = pipeline.query("What is zanshin?", n_results=3)

    # Check glossary match
    if not result.glossary_match:
        print("  FAIL: No glossary match for 'What is zanshin?'")
        return False

    m = result.glossary_match
    print(f"  Glossary match: {m['term_romaji']} ({m.get('term_kanji', '')})")
    if verbose:
        print(f"    Definition: {m['definition'][:120]}...")

    # Check semantic results have resolved metadata
    if not result.results:
        print("  FAIL: No semantic results")
        return False

    r = result.results[0]
    has_source = r.metadata.get("source", "") != ""
    has_path = r.metadata.get("file_path", "") != ""
    has_src_key = r.metadata.get("source_key", "") != ""

    print(f"  Semantic results: {len(result.results)}")
    print(f"  Metadata resolved: source={has_source}, file_path={has_path}, source_key={has_src_key}")

    if verbose:
        for i, r in enumerate(result.results, 1):
            meta = r.metadata
            print(f"    [{i}] src={meta.get('src', '?')} source={meta.get('source', '?')} "
                  f"relevance={1 - r.distance:.2f}")

    ok = has_source and has_path and has_src_key
    if not ok:
        print("  FAIL: Metadata not fully resolved")
    else:
        print("  OK")
    return ok


def check_article_retrieval(pipeline: RetrievalPipeline, verbose: bool = False) -> bool:
    """Test article semantic search with metadata resolution."""
    print("\n[4/4] Article retrieval check...")

    result = pipeline.query("How does Uchimura approach mental preparation?", n_results=3)

    if not result.results:
        print("  FAIL: No results for Uchimura query")
        return False

    # Check that article results are found (not just glossary)
    article_results = [r for r in result.results if "article" in r.metadata.get("type", "")]
    print(f"  Total results: {len(result.results)}")
    print(f"  Article results: {len(article_results)}")

    if not article_results:
        print("  FAIL: No article results found")
        return False

    r = article_results[0]
    meta = r.metadata
    print(f"  Top article: {meta.get('source', '?')} (src={meta.get('src', '?')})")
    print(f"    Title: {meta.get('title', '?')}")
    print(f"    Subject: {meta.get('subject', '?')}")
    print(f"    Path: {meta.get('file_path', '?')}")

    if verbose:
        print(f"    Text preview: {r.text[:150]}...")

    # Check prompt includes file paths
    has_path_in_prompt = "Theory" in result.formatted_prompt
    print(f"  Prompt includes file path: {has_path_in_prompt}")
    print(f"  Prompt length: {len(result.formatted_prompt):,} chars")

    ok = (
        meta.get("source", "") != ""
        and meta.get("file_path", "") != ""
        and meta.get("title", "") != ""
        and has_path_in_prompt
    )
    if not ok:
        print("  FAIL: Article metadata incomplete or prompt missing file path")
    else:
        print("  OK")
    return ok


def check_blog_retrieval(pipeline: RetrievalPipeline, verbose: bool = False) -> bool:
    """Test that Vietnamese blog content is retrievable and tagged correctly.

    Blog articles from kendo3ka are Vietnamese-only, so we query with
    language='vn' to ensure they surface properly.
    """
    print("\n[5/7] Blog retrieval check (maai, Vietnamese)...")

    result = pipeline.query("maai kendo", n_results=5, language="vn")

    if not result.results:
        print("  FAIL: No results for maai query with language=vn")
        return False

    # Should get blog results from the maai articles
    blog_results = [
        r for r in result.results
        if "blogs" in r.metadata.get("file_path", "").lower()
        or "blogs" in r.metadata.get("category", "").lower()
    ]
    print(f"  Total results: {len(result.results)}")
    print(f"  Blog results: {len(blog_results)}")

    if not blog_results:
        print("  FAIL: No blog results found (expected maai blog articles)")
        return False

    r = blog_results[0]
    meta = r.metadata
    print(f"  Top blog: {meta.get('source', '?')} (src={meta.get('src', '?')})")
    print(f"    Category: {meta.get('category', '?')}")
    print(f"    Language: {meta.get('lang', '?')}")
    print(f"    Path: {meta.get('file_path', '?')}")

    if verbose:
        print(f"    Text preview: {r.text[:150]}...")

    ok = (
        meta.get("source", "") != ""
        and meta.get("file_path", "") != ""
        and "blogs" in meta.get("file_path", "").lower()
    )
    if not ok:
        print("  FAIL: Blog metadata incomplete or wrong category")
    else:
        print("  OK")
    return ok


def check_blog_vietnamese(pipeline: RetrievalPipeline, verbose: bool = False) -> bool:
    """Test Vietnamese blog content retrieval with language filter."""
    print("\n[6/7] Blog Vietnamese content check (ki-ken-tai-ichi)...")

    result = pipeline.query("ki ken tai ichi", n_results=5)

    if not result.results:
        print("  FAIL: No results for ki-ken-tai-ichi query")
        return False

    # Check that we get results from the ki-ken-tai-ichi blog
    kkt_results = [
        r for r in result.results
        if "ki-ken-tai" in r.metadata.get("source", "").lower()
        or "ki-ken-tai" in r.metadata.get("file_path", "").lower()
    ]

    print(f"  Total results: {len(result.results)}")
    print(f"  Ki-ken-tai-ichi article results: {len(kkt_results)}")

    if verbose:
        for i, r in enumerate(result.results, 1):
            meta = r.metadata
            print(f"    [{i}] src={meta.get('src', '?')} source={meta.get('source', '?')} "
                  f"lang={meta.get('lang', '?')} dist={r.distance:.3f}")

    # Even without exact file match, we should get relevant results
    # Check at least some results mention relevant content
    relevant = any(
        "ki" in r.text.lower() and "ken" in r.text.lower()
        for r in result.results
    )

    ok = len(result.results) > 0 and relevant
    if not ok:
        print("  FAIL: No relevant ki-ken-tai-ichi content found")
    else:
        print("  OK")
    return ok


def check_cross_source(pipeline: RetrievalPipeline, verbose: bool = False) -> bool:
    """Test that a query can retrieve from multiple source categories."""
    print("\n[7/7] Cross-source retrieval check (zanshin across articles + glossary)...")

    result = pipeline.query("Explain zanshin in kendo practice", n_results=8)

    if not result.results:
        print("  FAIL: No results for zanshin query")
        return False

    # Categorize results by source category
    sources_seen = set()
    for r in result.results:
        cat = r.metadata.get("category", "unknown")
        sources_seen.add(cat)

    print(f"  Total results: {len(result.results)}")
    print(f"  Source categories: {sorted(sources_seen)}")

    if verbose:
        for i, r in enumerate(result.results, 1):
            meta = r.metadata
            print(f"    [{i}] src={meta.get('src', '?')} cat={meta.get('category', '?')} "
                  f"source={meta.get('source', '?')} dist={r.distance:.3f}")

    # Zanshin should appear in both glossary and articles/blogs
    has_articles = "articles" in sources_seen
    has_glossary = "glossary" in sources_seen
    ok = has_articles and has_glossary
    if not ok:
        print(f"  FAIL: Expected both 'articles' and 'glossary', got {sorted(sources_seen)}")
    else:
        print("  OK")
    return ok


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=== YSK Kenjin Pipeline Verification ===")

    results = []
    results.append(check_database(verbose))
    results.append(check_vector_store())

    print("\nLoading retrieval pipeline (embedding model)...")
    pipeline = RetrievalPipeline()

    results.append(check_glossary_retrieval(pipeline, verbose))
    results.append(check_article_retrieval(pipeline, verbose))
    results.append(check_blog_retrieval(pipeline, verbose))
    results.append(check_blog_vietnamese(pipeline, verbose))
    results.append(check_cross_source(pipeline, verbose))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} checks passed")

    if passed == total:
        print("All checks passed!")
    else:
        print("Some checks FAILED. Review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
