"""Evaluation runner: loads dataset, runs queries, computes metrics.

Usage:
    from kendocenter.evaluation.runner import EvalRunner
    runner = EvalRunner()               # uses default pipeline & dataset
    summary = runner.run()              # run all questions
    summary = runner.run(categories=["glossary_lookup"])  # subset
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from kendocenter.config import settings
from kendocenter.retrieval.pipeline import RetrievalPipeline
from kendocenter.evaluation.metrics import (
    recall_at_k,
    mean_reciprocal_rank,
    glossary_hit,
    keyword_recall,
)


@dataclass
class EvalQuestion:
    """A single question from the evaluation dataset."""

    id: str
    question: str
    category: str
    expected_glossary_term: str | None = None
    expected_source_keys: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    language: str | None = None
    difficulty: str = "medium"


@dataclass
class EvalResult:
    """Per-question evaluation result."""

    question_id: str
    question: str
    category: str
    difficulty: str
    recall_at_3: float
    recall_at_5: float
    recall_at_8: float
    mrr: float
    glossary_hit: bool | None
    keyword_recall: float
    retrieved_source_keys: list[str]
    num_results: int
    elapsed_ms: float


@dataclass
class EvalSummary:
    """Aggregated evaluation results."""

    total_questions: int
    mean_recall_at_3: float
    mean_recall_at_5: float
    mean_recall_at_8: float
    mean_mrr: float
    glossary_hit_rate: float
    mean_keyword_recall: float
    by_category: dict[str, dict[str, Any]]
    results: list[EvalResult]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        d = {
            "config": {
                "embedding_model": settings.embedding_model,
                "hybrid_enabled": settings.hybrid_enabled,
                "reranker_enabled": settings.reranker_enabled,
                "fuzzy_enabled": settings.fuzzy_enabled,
            },
            "total_questions": self.total_questions,
            "mean_recall_at_3": round(self.mean_recall_at_3, 4),
            "mean_recall_at_5": round(self.mean_recall_at_5, 4),
            "mean_recall_at_8": round(self.mean_recall_at_8, 4),
            "mean_mrr": round(self.mean_mrr, 4),
            "glossary_hit_rate": round(self.glossary_hit_rate, 4),
            "mean_keyword_recall": round(self.mean_keyword_recall, 4),
            "by_category": self.by_category,
            "results": [asdict(r) for r in self.results],
        }
        return d


def load_dataset(path: str | Path | None = None) -> list[EvalQuestion]:
    """Load evaluation questions from YAML file."""
    path = Path(path or settings.eval_dataset_path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    questions = []
    for q in data.get("questions", []):
        questions.append(EvalQuestion(
            id=q["id"],
            question=q["question"],
            category=q["category"],
            expected_glossary_term=q.get("expected_glossary_term"),
            expected_source_keys=q.get("expected_source_keys", []),
            expected_keywords=q.get("expected_keywords", []),
            language=q.get("language"),
            difficulty=q.get("difficulty", "medium"),
        ))
    return questions


class EvalRunner:
    """Runs evaluation queries and computes metrics."""

    def __init__(
        self,
        pipeline: RetrievalPipeline | None = None,
        dataset_path: str | Path | None = None,
    ):
        self.pipeline = pipeline or RetrievalPipeline()
        self.questions = load_dataset(dataset_path)

    def _evaluate_one(self, q: EvalQuestion) -> EvalResult:
        """Run a single evaluation question."""
        start = time.perf_counter()
        result = self.pipeline.query(
            q.question,
            n_results=8,
            language=q.language,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Extract source keys from results
        retrieved_keys = []
        for r in result.results:
            src_key = r.metadata.get("source_key", r.metadata.get("src", ""))
            if src_key:
                retrieved_keys.append(src_key)

        retrieved_texts = [r.text for r in result.results]

        return EvalResult(
            question_id=q.id,
            question=q.question,
            category=q.category,
            difficulty=q.difficulty,
            recall_at_3=recall_at_k(retrieved_keys, q.expected_source_keys, 3),
            recall_at_5=recall_at_k(retrieved_keys, q.expected_source_keys, 5),
            recall_at_8=recall_at_k(retrieved_keys, q.expected_source_keys, 8),
            mrr=mean_reciprocal_rank(retrieved_keys, q.expected_source_keys),
            glossary_hit=glossary_hit(result.glossary_match, q.expected_glossary_term),
            keyword_recall=keyword_recall(retrieved_texts, q.expected_keywords),
            num_results=len(result.results),
            retrieved_source_keys=retrieved_keys,
            elapsed_ms=round(elapsed_ms, 1),
        )

    def run(
        self,
        categories: list[str] | None = None,
    ) -> EvalSummary:
        """Run evaluation on all (or filtered) questions.

        Args:
            categories: If provided, only run questions in these categories.

        Returns:
            EvalSummary with per-question and aggregate metrics.
        """
        questions = self.questions
        if categories:
            questions = [q for q in questions if q.category in categories]

        results: list[EvalResult] = []
        for q in questions:
            results.append(self._evaluate_one(q))

        return self._summarize(results)

    def _summarize(self, results: list[EvalResult]) -> EvalSummary:
        """Compute aggregate metrics from per-question results."""
        n = len(results)
        if n == 0:
            return EvalSummary(
                total_questions=0,
                mean_recall_at_3=0, mean_recall_at_5=0, mean_recall_at_8=0,
                mean_mrr=0, glossary_hit_rate=0, mean_keyword_recall=0,
                by_category={}, results=[],
            )

        # Overall metrics
        glossary_results = [r for r in results if r.glossary_hit is not None]
        glossary_hit_rate = (
            sum(1 for r in glossary_results if r.glossary_hit) / len(glossary_results)
            if glossary_results else 0.0
        )

        # By-category breakdown
        categories: dict[str, list[EvalResult]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r)

        by_category = {}
        for cat, cat_results in sorted(categories.items()):
            cat_n = len(cat_results)
            cat_glossary = [r for r in cat_results if r.glossary_hit is not None]
            by_category[cat] = {
                "count": cat_n,
                "recall_at_3": round(sum(r.recall_at_3 for r in cat_results) / cat_n, 4),
                "recall_at_5": round(sum(r.recall_at_5 for r in cat_results) / cat_n, 4),
                "recall_at_8": round(sum(r.recall_at_8 for r in cat_results) / cat_n, 4),
                "mrr": round(sum(r.mrr for r in cat_results) / cat_n, 4),
                "keyword_recall": round(sum(r.keyword_recall for r in cat_results) / cat_n, 4),
                "glossary_hit_rate": round(
                    sum(1 for r in cat_glossary if r.glossary_hit) / len(cat_glossary), 4
                ) if cat_glossary else None,
                "avg_elapsed_ms": round(sum(r.elapsed_ms for r in cat_results) / cat_n, 1),
            }

        return EvalSummary(
            total_questions=n,
            mean_recall_at_3=round(sum(r.recall_at_3 for r in results) / n, 4),
            mean_recall_at_5=round(sum(r.recall_at_5 for r in results) / n, 4),
            mean_recall_at_8=round(sum(r.recall_at_8 for r in results) / n, 4),
            mean_mrr=round(sum(r.mrr for r in results) / n, 4),
            glossary_hit_rate=round(glossary_hit_rate, 4),
            mean_keyword_recall=round(sum(r.keyword_recall for r in results) / n, 4),
            by_category=by_category,
            results=results,
        )
