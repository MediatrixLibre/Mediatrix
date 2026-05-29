#!/usr/bin/env python3
"""
build-apparatus.py — generate the scholarly-apparatus pages from existing data.

Two derived, build-time pages that turn dormant anthology fields (pole, dates,
era) and the curated authority map into navigable scholarship. They do NOT
duplicate quote text — they INDEX into the hand-set anthology.html#sN anchors,
so there is no source-of-truth conflict and nothing to keep in sync by hand.

  catena.html       four doctrinal threads (Foundational / Co-Redemptrix /
                    Mediatrix / Both), each a chronological author index.
  concordance.html  master index of all 56 witnesses (dates, era, pole,
                    provenance) + the human-visible Wikidata/VIAF directory
                    (the anthology carries those links only in JSON-LD).

Both reuse anthology.html's page chrome (head/mast/footer/scripts) so they
inherit the design, fonts, service worker, and vestment system unchanged.
After generating, run `make seo` to fix each page's SEO block + sitemap.

Inputs:  site/data/anthology.json, tools/authority-map.json, site/anthology.html
Outputs: site/catena.html, site/concordance.html

Python 3.9+, stdlib only.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
ANTHOLOGY_JSON = SITE / "data" / "anthology.json"
AUTHORITY_MAP = REPO / "tools" / "authority-map.json"
TEMPLATE = SITE / "anthology.html"

POLE_NAMES = {
    "F": "Foundational",
    "CR": "Co-Redemptrix",
    "M": "Mediatrix",
    "B": "Both",
}
POLE_GLOSS = {
    "F": "Theotokos and the Immaculate Conception — the dogmatic ground on which Mediatrix and Co-Redemptrix stand.",
    "CR": "Mary's cooperation in the work of Redemption: the New Eve whose obedience undoes Eve's disobedience.",
    "M": "Mary's mediation of grace to the faithful: Mediatress of all graces, spiritual mother of believers.",
    "B": "Witnesses that name both cooperation in Redemption and mediation of grace together.",
}
# Doctrinal narrative order: ground, then the two poles, then the synthesis.
POLE_ORDER = ["F", "CR", "M", "B"]


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def sort_year(dates: str) -> int:
    """A sortable year from a free-form dates string."""
    if not dates:
        return 9999
    s = dates.replace("–", "-").replace("—", "-")
    m = re.search(r"\b(\d{3,4})\b", s)
    if m:
        return int(m.group(1))
    # "6th c." / "late 3rd century" -> mid-century estimate
    c = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s*c", s, re.IGNORECASE)
    if c:
        return int(c.group(1)) * 100 - 50
    return 9999


def load() -> tuple[list[dict], dict]:
    saints = json.loads(ANTHOLOGY_JSON.read_text(encoding="utf-8"))["saints"]
    amap_raw = json.loads(AUTHORITY_MAP.read_text(encoding="utf-8")).get("authorities", [])
    amap = {r["num"]: r for r in amap_raw}
    for s in saints:
        s["_year"] = sort_year(s.get("dates", ""))
        s["era_title"] = re.sub(r"\s*\(added [^)]*\)", "", s.get("era_title") or "")
    return saints, amap


# --- chrome ------------------------------------------------------------------

def chrome(slug: str, title: str) -> tuple[str, str]:
    """Return (top, tail) slices of anthology.html, retargeted for this page."""
    src = TEMPLATE.read_text(encoding="utf-8")
    i = src.index('<main')
    j = src.index("</main>")
    top = src[:i]
    tail = src[j:]  # includes </main> ... </html>
    top = top.replace('data-page="anthology"', f'data-page="{slug}"', 1)
    top = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", top, count=1, flags=re.DOTALL)
    return top, tail


def page(slug: str, title: str, body: str) -> str:
    top, tail = chrome(slug, title)
    return f'{top}<main id="main" class="prose">\n{body}\n</main>\n{tail[len("</main>"):]}'


# --- catena ------------------------------------------------------------------

def build_catena(saints: list[dict]) -> str:
    out: list[str] = []
    out.append('<!-- APPARATUS:catena -->')
    out.append('<header class="page-head">')
    out.append('<p class="kicker"><span class="dot"></span>Apparatus</p>')
    out.append('<h1>The Threads of Witness</h1>')
    out.append('<p class="lede">The same fifty-six voices of the <a href="anthology.html">Anthology</a>, '
               're-gathered by doctrinal pole and followed in order down the centuries. Each name links to its '
               'place in the Anthology.</p>')
    out.append('</header>')

    for pole in POLE_ORDER:
        members = sorted((s for s in saints if s.get("pole") == pole), key=lambda s: s["_year"])
        if not members:
            continue
        out.append('<section class="thread" aria-labelledby="thread-%s">' % pole.lower())
        out.append('<h2 id="thread-%s">%s <span class="pole">%s</span> '
                   '<span class="thread-count">%d witnesses</span></h2>'
                   % (pole.lower(), esc(POLE_NAMES[pole]), esc(pole), len(members)))
        out.append('<p class="thread-gloss">%s</p>' % esc(POLE_GLOSS[pole]))
        out.append('<ol class="thread-list">')
        for s in members:
            out.append(
                '<li><a href="anthology.html#s%d">%s</a>'
                '<span class="thread-meta">%s &middot; %s</span></li>'
                % (s["num"], esc(s["name"]), esc(s.get("dates", "")), esc(s.get("era_title", "")))
            )
        out.append('</ol>')
        out.append('</section>')

    out.append('<nav class="apparatus-nav" aria-label="Apparatus">'
               '<a href="concordance.html">Concordance &rarr;</a> &middot; '
               '<a href="anthology.html">Anthology</a></nav>')
    out.append('<!-- /APPARATUS:catena -->')
    return "\n".join(out)


# --- concordance -------------------------------------------------------------

def authority_links(rec: dict | None) -> str:
    if not rec:
        return ""
    parts = []
    if rec.get("qid"):
        parts.append('<a href="https://www.wikidata.org/wiki/%s" rel="external noopener">WD</a>' % esc(rec["qid"]))
    if rec.get("viaf"):
        parts.append('<a href="https://viaf.org/viaf/%s/" rel="external noopener">VIAF</a>' % esc(rec["viaf"]))
    return " ".join(parts)


def build_concordance(saints: list[dict], amap: dict) -> str:
    from collections import Counter
    by_pole = Counter(s.get("pole") for s in saints)
    by_prov = Counter(s.get("provenance") for s in saints)

    out: list[str] = []
    out.append('<!-- APPARATUS:concordance -->')
    out.append('<header class="page-head">')
    out.append('<p class="kicker"><span class="dot"></span>Apparatus</p>')
    out.append('<h1>Concordance of Witnesses</h1>')
    out.append('<p class="lede">Every witness in the <a href="anthology.html">Anthology</a>, '
               'in chronological order with doctrinal pole, evidential provenance, and a link to its '
               'authority record at Wikidata and VIAF. Names link into the Anthology.</p>')
    out.append('<p class="concordance-summary">%d witnesses &middot; %s &middot; %s</p>' % (
        len(saints),
        " · ".join("%d %s" % (by_pole[p], POLE_NAMES[p]) for p in POLE_ORDER if by_pole.get(p)),
        " · ".join("%d %s" % (n, prov) for prov, n in sorted(by_prov.items(), key=lambda kv: -kv[1]) if prov),
    ))
    out.append('</header>')

    # group by era, in chronological order of each era's earliest member
    eras: dict[str, list[dict]] = {}
    for s in saints:
        eras.setdefault(s.get("era_title") or "—", []).append(s)
    era_order = sorted(eras, key=lambda e: min(x["_year"] for x in eras[e]))

    out.append('<dl class="concordance">')
    for era in era_order:
        out.append('<dt class="era">%s</dt>' % esc(era))
        for s in sorted(eras[era], key=lambda x: x["_year"]):
            prov = s.get("provenance") or ""
            auth = authority_links(amap.get(s["num"]))
            out.append(
                '<dd class="entry">'
                '<a class="entry-name" href="anthology.html#s%d">%s</a>'
                '<span class="entry-dates">%s</span>'
                '<span class="saint-source">'
                '%s'
                '<span class="pole">%s</span>'
                '%s'
                '</span>'
                '</dd>'
                % (
                    s["num"], esc(s["name"]), esc(s.get("dates", "")),
                    ('<span class="prov %s">%s</span> ' % (esc(prov), esc(prov))) if prov else "",
                    esc(s.get("pole", "")),
                    (' <span class="authority">%s</span>' % auth) if auth else "",
                )
            )
    out.append('</dl>')
    out.append('<nav class="apparatus-nav" aria-label="Apparatus">'
               '<a href="catena.html">&larr; Threads of Witness</a> &middot; '
               '<a href="anthology.html">Anthology</a></nav>')
    out.append('<!-- /APPARATUS:concordance -->')
    return "\n".join(out)


def main() -> int:
    saints, amap = load()
    (SITE / "catena.html").write_text(
        page("catena", "The Threads of Witness · Mediatrix", build_catena(saints)),
        encoding="utf-8",
    )
    (SITE / "concordance.html").write_text(
        page("concordance", "Concordance of Witnesses · Mediatrix", build_concordance(saints, amap)),
        encoding="utf-8",
    )
    print("  wrote site/catena.html + site/concordance.html (%d witnesses)" % len(saints))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
