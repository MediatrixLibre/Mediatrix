#!/usr/bin/env python3
"""
build-mediatrix.py — Mediatrix data pipeline.

Reads the thirteen canonical markdown files from the Mariology corpus and
emits one normalised JSON per source to site/data/, plus
site/data/search-index.json for client-side search.

The corpus location is configurable via the MARIOLOGY_CORPUS environment
variable; if unset, the pipeline looks for ./corpus/mariology/ inside the
repository root.

Usage:
  ./tools/build-mediatrix.py                # build all
  ./tools/build-mediatrix.py anthology      # build a single extractor
  ./tools/build-mediatrix.py --verify       # verify outputs without rebuilding
  ./tools/build-mediatrix.py --list         # list extractors

Architecture:
  - tools/lib/parser.py supplies parsing primitives (frontmatter,
    section tree, blockquote / metadata-line extraction, provenance / pole
    detection).
  - One extractor function per source file. Each returns a dict ready
    to be JSON-serialised.
  - All extractors are pure: given the same markdown they produce the
    same JSON. Re-runnable without side effects.

No external dependencies. Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

# allow tools/lib import when invoked from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.parser import (  # noqa: E402
    Section,
    extract_blockquotes,
    extract_metadata_lines,
    normalize_whitespace,
    parse_numbered_header,
    parse_pole,
    parse_provenance,
    read_source,
    strip_markdown,
)


# --- paths --------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
SOURCE_DIR = Path(
    os.environ.get("MARIOLOGY_CORPUS")
    or (REPO / "corpus" / "mariology")
).expanduser()
DATA_DIR = REPO / "site" / "data"
SCHEMA_VERSION = 1


def _file_mtime(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _wrap(source_name: str, payload: dict) -> dict:
    """Wrap an extractor payload with provenance metadata."""
    src_path = SOURCE_DIR / source_name
    return {
        "schema_version": SCHEMA_VERSION,
        "source_file": source_name,
        "source_mtime": _file_mtime(src_path),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        **payload,
    }


# ========================================================================
#  EXTRACTORS — one function per source file
# ========================================================================


# --- 1. Library ---------------------------------------------------------

def extract_library() -> dict:
    """Mediatrix-Coredemptrix-Library.md → chronological eras + sources."""
    src = "Mediatrix-Coredemptrix-Library.md"
    fm, root = read_source(SOURCE_DIR / src)

    # Top-level H1 is the doc title. H2s are parts / eras.
    eras: list[dict] = []
    for h2 in root.find_all(2):
        eras.append(
            {
                "title": strip_markdown(h2.title),
                "summary": normalize_whitespace(strip_markdown(h2.first_paragraph()))[:500],
            }
        )

    return _wrap(src, {"title": fm.get("title", ""), "eras": eras, "era_count": len(eras)})


# --- 2. OT Types --------------------------------------------------------

def extract_ot_types() -> dict:
    """OT-Types-of-Our-Lady-Exegesis.md → 28 type records."""
    src = "OT-Types-of-Our-Lady-Exegesis.md"
    fm, root = read_source(SOURCE_DIR / src)

    types: list[dict] = []
    for h3 in root.find_all(3):
        num, raw_title = parse_numbered_header(h3.title)
        if num is None:
            continue
        # Split title into reference + name when an em-dash separator is present
        parts = re.split(r"\s+[—–-]\s+", raw_title, maxsplit=1)
        if len(parts) == 2:
            reference, name = parts[0].strip(), parts[1].strip()
        else:
            reference, name = "", raw_title

        meta = extract_metadata_lines(h3.body)
        blocks = extract_blockquotes(h3.body)
        types.append(
            {
                "num": num,
                "reference": strip_markdown(reference),
                "title": strip_markdown(name),
                "verse": blocks[0] if blocks else "",
                "body": normalize_whitespace(strip_markdown(h3.first_paragraph()))[:800],
                "provenance": (meta.get("provenance") or "").lower() or None,
                "pole": _detect_pole_in_body(h3.body),
            }
        )
    types.sort(key=lambda t: t["num"])

    return _wrap(src, {"title": fm.get("title", ""), "types": types, "type_count": len(types)})


def _detect_pole_in_body(body: str) -> str | None:
    """Scan body for `Pole: X` or `**Pole:** X` patterns."""
    for line in body.splitlines():
        if "pole" in line.lower() and ":" in line:
            after = line.split(":", 1)[1]
            p = parse_pole(after)
            if p:
                return p
    return None


# --- 3. NT Texts --------------------------------------------------------

def extract_nt_texts() -> dict:
    """NT-Load-Bearing-Texts.md → 3 passage records (Cana / Calvary / Rev 12)."""
    src = "NT-Load-Bearing-Texts.md"
    fm, root = read_source(SOURCE_DIR / src)

    passages: list[dict] = []
    syntheses: list[dict] = []
    # H1s of interest: "Part I — Cana (John 2:1-11)" through "Part V"
    # Parts I, II, III are passages; later parts are syntheses.
    PASSAGE_HDR = re.compile(
        r"^Part\s+(I{1,3}|IV|V|VI)\s*[—–-]\s*(.+)$", re.IGNORECASE
    )
    PASSAGE_ROMAN = {"I": 1, "II": 2, "III": 3}

    for part in root.find_all(1):
        m = PASSAGE_HDR.match(part.title.strip())
        if not m:
            continue
        roman = m.group(1).upper()
        title_remainder = m.group(2).strip()

        sections: list[dict] = []
        for h2 in part.children:
            if h2.level != 2:
                continue
            sections.append(
                {
                    "title": strip_markdown(h2.title),
                    "body": normalize_whitespace(strip_markdown(h2.first_paragraph()))[:600],
                }
            )

        blocks = extract_blockquotes(part.body)
        record = {
            "roman": roman,
            "title": strip_markdown(title_remainder),
            "greek": blocks[0] if blocks else "",
            "english": blocks[1] if len(blocks) > 1 else "",
            "sections": sections,
            "section_count": len(sections),
        }
        if roman in PASSAGE_ROMAN:
            passages.append(record)
        else:
            syntheses.append(record)

    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "passages": passages,
            "passage_count": len(passages),
            "syntheses": syntheses,
            "synthesis_count": len(syntheses),
        },
    )


# --- 4. Concise Anthology -----------------------------------------------

def extract_anthology() -> dict:
    """Marian-Concise-Anthology.md → 49 saint records."""
    src = "Marian-Concise-Anthology.md"
    fm, root = read_source(SOURCE_DIR / src)

    # The H2s are eras (Part I, Part II, ...). The H3s under each era are
    # the numbered saints.
    eras_map = {
        "apostolic": "Apostolic and Sub-Apostolic Era",
        "greek-fathers": "Greek Fathers",
        "latin-fathers": "Latin Fathers",
        "byzantine": "Byzantine Fathers",
        "medieval": "Medieval Doctors",
        "late-medieval": "Late Medieval and Renaissance",
        "counter-reformation": "Counter-Reformation and Early Modern",
        "modern-saints": "Modern Saints (19th-20th c.)",
        "modern-magisterium": "Modern Magisterium",
    }

    saints: list[dict] = []
    current_era: str | None = None
    current_era_slug: str | None = None

    def slugify_era(title: str) -> str | None:
        t = title.lower()
        for slug, name in eras_map.items():
            if name.lower().split(" (")[0] in t:
                return slug
        if "apostolic" in t:
            return "apostolic"
        if "greek" in t and "father" in t:
            return "greek-fathers"
        if "latin" in t and "father" in t:
            return "latin-fathers"
        if "byzantine" in t:
            return "byzantine"
        if "medieval" in t and "late" not in t:
            return "medieval"
        if "late" in t:
            return "late-medieval"
        if "counter" in t or "reformation" in t:
            return "counter-reformation"
        if "modern saint" in t:
            return "modern-saints"
        if "magisterium" in t:
            return "modern-magisterium"
        return None

    # Walk top-level H1 parts (Part I, Part II, ...)
    for part in root.find_all(1):
        if not part.title.lower().startswith("part"):
            continue
        current_era = strip_markdown(part.title)
        current_era_slug = slugify_era(part.title)
        for h2 in part.children:
            if h2.level != 2:
                continue
            num, raw_title = parse_numbered_header(h2.title)
            if num is None:
                continue
            # raw_title pattern: "Name (dates) — language" or "Name (dates)"
            name_match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*(?:[—–-]\s*(.+))?$", raw_title)
            if name_match:
                name = name_match.group(1).strip()
                dates = name_match.group(2).strip()
                language = (name_match.group(3) or "").strip()
            else:
                name, dates, language = raw_title, "", ""

            meta = extract_metadata_lines(h2.body)
            blocks = extract_blockquotes(h2.body)
            orig_lang, original_text, english_text = _split_quote_pair(blocks)

            saints.append(
                {
                    "num": num,
                    "name": strip_markdown(name),
                    "dates": dates,
                    "language": language,
                    "era_title": current_era,
                    "era_slug": current_era_slug,
                    "original_language": orig_lang or _infer_lang(language),
                    "original": original_text,
                    "english": english_text,
                    "source": strip_markdown(meta.get("source", "")),
                    "provenance": (parse_provenance(meta.get("provenance", "") or "") or "").lower() or None,
                    "pole": parse_pole(meta.get("pole", "") or ""),
                }
            )

    saints.sort(key=lambda s: s["num"])
    return _wrap(src, {"title": fm.get("title", ""), "saints": saints, "saint_count": len(saints)})


def _infer_lang(lang_field: str) -> str:
    """Infer original-language code from the heading's 'language' field."""
    if not lang_field:
        return ""
    f = lang_field.lower()
    for code in ("greek", "latin", "hebrew", "syriac", "french", "italian", "polish", "occitan", "spanish", "aramaic"):
        if code in f:
            return code
    return ""


