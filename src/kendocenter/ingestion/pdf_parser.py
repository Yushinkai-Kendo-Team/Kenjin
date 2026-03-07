"""Parse Glossary.pdf into structured kendo term entries.

The glossary is a LaTeX-generated two-column PDF. Standard text extraction
produces concatenated words, so we use character-level extraction with gap
analysis. We split each page into left/right columns before parsing to avoid
cross-column contamination.

Font identification:
- NotoSansDisplay-Regular: term names (romaji)
- NotoSansJP-Light: Japanese characters (kanji/kana)
- Pali-Bold: section/letter headers
- Pali-Italic: quoted translations
- Pali: definition body text
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass
class GlossaryEntry:
    """A single glossary term with its components."""

    term_romaji: str
    term_kanji: str = ""
    definition: str = ""
    category: str = ""
    source: str = "Glossary.pdf"

    def to_chunk_text(self) -> str:
        """Format as a single text chunk for embedding."""
        parts = [self.term_romaji]
        if self.term_kanji:
            parts[0] += f" ({self.term_kanji})"
        if self.definition:
            parts.append(self.definition)
        if self.category:
            parts.append(f"[Category: {self.category}]")
        return " — ".join(parts)


# Column boundary: left column x < 305, right column x >= 305
# All pages use two-column layout (intro text on page 1 falls in left column)
COLUMN_SPLIT_X = 305.0


def _reconstruct_column_text(
    chars: list[dict], y_tolerance: float = 5, space_threshold: float = 2.0
) -> str:
    """Reconstruct text from a set of characters with proper word spacing."""
    if not chars:
        return ""

    sorted_chars = sorted(chars, key=lambda c: (c["top"], c["x0"]))

    # Group into lines by y-proximity
    lines: list[list[dict]] = []
    current_line = [sorted_chars[0]]

    for c in sorted_chars[1:]:
        if abs(c["top"] - current_line[0]["top"]) <= y_tolerance:
            current_line.append(c)
        else:
            lines.append(current_line)
            current_line = [c]
    if current_line:
        lines.append(current_line)

    # Reconstruct each line with space insertion
    result_lines = []
    for line_chars in lines:
        line_chars = sorted(line_chars, key=lambda c: c["x0"])
        reconstructed = ""
        for i, c in enumerate(line_chars):
            if i > 0:
                prev = line_chars[i - 1]
                gap = c["x0"] - (prev["x0"] + prev.get("width", 5))
                if gap > space_threshold:
                    reconstructed += " "
            reconstructed += c["text"]
        result_lines.append(reconstructed)

    return "\n".join(result_lines)


def _extract_columns_text(pdf_path: str | Path) -> str:
    """Extract text from the PDF, processing two columns separately.

    For two-column pages, we split characters into left/right columns
    and extract each independently, then concatenate them in reading order
    (left column fully, then right column fully per page).
    """
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            chars = page.chars
            if not chars:
                continue

            # Two-column layout: split chars by x-position
            left_chars = [c for c in chars if c["x0"] < COLUMN_SPLIT_X]
            right_chars = [c for c in chars if c["x0"] >= COLUMN_SPLIT_X]

            # Skip page headers (small caps "GLOSSARY OF TERMS IN KENDO N")
            header_y = 45
            right_chars = [c for c in right_chars if c["top"] > header_y]

            left_text = _reconstruct_column_text(left_chars)
            right_text = _reconstruct_column_text(right_chars)

            # Combine: left column first, then right column
            combined = left_text
            if right_text.strip():
                combined += "\n" + right_text
            all_text.append(combined)

    return "\n\n".join(all_text)


# Section headers in the glossary
KNOWN_SECTIONS = {
    "DOJO COMMANDS": "dojo_commands",
    "SHIAI TERMS & COMMANDS": "shiai",
    "SHIAI TERMS": "shiai",
    "GENERAL TERMS": "general",
}

# Lines to skip (metadata, headers)
SKIP_PATTERNS = [
    re.compile(r"^ɢʟᴏSSᴀʀʏ"),
    re.compile(r"^Glossary of Terms"),
    re.compile(r"^Stephen Quinlan"),
    re.compile(r"^May \d+"),
    re.compile(r"^Pronunciation Aids"),
    re.compile(r"^common rules"),
    re.compile(r"^sound\. Also"),
    re.compile(r"^not normally done"),
    re.compile(r"^Any errors"),
    re.compile(r"^\d+$"),
]

# Entry start: Capitalized term with kanji in parentheses
ENTRY_WITH_KANJI = re.compile(
    r"^([A-Z][a-zA-Zōūû̥ı̥\u0323\u0325\-]+(?:\s+(?:no|ni|w|wo|de)\s+[a-zA-Zōūû̥\u0323\u0325\-]+)*"
    r"(?:\s+[a-z][a-zA-Zōūû̥\u0323\u0325\-]*)*)"
    r"\s*\(([^)]+)\)\s*(.*)"
)

# Entry start for entries without kanji (e.g., "Dead sword", "Connection")
ENTRY_NO_KANJI = re.compile(
    r"^([A-Z][a-zA-Z\-]+(?:\s+[a-z][a-zA-Z\-]*)*)"
    r"\s+((?:See\s+|A\s+|The\s+|Similar\s+|In\s+|Sometimes\s+|When\s+|Literally\s+).+)"
)


def _parse_column_text(text: str) -> list[GlossaryEntry]:
    """Parse extracted column text into glossary entries."""
    lines = text.split("\n")
    entries: list[GlossaryEntry] = []
    current_section = "general"
    current_entry: GlossaryEntry | None = None
    current_def_lines: list[str] = []

    def _save_current():
        nonlocal current_entry, current_def_lines
        if current_entry:
            if current_def_lines:
                full_def = " ".join(current_def_lines).strip()
                full_def = re.sub(r"\s+", " ", full_def)
                current_entry.definition = (
                    current_entry.definition + " " + full_def
                    if current_entry.definition
                    else full_def
                ).strip()
            entries.append(current_entry)
            current_entry = None
            current_def_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip headers/meta
        if any(p.match(line) for p in SKIP_PATTERNS):
            continue

        # Check for section headers
        section_found = False
        for section_name, section_key in KNOWN_SECTIONS.items():
            if section_name in line:
                current_section = section_key
                section_found = True
                break
        if section_found:
            continue

        # Skip single letter headers (A, B, C, etc.)
        if re.match(r"^[A-Z]$", line):
            continue

        # Try entry with kanji
        m = ENTRY_WITH_KANJI.match(line)
        if m:
            _save_current()
            current_entry = GlossaryEntry(
                term_romaji=m.group(1).strip(),
                term_kanji=m.group(2).strip(),
                definition=m.group(3).strip(),
                category=current_section,
            )
            current_def_lines = []
            continue

        # Try entry without kanji (e.g., "Dead hands Similar to...")
        m2 = ENTRY_NO_KANJI.match(line)
        if m2 and current_entry is not None:
            # Only start new entry if the term looks like a new concept
            term_candidate = m2.group(1).strip()
            if len(term_candidate) > 2 and term_candidate[0].isupper():
                _save_current()
                current_entry = GlossaryEntry(
                    term_romaji=term_candidate,
                    definition=m2.group(2).strip(),
                    category=current_section,
                )
                current_def_lines = []
                continue

        # Continuation of current definition
        if current_entry is not None:
            current_def_lines.append(line)
        # If no current entry, check if this line starts a new one anyway
        elif line and line[0].isupper():
            # Could be a new entry without standard format
            m3 = ENTRY_WITH_KANJI.match(line)
            if m3:
                current_entry = GlossaryEntry(
                    term_romaji=m3.group(1).strip(),
                    term_kanji=m3.group(2).strip(),
                    definition=m3.group(3).strip(),
                    category=current_section,
                )
                current_def_lines = []

    _save_current()
    return entries


def parse_glossary(pdf_path: str | Path) -> list[GlossaryEntry]:
    """Parse the kendo glossary PDF into structured entries.

    Args:
        pdf_path: Path to Glossary.pdf

    Returns:
        List of GlossaryEntry objects with term, kanji, definition, and category.
    """
    full_text = _extract_columns_text(pdf_path)
    entries = _parse_column_text(full_text)

    # Post-process: clean up entries
    cleaned = []
    seen_terms = set()
    for entry in entries:
        if not entry.term_romaji:
            continue
        entry.definition = re.sub(r"\s+", " ", entry.definition).strip()
        # Deduplicate (same term might appear in both columns due to wrapping)
        key = entry.term_romaji.lower()
        if key not in seen_terms:
            seen_terms.add(key)
            cleaned.append(entry)

    return cleaned


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from kendocenter.config import settings

    pdf_path = settings.theory_path / "glossary" / "Glossary.pdf"
    entries = parse_glossary(pdf_path)

    print(f"Total entries parsed: {len(entries)}")
    print()

    # Category distribution
    from collections import Counter

    cats = Counter(e.category for e in entries)
    print("Categories:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")
    print()

    # Show sample entries
    print("Sample entries:")
    for e in entries[:15]:
        kanji = f" ({e.term_kanji})" if e.term_kanji else ""
        defn = e.definition[:150] + "..." if len(e.definition) > 150 else e.definition
        print(f"  [{e.category:15s}] {e.term_romaji}{kanji}")
        print(f"    {defn}")
        print()

    # Also show some specific important terms
    print("=== Key terms check ===")
    important = ["Zanshin", "Men", "Kote", "Kamae", "Seme", "Maai", "Ippon", "Chiisai"]
    for term_name in important:
        matches = [e for e in entries if term_name.lower() in e.term_romaji.lower()]
        if matches:
            for m in matches:
                print(f"  {m.term_romaji} ({m.term_kanji}): {m.definition[:100]}...")
        else:
            print(f"  {term_name}: NOT FOUND")
