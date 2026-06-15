#!/usr/bin/env python3
"""
build-scripture-index.py — generate the Scripture Index apparatus page.

A canonical-order index of every Scripture reference the library treats, turning
the dispersed biblical citations into one navigable concordance. Two tiers:

  PRIMARY treatments  — the verse IS the subject of an expository section:
                        the Old Testament types (ot-types.html#tN) and the
                        three load-bearing New Testament texts
                        (nt-texts.html#cana|#calvary|#revelation-12).
  ALSO DISCUSSED IN   — every other page whose prose cites the verse, scanned
                        from the committed HTML (page-level links).

The page reuses anthology.html's chrome (head/mast/footer/scripts) and the
existing `concordance` CSS classes — no new tokens, no new CSS. It indexes
INTO existing anchors and pages; it duplicates no quote text.

Inputs:  site/data/ot-types.json, site/data/nt-texts.json,
         site/*.html (visible prose), site/anthology.html (template)
Outputs: site/scripture.html, site/data/scripture-index.json

Run `make seo` afterwards to inject this page's SEO block + sitemap entry.

Python 3.9+, stdlib only.
"""
from __future__ import annotations

import html
import json
import re
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
DATA = SITE / "data"
TEMPLATE = SITE / "anthology.html"

# ── Canonical Catholic canon (73 books): order, display name, abbreviations ──
# Order index drives sort. Abbreviations are matched case-insensitively; the
# longest alternatives must precede shorter ones in the regex (handled below).
CANON: list[tuple[str, list[str]]] = [
    ("Genesis", ["Genesis", "Gen", "Gn"]),
    ("Exodus", ["Exodus", "Exod", "Exo", "Ex"]),
    ("Leviticus", ["Leviticus", "Lev", "Lv"]),
    ("Numbers", ["Numbers", "Num", "Nm"]),
    ("Deuteronomy", ["Deuteronomy", "Deut", "Dt"]),
    ("Joshua", ["Joshua", "Josh", "Jos"]),
    ("Judges", ["Judges", "Judg", "Jdg"]),
    ("Ruth", ["Ruth", "Ru"]),
    ("1 Samuel", ["1 Samuel", "1 Sam", "1 Sm", "1Samuel", "1Sam"]),
    ("2 Samuel", ["2 Samuel", "2 Sam", "2 Sm", "2Samuel", "2Sam"]),
    ("1 Kings", ["1 Kings", "1 Kgs", "1 Kg", "1Kings"]),
    ("2 Kings", ["2 Kings", "2 Kgs", "2 Kg", "2Kings"]),
    ("1 Chronicles", ["1 Chronicles", "1 Chron", "1 Chr", "1Chronicles"]),
    ("2 Chronicles", ["2 Chronicles", "2 Chron", "2 Chr", "2Chronicles"]),
    ("Ezra", ["Ezra"]),
    ("Nehemiah", ["Nehemiah", "Neh"]),
    ("Tobit", ["Tobit", "Tob", "Tb"]),
    ("Judith", ["Judith", "Jdt"]),
    ("Esther", ["Esther", "Esth", "Est"]),
    ("1 Maccabees", ["1 Maccabees", "1 Macc", "1 Mac"]),
    ("2 Maccabees", ["2 Maccabees", "2 Macc", "2 Mac"]),
    ("Job", ["Job"]),
    ("Psalms", ["Psalms", "Psalm", "Pss", "Ps"]),
    ("Proverbs", ["Proverbs", "Prov", "Prv", "Pr"]),
    ("Ecclesiastes", ["Ecclesiastes", "Eccles", "Eccl", "Qoheleth"]),
    ("Song of Songs", ["Song of Songs", "Song of Solomon", "Canticle of Canticles",
                       "Canticles", "Canticle", "Song", "Cant"]),
    ("Wisdom", ["Wisdom of Solomon", "Wisdom", "Wis"]),
    ("Sirach", ["Sirach", "Ecclesiasticus", "Sir", "Ecclus"]),
    ("Isaiah", ["Isaiah", "Isa", "Is"]),
    ("Jeremiah", ["Jeremiah", "Jer"]),
    ("Lamentations", ["Lamentations", "Lam"]),
    ("Baruch", ["Baruch", "Bar"]),
    ("Ezekiel", ["Ezekiel", "Ezek", "Ez"]),
    ("Daniel", ["Daniel", "Dan", "Dn"]),
    ("Hosea", ["Hosea", "Hos"]),
    ("Joel", ["Joel"]),
    ("Amos", ["Amos"]),
    ("Obadiah", ["Obadiah", "Obad"]),
    ("Jonah", ["Jonah", "Jon"]),
    ("Micah", ["Micah", "Mic"]),
    ("Nahum", ["Nahum", "Nah"]),
    ("Habakkuk", ["Habakkuk", "Hab"]),
    ("Zephaniah", ["Zephaniah", "Zeph", "Zep"]),
    ("Haggai", ["Haggai", "Hag"]),
    ("Zechariah", ["Zechariah", "Zech", "Zec"]),
    ("Malachi", ["Malachi", "Mal"]),
    ("Matthew", ["Matthew", "Matt", "Mt"]),
    ("Mark", ["Mark", "Mk"]),
    ("Luke", ["Luke", "Lk"]),
    ("John", ["John", "Jn"]),
    ("Acts", ["Acts of the Apostles", "Acts"]),
    ("Romans", ["Romans", "Rom"]),
    ("1 Corinthians", ["1 Corinthians", "1 Cor", "1Corinthians"]),
    ("2 Corinthians", ["2 Corinthians", "2 Cor", "2Corinthians"]),
    ("Galatians", ["Galatians", "Gal"]),
    ("Ephesians", ["Ephesians", "Eph"]),
    ("Philippians", ["Philippians", "Phil", "Php"]),
    ("Colossians", ["Colossians", "Col"]),
    ("1 Thessalonians", ["1 Thessalonians", "1 Thess", "1 Thes"]),
    ("2 Thessalonians", ["2 Thessalonians", "2 Thess", "2 Thes"]),
    ("1 Timothy", ["1 Timothy", "1 Tim", "1 Tm"]),
    ("2 Timothy", ["2 Timothy", "2 Tim", "2 Tm"]),
    ("Titus", ["Titus", "Tit"]),
    ("Philemon", ["Philemon", "Phlm"]),
    ("Hebrews", ["Hebrews", "Heb"]),
    ("James", ["James", "Jas"]),
    ("1 Peter", ["1 Peter", "1 Pet", "1 Pt"]),
    ("2 Peter", ["2 Peter", "2 Pet", "2 Pt"]),
    ("1 John", ["1 John", "1 Jn"]),
    ("2 John", ["2 John", "2 Jn"]),
    ("3 John", ["3 John", "3 Jn"]),
    ("Jude", ["Jude"]),
    ("Revelation", ["Revelation", "Apocalypse", "Rev", "Apoc"]),
]