_ENGLISH_MARKER = re.compile(r"\*\*English:?\*\*\s*[:\.]?\s*", re.IGNORECASE)
_LANG_PREFIX = re.compile(
    r"^\*\*(Latin|Greek|Hebrew|Syriac|French|Italian|Polish|Occitan(?:\s*/\s*Gascon)?|Spanish|Aramaic)\*\*\s*",
    re.IGNORECASE,
)


def _split_quote_pair(blocks: list[str]) -> tuple[str, str, str]:
    """
    Anthology blockquotes contain both original-language and English in a
    single contiguous quote, demarcated by '**English:**'. Return
    (original_lang, original_text, english_text). Strips markdown wrappers.
    """
    if not blocks:
        return "", "", ""
    joined = " ".join(blocks)
    parts = _ENGLISH_MARKER.split(joined, maxsplit=1)
    if len(parts) == 2:
        original_blob, english_blob = parts
    else:
        original_blob, english_blob = joined, ""

    # Detect original language
    lang = ""
    lm = _LANG_PREFIX.match(original_blob)
    if lm:
        lang = lm.group(1).lower()
        original_blob = original_blob[lm.end():]
    # The original blob may still have a parenthetical citation prefix; we
    # leave it intact and let the source field carry the citation.

    # Find the actual quote. Preferred patterns, in order:
    #   1.  *"…"*  (italic-wrapped quote — the canonical form)
    #   2.  *“…”*  (smart quotes)
    #   3.  *…* after the colon that follows a parenthetical citation
    # The work-title italics inside the citation parens are explicitly skipped.
    original_text = ""
    # Remove the leading parenthetical citation if present
    blob_after_citation = re.sub(r"^\s*\([^)]*\)\s*:?\s*", "", original_blob).strip()

    # Pattern 1 + 2: italic-wrapped quotes (straight or smart)
    qm = re.search(r"\*[\"“]([^\"”]+)[\"”]\*", blob_after_citation)
    if qm:
        original_text = qm.group(1)
    else:
        # Pattern 3: any italic span after the citation
        qm = re.search(r"\*([^*]+)\*", blob_after_citation)
        if qm:
            original_text = qm.group(1)
        else:
            original_text = strip_markdown(blob_after_citation).strip().strip(":").strip().strip('"').strip()

    english_text = strip_markdown(english_blob).strip().strip('"').strip()

    return lang, normalize_whitespace(original_text), normalize_whitespace(english_text)


