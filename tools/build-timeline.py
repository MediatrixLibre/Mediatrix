#!/usr/bin/env python3
"""
build-timeline.py — generate the Chronological Witness Timeline apparatus.

A century-banded timeline that arrays the anthology's witnesses across the
centuries with the Marian dogmas and conciliar definitions as landmarks.
The point of difference from the Concordance (which already lists witnesses
chronologically by era):

  - Uniform time axis: centuries (eras vary in size; centuries don't).
  - Dogmatic landmarks interleaved at their actual years — Ephesus 431,
    Chalcedon 451, the Lateran 649, Ineffabilis Deus 1854, Munificentissimus
    Deus 1950 — so the doctrinal arc is visible alongside the voices.
  - Tightest information density: name · dates · pole only. Provenance and
    authority links belong to the Concordance.

Year resolution:
  - sort key       = MIN year extracted from the dates field (or name fallback)
  - century key    = midpoint of (min, max) years, so a witness with a long
                     life or one who works into a later century falls in the
                     right bucket (Justin Martyr c. 100–c. 165 → II century,
                     not I; Leo XIV b. 1955 + work 2025 → XX, not XXI)
  - empty dates    = fall back to the "Nth century" pattern in the name
                     (Sub Tuum Praesidium → III century from its qualifier)

Reuses anthology.html chrome and the existing concordance CSS classes; emits
no new CSS. Indexes into anthology.html#sN; duplicates no quote text.

Inputs:  site/data/anthology.json, site/anthology.html (template)
Outputs: site/timeline.html

Run `make seo` afterwards to inject this page's SEO block + sitemap entry.

Python 3.9+, stdlib only.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
# Output dir. Overridable via MEDIATRIX_APPARATUS_OUT so the apparatus-sync
# gate can rebuild into a temp dir without touching site/. Inputs (template
# chrome, data JSON) always read from site/.
OUT = Path(os.environ.get("MEDIATRIX_APPARATUS_OUT") or SITE).expanduser()
ANTHOLOGY_JSON = SITE / "data" / "anthology.json"
TEMPLATE = SITE / "anthology.html"

ROMAN = [
    "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI",
]

# Dogmatic + conciliar landmarks. Each tuple: (year, title, gloss). Kept short
# so the timeline reads as voices-plus-anchors, not voices-plus-essays.
LANDMARKS: list[tuple[int, str, str]] = [
    (431,  "Council of Ephesus",        "Mary defined Theotokos against Nestorius."),
    (451,  "Council of Chalcedon",      "the two natures of Christ; the Theotokos confessed."),
    (649,  "Lateran Council",           "Mary's perpetual virginity defined under Pope St. Martin I."),
    (1854, "Ineffabilis Deus",          "Bl. Pius IX defines the Immaculate Conception."),
    (1950, "Munificentissimus Deus",    "Ven. Pius XII defines the Assumption."),
]


# ── Year parsing ─────────────────────────────────────────────────────────────

def _years_in(text: str) -> list[int]:
    return [int(m.group()) for m in re.finditer(r"\b(\d{3,4})\b", text or "")]


def _century_fallback(text: str) -> int | None:
    """Parse 'late 3rd century' / 'Nth c.' patterns. Returns century int, or None."""
    m = re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)\s*c", text or "", re.IGNORECASE)
    return int(m.group(1)) if m else None


def sort_year(dates: str, name: str = "") -> int:
    """Stable sort key: earliest year referenced. Falls back to name's 'Nth c.'."""
    ys = _years_in(dates) or _years_in(name)
    if ys:
        return min(ys)
    c = _century_fallback(dates) or _century_fallback(name)
    return c * 100 - 50 if c else 9999


def place_century(dates: str, name: str = "") -> int:
    """Century bucket: midpoint of (min, max), so floruit lands correctly."""
    ys = _years_in(dates) or _years_in(name)
    if ys:
        mid = (min(ys) + max(ys)) / 2
        return int(mid - 1) // 100 + 1
    c = _century_fallback(dates) or _century_fallback(name)
    return c if c else 99


# ── Rendering ────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def chrome(slug: str, title: str) -> tuple[str, str]:
    src = TEMPLATE.read_text(encoding="utf-8")
    i = src.index("<main")
    j = src.index("</main>")
    top = src[:i].replace('data-page="anthology"', f'data-page="{slug}"', 1)
    top = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", top, count=1, flags=re.DOTALL)
    tail = src[j:]
    return top, tail


def roman(c: int) -> str:
    return ROMAN[c] if 0 < c < len(ROMAN) else str(c)


def century_label(c: int) -> str:
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(c if c < 20 else c % 10, "th")
    if c in (11, 12, 13):
        suffix = "th"
    return f"{c}{suffix} century"


