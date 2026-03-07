"""Verify the YKC Kenjin FastAPI endpoints.

Starts the server, runs API checks, then stops the server.

Usage:
    python scripts/verify_api.py
    python scripts/verify_api.py --verbose
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8001"
PROJECT_DIR = Path(__file__).parent.parent
PYTHON = str(PROJECT_DIR / ".venv" / "Scripts" / "python.exe")
SERVER_STARTUP_TIMEOUT = 30
SERVER_POLL_INTERVAL = 1


def start_server():
    """Start uvicorn server in background, return the process."""
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "kendocenter.main:app", "--port", "8001"],
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def wait_for_server():
    """Wait until the server responds to requests."""
    for _ in range(SERVER_STARTUP_TIMEOUT):
        try:
            req = urllib.request.Request(f"{BASE_URL}/")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(SERVER_POLL_INTERVAL)
    return False


def warmup_search():
    """Send a throwaway search to trigger embedding model loading."""
    print("  Warming up search endpoint (loading embedding model)...")
    try:
        payload = json.dumps({"question": "test", "n_results": 1}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/search",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120):
            return True
    except (urllib.error.URLError, ConnectionError, OSError, TimeoutError):
        return False


def stop_server(proc):
    """Stop the server process."""
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def api_get(path):
    """Make a GET request and return (status_code, json_body)."""
    req = urllib.request.Request(f"{BASE_URL}{path}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return e.code, body


def api_post(path, data):
    """Make a POST request and return (status_code, json_body)."""
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return e.code, body


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_root(verbose):
    """GET / — returns app name and version."""
    print("\n[1/9] GET / ...")
    status, body = api_get("/")
    ok = status == 200 and body.get("name") == "YKC Kenjin"
    print(f"  Status: {status}, name={body.get('name')}, version={body.get('version')}")
    if verbose:
        print(f"  Body: {json.dumps(body, indent=2)}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_health(verbose):
    """GET /api/health — returns term/doc/vector counts."""
    print("\n[2/9] GET /api/health ...")
    status, body = api_get("/api/health")
    terms = body.get("glossary_terms", 0)
    docs = body.get("documents", 0)
    vectors = body.get("vector_store_entries", 0)
    ok = status == 200 and terms >= 395 and docs >= 5 and vectors >= 690
    print(f"  Status: {status}")
    print(f"  Terms: {terms}, Documents: {docs}, Vectors: {vectors}")
    if verbose:
        print(f"  Body: {json.dumps(body, indent=2)}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_terms_list(verbose):
    """GET /api/terms?query=kamae — returns matching terms."""
    print("\n[3/9] GET /api/terms?query=kamae ...")
    status, body = api_get("/api/terms?query=kamae&limit=5")
    items = body.get("items", [])
    total = body.get("total", 0)
    ok = status == 200 and len(items) > 0 and total >= 395
    print(f"  Status: {status}, matched: {len(items)}, total: {total}")
    if verbose and items:
        for item in items:
            print(f"    - {item.get('term_romaji', '?')}: {item.get('definition', '?')[:80]}...")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_term_detail(verbose):
    """GET /api/terms/Zanshin — returns specific term."""
    print("\n[4/9] GET /api/terms/Zanshin ...")
    status, body = api_get("/api/terms/Zanshin")
    has_term = body.get("term_romaji", "").lower() == "zanshin"
    has_kanji = bool(body.get("term_kanji", ""))
    has_def = bool(body.get("definition", ""))
    ok = status == 200 and has_term and has_kanji and has_def
    print(f"  Status: {status}")
    print(f"  Term: {body.get('term_romaji', '?')} ({body.get('term_kanji', '?')})")
    if verbose:
        print(f"  Definition: {body.get('definition', '?')[:120]}...")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_search_glossary(verbose):
    """POST /api/search — glossary query with metadata resolution."""
    print("\n[5/9] POST /api/search (glossary query) ...")
    status, body = api_post("/api/search", {"question": "What is zanshin?", "n_results": 3})
    glossary = body.get("glossary_match")
    results = body.get("results", [])
    prompt = body.get("formatted_prompt", "")

    has_glossary = glossary is not None and "zanshin" in glossary.get("term_romaji", "").lower()
    has_results = len(results) > 0
    has_prompt = len(prompt) > 100

    # Check metadata resolution in results
    meta_resolved = False
    if results:
        meta = results[0].get("metadata", {})
        meta_resolved = bool(meta.get("source")) and bool(meta.get("source_key"))

    ok = status == 200 and has_glossary and has_results and has_prompt and meta_resolved
    print(f"  Status: {status}")
    print(f"  Glossary match: {glossary.get('term_romaji', '?') if glossary else 'None'}")
    print(f"  Semantic results: {len(results)}, metadata resolved: {meta_resolved}")
    print(f"  Prompt length: {len(prompt):,} chars")
    if verbose and results:
        for i, r in enumerate(results, 1):
            m = r.get("metadata", {})
            print(f"    [{i}] src={m.get('src', '?')} source={m.get('source', '?')} "
                  f"distance={r.get('distance', 0):.3f}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_search_article(verbose):
    """POST /api/search — article query with file_path in results."""
    print("\n[6/9] POST /api/search (article query) ...")
    status, body = api_post(
        "/api/search",
        {"question": "How does Uchimura approach mental preparation?", "n_results": 3},
    )
    results = body.get("results", [])
    prompt = body.get("formatted_prompt", "")

    article_results = [
        r for r in results if "article" in r.get("metadata", {}).get("type", "")
    ]
    has_articles = len(article_results) > 0

    # Check file_path is present
    has_path = False
    if article_results:
        has_path = bool(article_results[0].get("metadata", {}).get("file_path", ""))

    # Check prompt contains file path reference
    has_path_in_prompt = "Theory" in prompt

    ok = status == 200 and has_articles and has_path and has_path_in_prompt
    print(f"  Status: {status}")
    print(f"  Total results: {len(results)}, article results: {len(article_results)}")
    if article_results:
        m = article_results[0].get("metadata", {})
        print(f"  Top article: {m.get('source', '?')} (src={m.get('src', '?')})")
        print(f"  File path: {m.get('file_path', '?')}")
    print(f"  Prompt includes file path: {has_path_in_prompt}")
    if verbose:
        print(f"  Prompt length: {len(prompt):,} chars")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_search_blog(verbose):
    """POST /api/search — Vietnamese blog content retrieval (maai query)."""
    print("\n[7/9] POST /api/search (blog query: maai, Vietnamese) ...")
    # Blog articles are Vietnamese-only, so use language filter
    status, body = api_post(
        "/api/search",
        {"question": "maai kendo", "n_results": 5, "language": "vn"},
    )
    results = body.get("results", [])

    blog_results = [
        r for r in results
        if "blogs" in r.get("metadata", {}).get("file_path", "").lower()
    ]
    has_blogs = len(blog_results) > 0

    ok = status == 200 and has_blogs
    print(f"  Status: {status}")
    print(f"  Total results: {len(results)}, blog results: {len(blog_results)}")
    if blog_results:
        m = blog_results[0].get("metadata", {})
        print(f"  Top blog: {m.get('source', '?')} (src={m.get('src', '?')})")
        print(f"  Category: {m.get('category', '?')}")
    if verbose:
        for i, r in enumerate(results, 1):
            m = r.get("metadata", {})
            print(f"    [{i}] src={m.get('src', '?')} cat={m.get('category', '?')} "
                  f"source={m.get('source', '?')} dist={r.get('distance', 0):.3f}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_search_cross_source(verbose):
    """POST /api/search — cross-source retrieval (zanshin across articles + glossary)."""
    print("\n[8/9] POST /api/search (cross-source: zanshin) ...")
    status, body = api_post(
        "/api/search",
        {"question": "Explain zanshin in kendo practice", "n_results": 8},
    )
    results = body.get("results", [])

    categories = set()
    for r in results:
        cat = r.get("metadata", {}).get("category", "")
        if cat:
            categories.add(cat)

    has_articles = "articles" in categories
    has_glossary = "glossary" in categories

    ok = status == 200 and has_articles and has_glossary
    print(f"  Status: {status}")
    print(f"  Total results: {len(results)}")
    print(f"  Source categories: {sorted(categories)}")
    if verbose:
        for i, r in enumerate(results, 1):
            m = r.get("metadata", {})
            print(f"    [{i}] src={m.get('src', '?')} cat={m.get('category', '?')} "
                  f"source={m.get('source', '?')} dist={r.get('distance', 0):.3f}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def check_search_language_filter(verbose):
    """POST /api/search — language filter returns only matching results."""
    print("\n[9/9] POST /api/search (language filter: vn) ...")
    # Use "Uchimura" — the original articles have both EN and VN sections
    # Note: chunks use "vn" (not "vi") as the language code
    status, body = api_post(
        "/api/search",
        {"question": "Uchimura Ryoichi kendo", "n_results": 5, "language": "vn"},
    )
    results = body.get("results", [])

    # All results should have lang=vn (or type containing _vn)
    all_vi = all(
        r.get("metadata", {}).get("lang") == "vn"
        or "_vn" in r.get("metadata", {}).get("type", "")
        for r in results
    ) if results else False

    ok = status == 200 and len(results) > 0 and all_vi
    print(f"  Status: {status}")
    print(f"  Results: {len(results)}, all Vietnamese: {all_vi}")
    if verbose:
        for i, r in enumerate(results, 1):
            m = r.get("metadata", {})
            print(f"    [{i}] src={m.get('src', '?')} lang={m.get('lang', '?')} "
                  f"type={m.get('type', '?')} source={m.get('source', '?')}")
    print(f"  {'OK' if ok else 'FAIL'}")
    return ok


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=== YKC Kenjin API Verification ===")

    # Start server
    print("\nStarting FastAPI server on port 8001...")
    proc = start_server()

    try:
        if not wait_for_server():
            print("FAIL: Server did not start within timeout.")
            stop_server(proc)
            sys.exit(1)

        print("Server is ready.")

        # Warm up the search endpoint (triggers embedding model loading)
        if not warmup_search():
            print("FAIL: Search warmup timed out (embedding model failed to load).")
            stop_server(proc)
            sys.exit(1)
        print("  Search endpoint warmed up.")

        # Run checks
        results = []
        results.append(check_root(verbose))
        results.append(check_health(verbose))
        results.append(check_terms_list(verbose))
        results.append(check_term_detail(verbose))
        results.append(check_search_glossary(verbose))
        results.append(check_search_article(verbose))
        results.append(check_search_blog(verbose))
        results.append(check_search_cross_source(verbose))
        results.append(check_search_language_filter(verbose))

        # Summary
        passed = sum(results)
        total = len(results)
        print(f"\n{'=' * 40}")
        print(f"Results: {passed}/{total} checks passed")

        if passed == total:
            print("All API checks passed!")
        else:
            print("Some checks FAILED. Review output above.")

    finally:
        # Always stop server
        print("\nStopping server...")
        stop_server(proc)
        print("Server stopped.")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