# --- 5. Rosary ----------------------------------------------------------

def extract_rosary() -> dict:
    """Rosary-Companion.md → 20 mystery records + closing prayers."""
    src = "Rosary-Companion.md"
    fm, root = read_source(SOURCE_DIR / src)

    mysteries: list[dict] = []
    # Mystery H2s are numbered 1..20 ("## 1. The Annunciation (Luke 1:26-38)")
    for h2 in root.find_all(2):
        num, raw_title = parse_numbered_header(h2.title)
        if num is None or num < 1 or num > 20:
            continue
        # Determine set
        set_name = (
            "joyful"
            if num <= 5
            else "luminous"
            if num <= 10
            else "sorrowful"
            if num <= 15
            else "glorious"
        )
        # split title on " — " or " ("
        parts = re.split(r"\s+[—–-]\s+|\s*\(", raw_title, maxsplit=1)
        title = parts[0].strip()
        reference = ""
        if len(parts) > 1:
            reference = parts[1].rstrip(")").strip()

        # Pull the principal scripture quote (first blockquote) and a fruit / intention
        blocks = extract_blockquotes(h2.body)
        scripture_block = blocks[0] if blocks else ""

        # Try to detect fruit / intention from "**Fruit:** X" lines
        body = h2.body
        fruit = _find_inline_field(body, "Fruit")
        intention = _find_inline_field(body, "Intention")

        mysteries.append(
            {
                "num": num,
                "set": set_name,
                "title": strip_markdown(title),
                "reference": strip_markdown(reference),
                "scripture": scripture_block,
                "fruit": fruit,
                "intention": intention,
            }
        )

    mysteries.sort(key=lambda m: m["num"])

    days = {
        "monday": "joyful",
        "tuesday": "sorrowful",
        "wednesday": "glorious",
        "thursday": "luminous",
        "friday": "sorrowful",
        "saturday": "joyful",
        "sunday": "glorious",
    }
    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "distribution": days,
            "mysteries": mysteries,
            "mystery_count": len(mysteries),
        },
    )