CANON_ORDER = {name: i for i, (name, _) in enumerate(CANON)}
# Map every lowercased abbreviation -> canonical name.
ABBREV = {}
for canon_name, abbrs in CANON:
    for a in abbrs:
        ABBREV[a.lower()] = canon_name

# Build one big alternation, longest-first so "1 Samuel" beats "1 Sam" beats "Sam".
_alts = sorted({a for _, abbrs in CANON for a in abbrs}, key=len, reverse=True)
_BOOK_RE = "|".join(re.escape(a) for a in _alts)

# A reference with explicit chapter:verse (used for prose, high precision).
# Single verse or a hyphen range only — no comma-lists, which mis-capture
# adjacent refs like "Jn 2:3, 2:5" (two verses) as one "2:3, 2".
VERSE_RE = re.compile(
    r"\b(" + _BOOK_RE + r")\.?\s+(\d+):(\d+(?:[-–]\d+)?)",
    re.IGNORECASE,
)
# A looser reference allowing chapter-only / chapter-range (used for the curated
# ot-types `reference` field only, never for prose).
LOOSE_RE = re.compile(
    r"\b(" + _BOOK_RE + r")\.?\s*(\d+(?:[-–]\d+)?)?(?::(\d+(?:[-–]\d+)?(?:,\s*\d+)*))?",
    re.IGNORECASE,
)


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def canon_of(book_token: str) -> str | None:
    return ABBREV.get(book_token.lower().replace(".", "").strip())


def sort_key(book: str, chapter: int, verse: int) -> tuple[int, int, int]:
    return (CANON_ORDER.get(book, 999), chapter, verse)


def norm_chapter(ch: str | None) -> tuple[int, str]:
    """Return (sortable_chapter_int, display) from a chapter token like '3' or '2-3'."""
    if not ch:
        return (0, "")
    ch = ch.replace("–", "-")
    first = re.match(r"\d+", ch)
    return (int(first.group()) if first else 0, ch)


def norm_verse(v: str | None) -> tuple[int, str]:
    if not v:
        return (0, "")
    v = v.replace("–", "-")
    first = re.match(r"\d+", v)
    return (int(first.group()) if first else 0, v)


def ref_display(book: str, ch_disp: str, v_disp: str) -> str:
    if ch_disp and v_disp:
        return f"{book} {ch_disp}:{v_disp}"
    if ch_disp:
        return f"{book} {ch_disp}"
    return book


# ── Prose extraction ─────────────────────────────────────────────────────────

class _Visible(HTMLParser):
    """Collect visible text, skipping <script>/<style>/<head>."""
    def __init__(self):
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible_text(html_path: Path) -> str:
    p = _Visible()
    p.feed(html_path.read_text(encoding="utf-8"))
    return " ".join(p.parts)


