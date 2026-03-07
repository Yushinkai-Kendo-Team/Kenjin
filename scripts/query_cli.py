"""CLI tool for testing kendo knowledge retrieval.

Usage:
    python scripts/query_cli.py "What is zanshin?"
    python scripts/query_cli.py --interactive
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kendocenter.retrieval.pipeline import RetrievalPipeline


def query_once(pipeline: RetrievalPipeline, question: str) -> None:
    """Run a single query and display results."""
    result = pipeline.query(question)

    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}")

    if result.glossary_match:
        m = result.glossary_match
        kanji = f" ({m['term_kanji']})" if m.get("term_kanji") else ""
        print(f"\n📖 Glossary Match: {m['term_romaji']}{kanji}")
        print(f"   {m['definition'][:200]}")
        print(f"   [Category: {m.get('category', '')}]")

    if result.results:
        print(f"\n🔍 Semantic Search Results ({len(result.results)}):")
        for i, r in enumerate(result.results, 1):
            source = r.metadata.get("source", "?")
            doc_type = r.metadata.get("type", "?")
            relevance = 1 - r.distance
            print(f"\n   [{i}] {source} ({doc_type}) — relevance: {relevance:.2f}")
            # Show first 200 chars of text
            preview = r.text[:200].replace("\n", " ")
            print(f"       {preview}...")
    else:
        print("\n   No semantic search results found.")

    print(f"\n{'='*60}")
    print("Formatted prompt length:", len(result.formatted_prompt), "chars")
    print("(Use --prompt to see full prompt for Claude Code)")


def main():
    pipeline = RetrievalPipeline()

    if "--interactive" in sys.argv:
        print("YKC Kenjin CLI — Type 'quit' to exit")
        while True:
            try:
                question = input("\nAsk: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question.lower() in ("quit", "exit", "q"):
                break
            if question:
                query_once(pipeline, question)
    elif len(sys.argv) > 1:
        question = " ".join(
            a for a in sys.argv[1:] if not a.startswith("--")
        )
        if question:
            query_once(pipeline, question)

            if "--prompt" in sys.argv:
                result = pipeline.query(question)
                print("\n\n=== FULL PROMPT FOR CLAUDE CODE ===\n")
                print(result.formatted_prompt)
    else:
        print("Usage:")
        print("  python scripts/query_cli.py 'What is zanshin?'")
        print("  python scripts/query_cli.py --interactive")
        print("  python scripts/query_cli.py 'What is seme?' --prompt")


if __name__ == "__main__":
    main()