def _find_inline_field(body: str, label: str) -> str:
    """Find a line like '**Fruit:** humility.' and return 'humility'."""
    pat = re.compile(rf"\*\*{label}\s*:?\*\*\s*(.+)", re.IGNORECASE)
    for line in body.splitlines():
        m = pat.search(line)
        if m:
            return strip_markdown(m.group(1).strip().rstrip("."))
    return ""


# --- 6. Protestant Objections Defense -----------------------------------

def extract_defense() -> dict:
    """Protestant-Objections-Defense.md → 12 objection records."""
    src = "Protestant-Objections-Defense.md"
    fm, root = read_source(SOURCE_DIR / src)

    objections: list[dict] = []
    # H1s "# Objection N. Title"
    for h1 in root.find_all(1):
        m = re.match(r"^\s*Objection\s+(\d+)\.?\s+(.+)$", h1.title, re.IGNORECASE)
        if not m:
            continue
        num = int(m.group(1))
        title = m.group(2).strip()
        objections.append(
            {
                "num": num,
                "title": strip_markdown(title),
                "summary": normalize_whitespace(strip_markdown(h1.first_paragraph()))[:400],
            }
        )
    objections.sort(key=lambda o: o["num"])
    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "objections": objections,
            "objection_count": len(objections),
        },
    )


# --- 7. Feasts ----------------------------------------------------------

def extract_feasts() -> dict:
    """Marian-Feasts-Liturgical-Calendar.md → 18 feast records."""
    src = "Marian-Feasts-Liturgical-Calendar.md"
    fm, root = read_source(SOURCE_DIR / src)

    feasts: list[dict] = []
    # H2s with calendar dates ("## January 1 — Solemnity of Mary, Mother of God")
    DATE_HDR = re.compile(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        re.IGNORECASE,
    )
    for h2 in root.find_all(2):
        if not DATE_HDR.match(h2.title.strip()):
            continue
        # Format: "DATE — TITLE" or "DATE — TITLE (subtitle)"
        parts = re.split(r"\s+[—–-]\s+", h2.title.strip(), maxsplit=1)
        date_str = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        # subtitle in parens?
        sub = ""
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", name)
        if m:
            name = m.group(1).strip()
            sub = m.group(2).strip()
        feasts.append(
            {
                "date": date_str,
                "name": strip_markdown(name),
                "subtitle": strip_markdown(sub),
            }
        )

    return _wrap(src, {"title": fm.get("title", ""), "feasts": feasts, "feast_count": len(feasts)})


# --- 8. Apparitions -----------------------------------------------------