# Pages excluded from the prose scan: the index itself, the apparatus pages
# (which only re-index), the 404, and the GSC stub.
SCAN_SKIP = {
    "scripture.html", "catena.html", "concordance.html", "search.html",
    "404.html", "googleb165be8284f6de2d.html",
}

PAGE_TITLES = {
    "index.html": "Home",
    "library.html": "The Library",
    "anthology.html": "Anthology",
    "rosary.html": "Rosary Companion",
    "litany.html": "Litany of Loreto",
    "office.html": "Office of Readings",
    "akathist.html": "Akathist Hymn",
    "defense.html": "Protestant Objections",
    "ot-types.html": "Old Testament Types",
    "nt-texts.html": "New Testament Texts",
    "feasts.html": "Marian Feasts",
    "apparitions.html": "Apparitions",
    "iconography.html": "Iconography",
    "about.html": "About",
    "devotions.html": "Devotions",
    "mater-populi-fidelis.html": "Mater Populi Fidelis",
}


# ── Index assembly ───────────────────────────────────────────────────────────

def new_entry(book, ch_sort, v_sort, ch_disp, v_disp):
    return {
        "ref": ref_display(book, ch_disp, v_disp),
        "book": book,
        "_sort": (CANON_ORDER.get(book, 999), ch_sort, v_sort),
        "primary": [],          # list of {label, href}
        "mentions": OrderedDict(),  # page filename -> title
    }


def key_of(book, ch_sort, v_sort):
    return (book, ch_sort, v_sort)


def add_primary(index, ref_text, label, href, *, loose=False):
    """Parse a curated reference (may be chapter-only/book-only) and attach a primary treatment."""
    m = (LOOSE_RE if loose else VERSE_RE).search(ref_text)
    if not m:
        return None
    book = canon_of(m.group(1))
    if not book:
        return None
    if loose:
        ch_sort, ch_disp = norm_chapter(m.group(2))
        v_sort, v_disp = norm_verse(m.group(3))
    else:
        ch_sort, ch_disp = norm_chapter(m.group(2))
        v_sort, v_disp = norm_verse(m.group(3))
    k = key_of(book, ch_sort, v_sort)
    if k not in index:
        index[k] = new_entry(book, ch_sort, v_sort, ch_disp, v_disp)
    index[k]["primary"].append({"label": label, "href": href})
    return k


def add_mentions_from_prose(index, page, title, text):
    seen_here = set()
    for m in VERSE_RE.finditer(text):
        book = canon_of(m.group(1))
        if not book:
            continue
        ch_sort, ch_disp = norm_chapter(m.group(2))
        v_sort, v_disp = norm_verse(m.group(3))
        k = key_of(book, ch_sort, v_sort)
        if k not in index:
            index[k] = new_entry(book, ch_sort, v_sort, ch_disp, v_disp)
        # record the page once per verse
        index[k]["mentions"].setdefault(page, title)
        seen_here.add(k)
    return len(seen_here)


def nt_slug(title: str) -> str:
    t = title.lower()
    if "cana" in t:
        return "cana"
    if "calvary" in t:
        return "calvary"
    if "revelation" in t or "apoc" in t:
        return "revelation-12"
    return ""


def build_index() -> dict:
    index: dict = {}

    # PRIMARY 1: Old Testament types
    ot = json.loads((DATA / "ot-types.json").read_text(encoding="utf-8"))
    ot_recs = next((v for v in ot.values() if isinstance(v, list)), ot) if isinstance(ot, dict) else ot
    for r in ot_recs:
        num = r.get("num")
        label = f"OT Types §{num} — {r.get('title', '').strip()}"
        href = f"ot-types.html#t{num}"
        ref = (r.get("reference") or "").strip()
        used = add_primary(index, ref, label, href, loose=True) if ref else None
        if used is None:
            # reference field empty/odd (e.g. t19): try the title's parenthetical
            add_primary(index, r.get("title", ""), label, href, loose=True)

    # PRIMARY 2: New Testament load-bearing texts
    nt = json.loads((DATA / "nt-texts.json").read_text(encoding="utf-8"))
    nt_recs = next((v for v in nt.values() if isinstance(v, list)), nt) if isinstance(nt, dict) else nt
    for r in nt_recs:
        title = r.get("title", "").strip()
        slug = nt_slug(title)
        if not slug:
            continue
        label = f"NT Texts — {title}"
        href = f"nt-texts.html#{slug}"
        # The scripture is inside the title, e.g. "Cana (John 2:1-11)"; Rev 12 has no colon.
        if not add_primary(index, title, label, href, loose=False):
            add_primary(index, title, label, href, loose=True)

    # SECONDARY: prose mentions across content pages
    for f in sorted(SITE.glob("*.html")):
        if f.name in SCAN_SKIP:
            continue
        title = PAGE_TITLES.get(f.name, f.stem.replace("-", " ").title())
        add_mentions_from_prose(index, f.name, title, visible_text(f))

    return index


