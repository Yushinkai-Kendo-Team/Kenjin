"""Compare two evaluation result JSON files side-by-side.

Usage:
    python scripts/compare_models.py baseline.json current.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def compare(baseline_path: str, current_path: str) -> None:
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(current_path, encoding="utf-8") as f:
        current = json.load(f)

    print(f"\n{'=' * 65}")
    print(f"  Model Comparison: {baseline_path} vs {current_path}")
    print(f"{'=' * 65}")

    metrics = [
        ("Recall@3", "mean_recall_at_3"),
        ("Recall@5", "mean_recall_at_5"),
        ("Recall@8", "mean_recall_at_8"),
        ("MRR", "mean_mrr"),
        ("Glossary Hit", "glossary_hit_rate"),
        ("Keyword Recall", "mean_keyword_recall"),
    ]

    print(f"\n  Overall Metrics:")
    print(f"    {'Metric':<20} {'Baseline':>10} {'Current':>10} {'Delta':>10}")
    print(f"    {'-' * 20} {'-' * 10} {'-' * 10} {'-' * 10}")
    for label, key in metrics:
        b = baseline.get(key, 0)
        c = current.get(key, 0)
        delta = c - b
        sign = "+" if delta >= 0 else ""
        print(f"    {label:<20} {b:>10.4f} {c:>10.4f} {sign}{delta:>9.4f}")

    # By-category comparison
    base_cats = baseline.get("by_category", {})
    curr_cats = current.get("by_category", {})
    all_cats = sorted(set(list(base_cats.keys()) + list(curr_cats.keys())))

    if all_cats:
        print(f"\n  Recall@5 by Category:")
        print(f"    {'Category':<20} {'Baseline':>10} {'Current':>10} {'Delta':>10}")
        print(f"    {'-' * 20} {'-' * 10} {'-' * 10} {'-' * 10}")
        for cat in all_cats:
            b = base_cats.get(cat, {}).get("recall_at_5", 0)
            c = curr_cats.get(cat, {}).get("recall_at_5", 0)
            delta = c - b
            sign = "+" if delta >= 0 else ""
            print(f"    {cat:<20} {b:>10.4f} {c:>10.4f} {sign}{delta:>9.4f}")

    print(f"\n{'=' * 65}")


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/compare_models.py <baseline.json> <current.json>")
        sys.exit(1)
    compare(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