def extract_apparitions() -> dict:
    """Marian-Apparitions-Reference.md → 7 primary + secondary records."""
    src = "Marian-Apparitions-Reference.md"
    fm, root = read_source(SOURCE_DIR / src)

    apparitions: list[dict] = []
    # Roman-numeral H1s "# I. Our Lady of Guadalupe (1531)"
    ROMAN_HDR = re.compile(r"^\s*(I{1,3}|IV|V|VI|VII|VIII|IX|X)\.\s+(.+)$")
    for h1 in root.find_all(1):
        m = ROMAN_HDR.match(h1.title)
        if not m:
            continue
        body_title = m.group(2)
        # extract year in parens
        ym = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", body_title)
        if ym:
            name, year = ym.group(1).strip(), ym.group(2).strip()
        else:
            name, year = body_title, ""

        # try to find visionary line
        visionary = ""
        for line in h1.body.splitlines():
            ll = line.strip()
            if ll.lower().startswith("- **visionary"):
                visionary = re.sub(r"^-\s+\*\*Visionary\*?\*?:?\s*\*?\*?", "", ll, flags=re.I).strip()
                visionary = strip_markdown(visionary.split(".")[0]).strip()
                break

        apparitions.append(
            {
                "roman": m.group(1),
                "name": strip_markdown(name),
                "year": year,
                "visionary": visionary,
            }
        )

    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "apparitions": apparitions,
            "apparition_count": len(apparitions),
        },
    )


# --- 9. Litany ----------------------------------------------------------

def extract_litany() -> dict:
    """Litany-of-Loreto-Annotated.md → 54 title records + papal additions."""
    src = "Litany-of-Loreto-Annotated.md"
    fm, root = read_source(SOURCE_DIR / src)

    titles: list[dict] = []
    current_group: str | None = None
    current_group_slug: str | None = None
    group_count = 0

    # H1s: "# Group 1: The Foundational Titles"
    # H2s under each group: "## 1. *Sancta Maria* (Holy Mary)"
    for h1 in root.find_all(1):
        gm = re.match(r"^Group\s+(\d+)\s*[:.]?\s*(.*)$", h1.title, re.IGNORECASE)
        if gm:
            group_count += 1
            current_group = h1.title.strip()
            current_group_slug = _slug(gm.group(2) or h1.title)
        for h2 in h1.children:
            if h2.level != 2:
                continue
            # match patterns: "1. *Sancta Maria* (Holy Mary)" or "9–12. Mater purissima ... (Mother most pure)"
            tm = re.match(
                r"^\s*([\d–—\-,\s]+)\.\s*\*?([^*(]+?)\*?\s*(?:\((.+?)\))?\s*$",
                h2.title,
            )
            if not tm:
                continue
            numbers = _parse_number_range(tm.group(1))
            latin = tm.group(2).strip()
            english = (tm.group(3) or "").strip()
            meta = extract_metadata_lines(h2.body)
            titles.append(
                {
                    "numbers": numbers,
                    "first_num": numbers[0] if numbers else None,
                    "latin": strip_markdown(latin),
                    "english": strip_markdown(english),
                    "group": current_group,
                    "group_slug": current_group_slug,
                    "scriptural_root": meta.get("scriptural root", "") or meta.get("scriptural roots", ""),
                    "added": meta.get("added", "") or meta.get("added to the litany", ""),
                }
            )

    titles.sort(key=lambda t: (t["first_num"] or 999))
    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "titles": titles,
            "title_count": len(titles),
            "group_count": group_count,
        },
    )


def _parse_number_range(s: str) -> list[int]:
    """'1' → [1]; '9-12' → [9,10,11,12]; '27, 28, 29' → [27,28,29]"""
    s = s.replace("–", "-").replace("—", "-").strip()
    out: list[int] = []
    for part in re.split(r",\s*", s):
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            except ValueError:
                continue
        else:
            try:
                out.append(int(part))
            except ValueError:
                continue
    return out


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"\s+", "-", s.strip())
    return s


# --- 10. Office of Readings ---------------------------------------------