# ── Rendering ────────────────────────────────────────────────────────────────

def chrome(slug: str, title: str) -> tuple[str, str]:
    src = TEMPLATE.read_text(encoding="utf-8")
    i = src.index("<main")
    j = src.index("</main>")
    top = src[:i].replace('data-page="anthology"', f'data-page="{slug}"', 1)
    top = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", top, count=1, flags=re.DOTALL)
    tail = src[j:]
    return top, tail


TESTAMENT_SPLIT = CANON_ORDER["Matthew"]


def render(index: dict) -> str:
    entries = sorted(index.values(), key=lambda e: e["_sort"])
    n_refs = len(entries)
    n_primary = sum(1 for e in entries if e["primary"])
    n_books = len({e["book"] for e in entries})

    out: list[str] = []
    out.append("<!-- APPARATUS:scripture -->")
    out.append('<header class="page-head">')
    out.append('<p class="kicker"><span class="dot"></span>Apparatus</p>')
    out.append("<h1>Index of Holy Scripture</h1>")
    out.append('<p class="lede">Every passage the library expounds or cites, gathered in the order of '
               'the Catholic canon. A <strong>primary</strong> entry marks where the verse is itself the '
               'subject of a section — the <a href="ot-types.html">Old Testament types</a> and the three '
               '<a href="nt-texts.html">load-bearing New Testament texts</a>. The remaining links show '
               'every page whose commentary touches the verse.</p>')
    out.append('<p class="concordance-summary">%d references &middot; %d books &middot; %d with a primary treatment</p>'
               % (n_refs, n_books, n_primary))
    out.append("</header>")

    def section(title_text, members):
        if not members:
            return
        out.append('<section class="thread">')
        out.append('<h2>%s</h2>' % esc(title_text))
        # group by book
        by_book: "OrderedDict[str, list]" = OrderedDict()
        for e in members:
            by_book.setdefault(e["book"], []).append(e)
        out.append('<dl class="concordance">')
        for book, refs in by_book.items():
            out.append('<dt class="era">%s</dt>' % esc(book))
            for e in refs:
                links = []
                for p in e["primary"]:
                    links.append('<a class="entry-name" href="%s">%s</a>'
                                 % (esc(p["href"]), esc(p["label"])))
                mentions = [
                    '<a href="%s">%s</a>' % (esc(pg), esc(ti))
                    for pg, ti in e["mentions"].items()
                ]
                meta = ""
                if mentions:
                    meta = '<span class="saint-source">also discussed in: %s</span>' % " &middot; ".join(mentions)
                primary_html = ("".join('<span class="prov verbatim">primary</span> ' for _ in e["primary"][:1]))
                out.append(
                    '<dd class="entry">'
                    '<span class="entry-name">%s</span>'
                    '%s%s%s'
                    '</dd>'
                    % (
                        esc(e["ref"]),
                        (" " + " ".join(links)) if links else "",
                        (" " + primary_html) if e["primary"] else "",
                        (" " + meta) if meta else "",
                    )
                )
        out.append("</dl>")
        out.append("</section>")

    ot_members = [e for e in entries if e["_sort"][0] < TESTAMENT_SPLIT]
    nt_members = [e for e in entries if e["_sort"][0] >= TESTAMENT_SPLIT]
    section("The Old Testament", ot_members)
    section("The New Testament", nt_members)

    out.append('<nav class="apparatus-nav" aria-label="Apparatus">'
               '<a href="catena.html">Threads of Witness</a> &middot; '
               '<a href="concordance.html">Concordance</a> &middot; '
               '<a href="anthology.html">Anthology</a></nav>')
    out.append("<!-- /APPARATUS:scripture -->")
    return "\n".join(out)


def main() -> int:
    index = build_index()
    body = render(index)
    top, tail = chrome("scripture", "Index of Holy Scripture")
    page = f'{top}<main id="main" class="prose">\n{body}\n</main>\n{tail[len("</main>"):]}'
    (SITE / "scripture.html").write_text(page, encoding="utf-8")

    # machine-readable sidecar
    serial = [
        {
            "ref": e["ref"], "book": e["book"],
            "primary": e["primary"],
            "mentions": list(e["mentions"].keys()),
        }
        for e in sorted(index.values(), key=lambda e: e["_sort"])
    ]
    (DATA / "scripture-index.json").write_text(
        json.dumps({"schema_version": 1, "count": len(serial), "references": serial},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    n_primary = sum(1 for e in index.values() if e["primary"])
    print(f"  wrote   site/scripture.html ({len(index)} refs, {n_primary} primary)")
    print(f"  wrote   site/data/scripture-index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
