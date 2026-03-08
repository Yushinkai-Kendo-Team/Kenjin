"""Kendo-specific system prompt and context formatting.

Builds prompts for use with Claude Code (copy-paste) or Claude API.
"""

from __future__ import annotations

from kendocenter.storage.models import SearchResult

KENDO_SYSTEM_PROMPT = """You are YSK Kenjin, an expert AI assistant specialized in Kendo (Japanese sword martial art — 剣道).

Your role:
- Answer questions about kendo terminology, techniques, philosophy, training methods, competition rules, and equipment.
- Always use correct kendo terminology. Preserve Japanese terms — do NOT translate them to English equivalents.
- When referencing techniques, include both romaji and kanji where available.
- Cite your sources using [Source: filename] notation.
- If the provided context doesn't contain the answer, say so honestly. Do NOT make up information.

Important terminology rules:
- "Men" = the head strike/target and head protector, NEVER translate as "face" or "mask"
- "Kote" = the wrist/forearm strike/target and protective gloves
- "Dō" = the torso strike/target and body protector
- "Tsuki" = the throat thrust
- "Kamae" = guard/stance, not just "position"
- "Keiko" = training/practice
- "Sensei" = teacher/instructor, preserve as-is
- "Ippon" = a valid point in competition
- "Maai" = combative distance/interval, much more than "distance"
- "Seme" = pressure/initiative/offense — a deep concept beyond "attack"
- "Zanshin" = continuing awareness/alertness after striking
- "Ki-ken-tai-itchi" = unity of spirit, sword, and body
- "Waza" = technique(s)
- "Suburi" = solo practice swings
- "Shinai" = bamboo practice sword, not "stick"
- "Bōgu" = kendo armor/equipment

Always maintain the dignity and philosophical depth of kendo in your responses."""


def format_context(
    results: list[SearchResult],
    glossary_match: dict | None = None,
) -> str:
    """Format retrieved results into a context block for the LLM.

    Uses resolved metadata (source filename, title, file_path) from the retriever.
    """
    parts = []

    # Glossary exact match first (if any)
    if glossary_match:
        kanji = f" ({glossary_match['term_kanji']})" if glossary_match.get("term_kanji") else ""
        parts.append(
            f"GLOSSARY ENTRY:\n"
            f"{glossary_match['term_romaji']}{kanji}: {glossary_match['definition']}\n"
            f"Category: {glossary_match.get('category', 'general')}\n"
            f"[Source: Glossary.pdf]"
        )

    # Semantic search results
    for i, result in enumerate(results, 1):
        source = result.metadata.get("source", "unknown")
        doc_type = result.metadata.get("type", "unknown")
        language = result.metadata.get("language", "en")
        file_path = result.metadata.get("file_path", "")
        relevance = f"(relevance: {1 - result.distance:.2f})" if result.distance else ""

        source_ref = f"[{source}]"
        if file_path:
            source_ref = f"[{source} ({file_path})]"

        header = f"SOURCE {i} {source_ref} ({doc_type}, {language}) {relevance}"
        parts.append(f"{header}:\n{result.text}")

    return "\n\n---\n\n".join(parts) if parts else "(No relevant context found)"


def build_prompt(
    query: str,
    results: list[SearchResult],
    glossary_match: dict | None = None,
) -> str:
    """Build a complete prompt with system instruction, context, and question.

    This prompt can be:
    - Copied into Claude Code for manual use (Phase 1)
    - Sent to Claude API programmatically (Phase 2+)
    """
    context = format_context(results, glossary_match)

    return (
        f"{KENDO_SYSTEM_PROMPT}\n\n"
        f"---\n\n"
        f"Based on the following kendo knowledge sources, answer the question. "
        f"Always cite your sources. If the sources don't contain enough information, "
        f"say so clearly.\n\n"
        f"RETRIEVED CONTEXT:\n{context}\n\n"
        f"QUESTION: {query}"
    )