def build() -> str:
    saints = json.loads(ANTHOLOGY_JSON.read_text(encoding="utf-8"))["saints"]
    for s in saints:
        s["_sort"] = sort_year(s.get("dates", ""), s.get("name", ""))
        s["_cent"] = place_century(s.get("dates", ""), s.get("name", ""))

    # Build the chronological stream: every event tagged ("witness"|"landmark"),
    # paired with a (year, kind-rank, index) sort key so same-year ties resolve
    # witness-before-landmark when they coincide.
    stream: list[tuple[int, int, str, object]] = []
    for s in saints:
        stream.append((s["_sort"], 0, "witness", s))
    for year, title, gloss in LANDMARKS:
        stream.append((year, 1, "landmark", (title, gloss)))
    stream.sort(key=lambda t: (t[0], t[1]))

    # Group by century. Witnesses use the midpoint-derived _cent; landmarks
    # (single year) just bucket on that year.
    by_century: dict[int, list[tuple[str, int, object]]] = {}
    for year, _, kind, payload in stream:
        if kind == "witness":
            c = payload["_cent"]
        else:
            c = (year - 1) // 100 + 1
        by_century.setdefault(c, []).append((kind, year, payload))

    centuries_sorted = sorted(by_century.keys())

    # year range for the summary: earliest year ANY witness references → latest year ANY
    # witness references (so Leo XIV b. 1955 + elected 2025 contributes 2025, not 1955)
    all_years: list[int] = []
    for s in saints:
        all_years.extend(_years_in(s.get("dates", "")))
        all_years.extend(_years_in(s.get("name", "")))
    year_min, year_max = (min(all_years), max(all_years)) if all_years else (0, 0)

    out: list[str] = []
    out.append("<!-- APPARATUS:timeline -->")
    out.append('<header class="page-head">')
    out.append('<p class="kicker"><span class="dot"></span>Apparatus</p>')
    out.append("<h1>Chronological Witness Timeline</h1>")
    out.append('<p class="lede">The %d voices of the <a href="anthology.html">Anthology</a> '
               'arrayed across the centuries, with the Marian dogmas and the conciliar definitions as '
               'landmarks. Names link into the Anthology; landmarks frame the dogmatic arc.</p>'
               % len(saints))
    out.append('<p class="concordance-summary">%d witnesses &middot; %d landmarks &middot; '
               '%d centuries &middot; c. %d &ndash; %d</p>'
               % (len(saints), len(LANDMARKS), len(centuries_sorted), year_min, year_max))
    out.append("</header>")

    out.append('<dl class="concordance">')
    for c in centuries_sorted:
        out.append(f'<dt class="era">{esc(roman(c))} &middot; {esc(century_label(c))}</dt>')
        for kind, year, payload in by_century[c]:
            if kind == "witness":
                s = payload
                out.append(
                    '<dd class="entry">'
                    '<a class="entry-name" href="anthology.html#s%d">%s</a>'
                    '<span class="entry-dates">%s</span>'
                    '<span class="saint-source"><span class="pole">%s</span></span>'
                    '</dd>'
                    % (
                        s["num"],
                        esc(s["name"]),
                        esc(s.get("dates", "")),
                        esc(s.get("pole", "")),
                    )
                )
            else:
                title, gloss = payload
                # Landmark dd: reuse the same column scaffold so the grid stays
                # honest; differentiate via italic title (no link) and a small-caps
                # year-as-name. No new CSS.
                out.append(
                    '<dd class="entry">'
                    '<span class="entry-name"><em>%s</em></span>'
                    '<span class="entry-dates">%d</span>'
                    '<span class="saint-source">%s</span>'
                    '</dd>'
                    % (esc(title), year, esc(gloss))
                )
    out.append("</dl>")

    out.append('<nav class="apparatus-nav" aria-label="Apparatus">'
               '<a href="catena.html">Threads of Witness</a> &middot; '
               '<a href="concordance.html">Concordance</a> &middot; '
               '<a href="scripture.html">Scripture Index</a> &middot; '
               '<a href="anthology.html">Anthology</a></nav>')
    out.append("<!-- /APPARATUS:timeline -->")
    return "\n".join(out)


def main() -> int:
    body = build()
    top, tail = chrome("timeline", "Chronological Witness Timeline")
    page = f'{top}<main id="main" class="prose">\n{body}\n</main>\n{tail[len("</main>"):]}'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timeline.html").write_text(page, encoding="utf-8")

    # Stats for the run line
    saints = json.loads(ANTHOLOGY_JSON.read_text(encoding="utf-8"))["saints"]
    print(f"  wrote   site/timeline.html ({len(saints)} witnesses + {len(LANDMARKS)} landmarks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
