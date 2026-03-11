"""Pure metric computation functions for RAG evaluation.

All functions are stateless and operate on pre-computed retrieval results.
"""

from __future__ import annotations


def recall_at_k(
    retrieved_keys: list[str],
    expected_keys: list[str],
    k: int,
) -> float:
    """Fraction of expected source keys found in top-k retrieved results.

    Args:
        retrieved_keys: Source keys from retrieval, ordered by rank.
        expected_keys: Ground-truth source keys that should appear.
        k: Cutoff rank.

    Returns:
        Recall score between 0.0 and 1.0. Returns 1.0 if expected_keys is empty
        (negative questions with no expected results).
    """
    if not expected_keys:
        return 1.0 if not retrieved_keys[:k] else 0.0
    top_k = set(retrieved_keys[:k])
    hits = sum(1 for key in expected_keys if key in top_k)
    return hits / len(expected_keys)


def mean_reciprocal_rank(
    retrieved_keys: list[str],
    expected_keys: list[str],
) -> float:
    """Reciprocal rank of the first relevant result.

    Args:
        retrieved_keys: Source keys from retrieval, ordered by rank.
        expected_keys: Ground-truth source keys that should appear.

    Returns:
        1/rank of first hit, or 0.0 if no expected key is found.
        Returns 1.0 if expected_keys is empty (negative question).
    """
    if not expected_keys:
        return 1.0 if not retrieved_keys else 0.0
    expected_set = set(expected_keys)
    for i, key in enumerate(retrieved_keys):
        if key in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def glossary_hit(
    glossary_match: dict | None,
    expected_term: str | None,
) -> bool | None:
    """Check if glossary exact-match lookup succeeded.

    Args:
        glossary_match: The glossary match dict from retriever (or None).
        expected_term: The expected term romaji (or None if not a glossary question).

    Returns:
        True/False for glossary questions, None for non-glossary questions.
    """
    if expected_term is None:
        return None
    if glossary_match is None:
        return False
    matched_term = glossary_match.get("term_romaji", "")
    return matched_term.lower() == expected_term.lower()


def keyword_recall(
    retrieved_texts: list[str],
    expected_keywords: list[str],
) -> float:
    """Fraction of expected keywords found in any retrieved text.

    Case-insensitive. A keyword is considered found if it appears as a
    substring in any of the retrieved texts.

    Args:
        retrieved_texts: Text content of retrieved chunks.
        expected_keywords: Keywords expected to appear in results.

    Returns:
        Recall score between 0.0 and 1.0. Returns 1.0 if no keywords expected.
    """
    if not expected_keywords:
        return 1.0
    combined = " ".join(retrieved_texts).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
    return hits / len(expected_keywords)