def extract_office() -> dict:
    """Marian-Office-of-Readings-Sourcebook.md → 14 feast Office readings + supplementary."""
    src = "Marian-Office-of-Readings-Sourcebook.md"
    fm, root = read_source(SOURCE_DIR / src)

    DATE_HDR = re.compile(
        r"^(January|February|March|April|May|June|July|August|September|October|November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
        re.IGNORECASE,
    )
    SKIP_PREFIXES = (
        "preamble", "how to use", "structure", "related", "note", "table of contents",
    )
    SUPPL_PREFIXES = (
        "common of", "saturday marian", "1962", "a note on",
    )

    feast_readings: list[dict] = []
    supplementary: list[dict] = []

    for h2 in root.find_all(2):
        title = h2.title.strip()
        tl = title.lower()
        if tl.startswith(SKIP_PREFIXES):
            continue
        # Strip any `{#anchor}` tail
        clean_title = re.sub(r"\s*\{#[^}]+\}\s*$", "", title).strip()
        summary = normalize_whitespace(strip_markdown(h2.first_paragraph()))[:500]
        record = {"title": strip_markdown(clean_title), "summary": summary}

        if DATE_HDR.match(clean_title):
            # split "DATE, NAME"
            parts = re.split(r",\s+", clean_title, maxsplit=1)
            record["date"] = parts[0].strip()
            record["feast"] = parts[1].strip() if len(parts) > 1 else ""
            feast_readings.append(record)
        elif tl.startswith(SUPPL_PREFIXES):
            supplementary.append(record)
        else:
            supplementary.append(record)

    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "readings": feast_readings,
            "reading_count": len(feast_readings),
            "supplementary": supplementary,
            "supplementary_count": len(supplementary),
        },
    )


# --- 11. Akathist Hymn --------------------------------------------------

def extract_akathist() -> dict:
    """Akathist-Hymn-Translated-Annotated.md → 24 stanzas + prooemion."""
    src = "Akathist-Hymn-Translated-Annotated.md"
    fm, root = read_source(SOURCE_DIR / src)

    # Headers in this source follow the pattern:
    #   "Stanza N (Kontakion M, alpha)" or
    #   "Stanza N (Ikos M, beta) — Subtitle" or
    #   "The Prooemion"
    STANZA_HDR = re.compile(
        r"^Stanza\s+(\d+)\s*\((Kontakion|Ikos|Oikos)\s+(\d+)\s*,\s*(\w+)\)\s*(?:[—–-]\s*(.+))?$",
        re.IGNORECASE,
    )

    stanzas: list[dict] = []
    prooemion = None

    for h2 in root.find_all(2):
        title = h2.title.strip()
        if title.lower().startswith("the prooemion") or title.lower().startswith("prooemion"):
            blocks = extract_blockquotes(h2.body)
            prooemion = {
                "title": strip_markdown(title),
                "greek": blocks[0] if blocks else "",
                "english": blocks[1] if len(blocks) > 1 else "",
            }
            continue
        m = STANZA_HDR.match(title)
        if not m:
            continue
        stanza_num = int(m.group(1))
        kind = m.group(2).lower()
        cycle_num = int(m.group(3))
        greek_letter = m.group(4).lower()
        subtitle = (m.group(5) or "").strip()

        blocks = extract_blockquotes(h2.body)
        # In this source the principal blockquote is the English translation;
        # Greek snippets appear inline in *italics* within the annotation prose.
        # Separate any block containing Greek characters into `greek_inline`.
        english_blocks: list[str] = []
        greek_blocks: list[str] = []
        for b in blocks:
            if any(0x0370 <= ord(c) <= 0x03FF for c in b):
                greek_blocks.append(b)
            else:
                english_blocks.append(b)

        # Pull short inline Greek snippets from annotation prose (e.g. *ἱλασμὸς τοῦ παντὸς κόσμου*)
        greek_inline_raw = re.findall(r"\*([^*]*[Ͱ-Ͽ][^*]*)\*", h2.body)
        greek_inline = [normalize_whitespace(g) for g in greek_inline_raw]

        stanzas.append(
            {
                "stanza_num": stanza_num,
                "kind": kind,  # "kontakion" or "ikos"
                "cycle_num": cycle_num,
                "greek_letter": greek_letter,
                "subtitle": strip_markdown(subtitle),
                "english": english_blocks[0] if english_blocks else "",
                "greek_blocks": greek_blocks,
                "greek_inline": greek_inline[:8],  # cap to avoid bloat
            }
        )

    stanzas.sort(key=lambda s: s["stanza_num"])
    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "prooemion": prooemion,
            "stanzas": stanzas,
            "stanza_count": len(stanzas),
        },
    )


# --- 12. Iconography ----------------------------------------------------

def extract_iconography() -> dict:
    """Marian-Iconography-Reference.md → types + symbols + images."""
    src = "Marian-Iconography-Reference.md"
    fm, root = read_source(SOURCE_DIR / src)

    sections: list[dict] = []
    for h2 in root.find_all(2):
        if h2.title.lower().startswith(("preamble", "how", "related", "note")):
            continue
        sections.append(
            {
                "title": strip_markdown(h2.title),
                "summary": normalize_whitespace(strip_markdown(h2.first_paragraph()))[:400],
            }
        )

    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "sections": sections,
            "section_count": len(sections),
        },
    )


