"""Run RAG evaluation and print metrics report.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --verbose
    python scripts/run_eval.py --category glossary_lookup
    python scripts/run_eval.py --output results.json
    python scripts/run_eval.py --compare baseline.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from kendocenter.evaluation.runner import EvalRunner, EvalSummary


def print_report(summary: EvalSummary, verbose: bool = False) -> None:
    """Print a formatted evaluation report."""
    cats = summary.by_category
    cat_breakdown = ", ".join(f"{v.get('count', 0)} {k}" for k, v in cats.items())

    print(f"\n{'=' * 60}")
    print(f"  YSK Kenjin RAG Evaluation Report")
    print(f"{'=' * 60}")
    print(f"  Questions: {summary.total_questions} ({cat_breakdown})")
    print()
    print(f"  Overall Metrics:")
    print(f"    Recall@3:        {summary.mean_recall_at_3:.4f}")
    print(f"    Recall@5:        {summary.mean_recall_at_5:.4f}")
    print(f"    Recall@8:        {summary.mean_recall_at_8:.4f}")
    print(f"    MRR:             {summary.mean_mrr:.4f}")
    print(f"    Glossary Hit:    {summary.glossary_hit_rate:.4f}")
    print(f"    Keyword Recall:  {summary.mean_keyword_recall:.4f}")

    print(f"\n  By Category:")
    print(f"    {'Category':<20} {'R@3':>6} {'R@5':>6} {'R@8':>6} {'MRR':>6} {'KwR':>6} {'ms':>7}")
    print(f"    {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7}")
    for cat, m in sorted(cats.items()):
        print(f"    {cat:<20} {m['recall_at_3']:>6.2f} {m['recall_at_5']:>6.2f} "
              f"{m['recall_at_8']:>6.2f} {m['mrr']:>6.2f} {m['keyword_recall']:>6.2f} "
              f"{m['avg_elapsed_ms']:>7.1f}")

    if verbose:
        print(f"\n  Per-Question Detail:")
        print(f"    {'ID':<30} {'R@8':>5} {'MRR':>5} {'KwR':>5} {'Gloss':>5} {'#Res':>5} {'ms':>7}")
        print(f"    {'-'*30} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*7}")
        for r in summary.results:
            gloss_str = "  -  " if r.glossary_hit is None else (" yes " if r.glossary_hit else "  NO ")
            print(f"    {r.question_id:<30} {r.recall_at_8:>5.2f} {r.mrr:>5.2f} "
                  f"{r.keyword_recall:>5.2f} {gloss_str} {r.num_results:>5} {r.elapsed_ms:>7.1f}")

        # Show failures
        failures = [r for r in summary.results if r.recall_at_8 == 0 and r.category != "negative"]
        if failures:
            print(f"\n  Failures (Recall@8 = 0, non-negative):")
            for r in failures:
                print(f"    [{r.question_id}] \"{r.question}\"")
                print(f"      Retrieved: {r.retrieved_source_keys or 'none'}")

    print(f"\n{'=' * 60}")


def print_comparison(current: EvalSummary, baseline_path: str) -> None:
    """Compare current results with a saved baseline."""
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    print(f"\n  Comparison vs {baseline_path}:")
    print(f"    {'Metric':<20} {'Baseline':>10} {'Current':>10} {'Delta':>10}")
    print(f"    {'-'*20} {'-'*10} {'-'*10} {'-'*10}")

    metrics = [
        ("Recall@3", "mean_recall_at_3"),
        ("Recall@5", "mean_recall_at_5"),
        ("Recall@8", "mean_recall_at_8"),
        ("MRR", "mean_mrr"),
        ("Glossary Hit", "glossary_hit_rate"),
        ("Keyword Recall", "mean_keyword_recall"),
    ]
    for label, key in metrics:
        base_val = baseline.get(key, 0)
        curr_val = getattr(current, key, 0)
        delta = curr_val - base_val
        sign = "+" if delta >= 0 else ""
        print(f"    {label:<20} {base_val:>10.4f} {curr_val:>10.4f} {sign}{delta:>9.4f}")


def main():
    parser = argparse.ArgumentParser(description="YSK Kenjin RAG Evaluation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-question detail")
    parser.add_argument("--category", "-c", help="Run only this category")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    parser.add_argument("--compare", help="Compare with baseline JSON file")
    parser.add_argument("--dataset", help="Path to eval dataset YAML")
    args = parser.parse_args()

    print("Loading pipeline (embedding model)...")
    categories = [args.category] if args.category else None

    runner = EvalRunner(dataset_path=args.dataset)
    print(f"Dataset: {len(runner.questions)} questions")

    print("Running evaluation...")
    summary = runner.run(categories=categories)

    print_report(summary, verbose=args.verbose)

    if args.compare:
        print_comparison(summary, args.compare)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved to {args.output}")


if __name__ == "__main__":
    main()
