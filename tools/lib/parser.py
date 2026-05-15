"""
Markdown parsing primitives shared by every Mediatrix extractor.

The source files at $MARIOLOGY_CORPUS/ follow consistent conventions:

  ---
  YAML frontmatter
  ---

  # Title
  > Pull-quote
  ## Section
  ### Numbered item
  > **Greek / Latin** (Source): text
  > **English:** translation
  - **Source:** ...
  - **Provenance:** VERBATIM / TRADITIONAL / DISPUTED / LITURGICAL / MAGISTERIAL
  - **Pole:** M / CR / B / F

No external dependencies. Python 3.9+. Pure stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# --- frontmatter --------------------------------------------------------

_FRONTMATTER_DELIM = re.compile(r"^---\s*$")
_KEY_VALUE = re.compile(r"^(\w[\w-]*)\s*:\s*(.*)$")
_LIST_ITEM = re.compile(r"^\s+-\s+(.+)$")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """
    Return (frontmatter_dict, body_without_frontmatter).

    Handles simple YAML: string values, lists. Does not handle nested maps
    (none of the Mediatrix files use them). Strips surrounding quotes.
    """
    lines = text.splitlines(keepends=True)
    if not lines or not _FRONTMATTER_DELIM.match(lines[0]):
        return {}, text

    end = None
    for i, line in enumerate(lines[1:], start=1):
        if _FRONTMATTER_DELIM.match(line):
            end = i
            break
    if end is None:
        return {}, text

    fm: dict[str, object] = {}
    current_key: str | None = None
    for line in lines[1:end]:
        stripped = line.rstrip("\n")
        if not stripped.strip():
            continue
        m = _KEY_VALUE.match(stripped)
        if m:
            key, value = m.group(1), m.group(2).strip()
            current_key = key
            if value == "":
                fm[key] = []
            else:
                fm[key] = _strip_quotes(value)
        else:
            li = _LIST_ITEM.match(stripped)
            if li and current_key is not None:
                existing = fm.get(current_key)
                if not isinstance(existing, list):
                    fm[current_key] = [] if existing == "" else [existing]
                fm[current_key].append(_strip_quotes(li.group(1).strip()))  # type: ignore[union-attr]

    body = "".join(lines[end + 1 :])
    return fm, body


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


# --- sections -----------------------------------------------------------

_HEADER = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Section:
    """A markdown section: header + body lines until the next header at <= level."""

    level: int
    title: str
    body: str
    children: list[Section] = field(default_factory=list)

    def find_all(self, level: int) -> list[Section]:
        out: list[Section] = []
        for c in self.children:
            if c.level == level:
                out.append(c)
            out.extend(c.find_all(level))
        return out

    def first_paragraph(self) -> str:
        """First non-empty block before the first blockquote / list / header."""
        para: list[str] = []
        for line in self.body.splitlines():
            stripped = line.strip()
            if not stripped:
                if para:
                    return " ".join(para).strip()
                continue
            if stripped.startswith(("- ", "> ", "#", "|", "*")):
                if para:
                    return " ".join(para).strip()
                continue
            para.append(stripped)
        return " ".join(para).strip()


def split_sections(text: str) -> Section:
    """
    Build a tree of Section objects from a markdown body. The root section
    has level 0 and contains everything.
    """
    root = Section(level=0, title="", body="")
    stack: list[Section] = [root]
    current_body: list[str] = []

    for line in text.splitlines(keepends=True):
        m = _HEADER.match(line.rstrip("\n"))
        if m:
            # flush body to current top of stack
            stack[-1].body += "".join(current_body)
            current_body = []
            level = len(m.group(1))
            title = m.group(2)
            sec = Section(level=level, title=title, body="")
            # pop stack to find parent
            while stack and stack[-1].level >= level:
                stack.pop()
            (stack[-1] if stack else root).children.append(sec)
            stack.append(sec)
        else:
            current_body.append(line)
    if stack:
        stack[-1].body += "".join(current_body)
    return root


# --- blockquote + metadata-line extraction ------------------------------

_BLOCKQUOTE_LINE = re.compile(r"^>\s?(.*)$")
_BOLD_LABEL_LINE = re.compile(r"^-\s+\*\*(.+?)\*\*[:\.]?\s*(.*)$")


def extract_blockquotes(body: str) -> list[str]:
    """
    Return each contiguous blockquote in `body` as a single string (lines joined).
    """
    out: list[str] = []
    buf: list[str] = []
    for line in body.splitlines():
        m = _BLOCKQUOTE_LINE.match(line)
        if m:
            buf.append(m.group(1))
        else:
            if buf:
                out.append(" ".join(s for s in buf if s.strip() != "").strip())
                buf = []
    if buf:
        out.append(" ".join(s for s in buf if s.strip() != "").strip())
    return out


def extract_metadata_lines(body: str) -> dict[str, str]:
    """
    Lines of the form `- **Key:** value` become {key.lower(): value}.
    """
    out: dict[str, str] = {}
    for line in body.splitlines():
        m = _BOLD_LABEL_LINE.match(line)
        if m:
            key = m.group(1).strip().lower().rstrip(":")
            val = m.group(2).strip()
            out[key] = val
    return out


# --- inline cleanup helpers ---------------------------------------------

_MD_LINK = re.compile(r"\[\[(.+?)\]\]")
_MD_EMPHASIS = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"\*(.+?)\*|_(.+?)_")


def strip_markdown(s: str) -> str:
    """Strip basic markdown wrappers for plain-text fields."""
    s = _MD_LINK.sub(lambda m: m.group(1), s)
    s = _MD_EMPHASIS.sub(lambda m: m.group(1), s)
    s = _MD_ITALIC.sub(lambda m: m.group(1) or m.group(2) or "", s)
    return s.strip()


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --- provenance parsing -------------------------------------------------

_PROVENANCE_TIERS = {
    "VERBATIM",
    "TRADITIONAL",
    "DISPUTED",
    "LITURGICAL",
    "MAGISTERIAL",
}


def parse_provenance(line: str) -> str | None:
    """Detect provenance tier in the canonical markdown style."""
    up = line.upper()
    for tier in _PROVENANCE_TIERS:
        if tier in up:
            return tier.lower()
    return None


_POLE_TOKENS = {"M", "CR", "B", "F"}


def parse_pole(line: str) -> str | None:
    """Pole tokens M / CR / B / F. Look for the first match."""
    # match standalone tokens, not e.g. "M" inside "Mediatrix"
    for tok in ("CR", "M", "B", "F"):
        if re.search(rf"\b{tok}\b", line):
            return tok
    return None


# --- file IO helpers ----------------------------------------------------


def read_source(path: Path) -> tuple[dict[str, object], Section]:
    """
    Open a markdown file, parse frontmatter, return (frontmatter, root_section).
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    return fm, split_sections(body)


# --- iteration over numbered items --------------------------------------

_NUMBERED_HEADER = re.compile(r"^\s*(\d+)\.?\s+(.*?)\s*$")


def parse_numbered_header(title: str) -> tuple[int | None, str]:
    """
    Header titles like "1. The Annunciation (Luke 1:26-38)" → (1, "The Annunciation (Luke 1:26-38)")
    """
    m = _NUMBERED_HEADER.match(title)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, title.strip()