# --- 13. Perfect Prompts (meta) -----------------------------------------

def extract_prompts() -> dict:
    """_Perfect-Prompts-Mariology-Build.md → list of prompts."""
    src = "_Perfect-Prompts-Mariology-Build.md"
    fm, root = read_source(SOURCE_DIR / src)

    prompts: list[dict] = []
    for h2 in root.find_all(2):
        m = re.match(r"^\s*Prompt\s+(\d+)\s*[:.]?\s*(.*)$", h2.title, re.IGNORECASE)
        if not m:
            continue
        prompts.append(
            {
                "num": int(m.group(1)),
                "title": strip_markdown(m.group(2)),
            }
        )

    prompts.sort(key=lambda p: p["num"])
    return _wrap(
        src,
        {
            "title": fm.get("title", ""),
            "prompts": prompts,
            "prompt_count": len(prompts),
        },
    )


# ========================================================================
#  SEARCH INDEX
# ========================================================================


def build_search_index(extractions: dict[str, dict]) -> dict:
    """
    Walk all extracted JSON payloads and build a single search index.

    Each entry: {slug, kind, title, subtitle, body, refs}
      - slug: target page (e.g. 'anthology.html')
      - kind: 'saint', 'title', 'type', 'mystery', 'feast', etc.
      - title: primary display
      - subtitle: secondary display
      - body: full text indexed for keyword matching
    """
    entries: list[dict] = []

    # Anthology saints
    for s in extractions.get("anthology", {}).get("saints", []):
        entries.append(
            {
                "slug": f"anthology.html#s{s['num']}",
                "kind": "saint",
                "title": s.get("name", ""),
                "subtitle": f"{s.get('dates', '')} · {s.get('language', '')}",
                "body": " ".join(
                    str(v)
                    for v in (s.get("english", ""), s.get("original", ""), s.get("source", ""))
                ),
            }
        )

    # OT types
    for t in extractions.get("ot-types", {}).get("types", []):
        entries.append(
            {
                "slug": f"ot-types.html#t{t['num']}",
                "kind": "ot-type",
                "title": t.get("title", ""),
                "subtitle": t.get("reference", ""),
                "body": " ".join(str(v) for v in (t.get("body", ""), t.get("verse", ""))),
            }
        )

    # Litany titles
    for ttl in extractions.get("litany", {}).get("titles", []):
        if ttl["first_num"] is None:
            continue
        entries.append(
            {
                "slug": f"litany.html",
                "kind": "litany-title",
                "title": ttl.get("latin", ""),
                "subtitle": ttl.get("english", ""),
                "body": " ".join(
                    str(v)
                    for v in (
                        ttl.get("scriptural_root", ""),
                        ttl.get("group", ""),
                        ttl.get("added", ""),
                    )
                ),
            }
        )

    # Mysteries
    for m in extractions.get("rosary", {}).get("mysteries", []):
        entries.append(
            {
                "slug": f"rosary.html#m{m['num']}",
                "kind": "mystery",
                "title": m.get("title", ""),
                "subtitle": f"{m.get('set', '').title()} · {m.get('reference', '')}",
                "body": " ".join(
                    str(v) for v in (m.get("scripture", ""), m.get("fruit", ""), m.get("intention", ""))
                ),
            }
        )

    # Feasts
    for f in extractions.get("feasts", {}).get("feasts", []):
        entries.append(
            {
                "slug": "feasts.html",
                "kind": "feast",
                "title": f.get("name", ""),
                "subtitle": f.get("date", ""),
                "body": f.get("subtitle", ""),
            }
        )

    # Apparitions
    for a in extractions.get("apparitions", {}).get("apparitions", []):
        entries.append(
            {
                "slug": f"apparitions.html",
                "kind": "apparition",
                "title": a.get("name", ""),
                "subtitle": f"{a.get('year', '')} · {a.get('visionary', '')}",
                "body": a.get("visionary", ""),
            }
        )

    # Objections
    for o in extractions.get("defense", {}).get("objections", []):
        entries.append(
            {
                "slug": "defense.html",
                "kind": "objection",
                "title": o.get("title", ""),
                "subtitle": f"Objection {o['num']}",
                "body": o.get("summary", ""),
            }
        )

    # NT passages
    for p in extractions.get("nt-texts", {}).get("passages", []):
        entries.append(
            {
                "slug": "nt-texts.html",
                "kind": "nt-passage",
                "title": p.get("title", ""),
                "subtitle": f"{p.get('section_count', 0)} exegetical points",
                "body": p.get("greek", "") + " " + p.get("english", ""),
            }
        )

    # Akathist stanzas
    for st in extractions.get("akathist", {}).get("stanzas", []):
        entries.append(
            {
                "slug": "akathist.html",
                "kind": "akathist-stanza",
                "title": f"Stanza {st['stanza_num']} ({st.get('kind', '').title()} {st.get('cycle_num', '')}, {st.get('greek_letter', '')})",
                "subtitle": st.get("subtitle", ""),
                "body": st.get("english", "") + " " + " ".join(st.get("greek_inline", [])),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(entries),
        "entries": entries,
    }


# ========================================================================
#  RUNNER
# ========================================================================


EXTRACTORS: dict[str, callable] = {  # type: ignore[type-arg]
    "library": extract_library,
    "ot-types": extract_ot_types,
    "nt-texts": extract_nt_texts,
    "anthology": extract_anthology,
    "rosary": extract_rosary,
    "defense": extract_defense,
    "feasts": extract_feasts,
    "apparitions": extract_apparitions,
    "litany": extract_litany,
    "office": extract_office,
    "akathist": extract_akathist,
    "iconography": extract_iconography,
    "prompts": extract_prompts,
}


def write_json(name: str, data: dict) -> Path:
    out = DATA_DIR / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", help="Extractor names; omit to build all.")
    ap.add_argument("--list", action="store_true", help="List available extractors.")
    ap.add_argument("--verify", action="store_true", help="Verify outputs exist + report record counts.")
    args = ap.parse_args()

    if args.list:
        for name in EXTRACTORS:
            print(name)
        return 0

    if args.verify:
        ok = True
        for name in EXTRACTORS:
            p = DATA_DIR / f"{name}.json"
            if not p.exists():
                print(f"  MISSING  {name}.json")
                ok = False
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            # find the *_count fields and report them
            counts = {k: v for k, v in data.items() if k.endswith("_count")}
            count_str = " · ".join(f"{k}={v}" for k, v in counts.items()) or "ok"
            print(f"  OK       {name}.json   {count_str}")
        idx_path = DATA_DIR / "search-index.json"
        if idx_path.exists():
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
            print(f"  OK       search-index.json   entry_count={idx.get('entry_count', '?')}")
        else:
            print(f"  MISSING  search-index.json")
            ok = False
        return 0 if ok else 1

    targets = args.targets or list(EXTRACTORS.keys())
    extractions: dict[str, dict] = {}
    for name in targets:
        if name not in EXTRACTORS:
            print(f"unknown extractor: {name}", file=sys.stderr)
            return 2
        print(f"  building {name}.json ...", end=" ", flush=True)
        try:
            data = EXTRACTORS[name]()
            extractions[name] = data
            out = write_json(name, data)
            counts = {k: v for k, v in data.items() if k.endswith("_count")}
            count_str = " · ".join(f"{k}={v}" for k, v in counts.items())
            print(f"OK   {count_str}   →  {out.relative_to(REPO)}")
        except Exception as e:  # noqa: BLE001
            print(f"FAIL: {e}")
            raise

    # rebuild the search index from whatever we just produced
    if len(targets) == len(EXTRACTORS):
        print("  building search-index.json ...", end=" ", flush=True)
        idx = build_search_index(extractions)
        out = write_json("search-index", idx)
        print(f"OK   entries={idx['entry_count']}   →  {out.relative_to(REPO)}")
    else:
        # if partial build, reload existing extractions so the index is consistent
        all_data: dict[str, dict] = {}
        for name in EXTRACTORS:
            p = DATA_DIR / f"{name}.json"
            if p.exists():
                all_data[name] = json.loads(p.read_text(encoding="utf-8"))
        print("  rebuilding search-index.json ...", end=" ", flush=True)
        idx = build_search_index(all_data)
        out = write_json("search-index", idx)
        print(f"OK   entries={idx['entry_count']}   →  {out.relative_to(REPO)}")

    print()
    print(f"  data layer: {DATA_DIR.relative_to(REPO)}/  ({len(targets)} extractors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
