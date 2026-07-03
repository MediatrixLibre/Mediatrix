#!/usr/bin/env python3
"""
inject-seo.py: idempotent SEO meta injector for the Mediatrix pages.

Inserts per-page canonical, meta description, Open Graph, Twitter Card,
JSON-LD structured data, and critical-font preload into every `site/*.html`.

Idempotent: each injected block is wrapped in `<!-- SEO -->`/`<!-- /SEO -->`
markers, so re-runs replace the block in place rather than duplicating.

Run via:
    python3 tools/inject-seo.py             # inject / refresh on all pages
    python3 tools/inject-seo.py --check     # report missing or stale
    python3 tools/inject-seo.py --remove    # strip the SEO block from every page

No external dependencies. Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from textwrap import dedent

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
AUTHORITY_MAP_PATH = REPO / "tools" / "authority-map.json"

ORIGIN = "https://stella-maris.pages.dev"
OG_IMAGE = f"{ORIGIN}/og.png"
SITE_NAME = "Mediatrix"
PUBLISHER = "MediatrixLibre"
PUBLISHER_EMAIL = "mediatrixdev@proton.me"
DATE_PUBLISHED = "2026-05-15"

# Per-page metadata. Keys = HTML filenames.
PAGES = {
    "index.html": {
        "title": "Mediatrix: a Marian study library",
        "description": "A hand-set Marian study library: Mary's cooperation in the work of salvation, the Mediatrix and Co-Redemptrix questions, and the four Marian dogmas, drawn from patristic, medieval, and magisterial witness.",
        "type": "website",
    },
    "library.html": {
        "title": "The Library: twelve eras of Marian witness",
        "description": "From the early Fathers to Vatican II, Marian witness traced era by era.",
        "type": "article",
    },
    "anthology.html": {
        "title": "Anthology: sixty-five voices, in their own words",
        "description": "Sixty-five patristic, medieval, and magisterial voices on Mary, from Justin Martyr to Pope Leo XIV, each with provenance and translation notes.",
        "type": "article",
    },
    "rosary.html": {
        "title": "Rosary Companion: the twenty mysteries",
        "description": "Twenty rosary mysteries with scriptural and patristic gloss for each.",
        "type": "article",
    },
    "litany.html": {
        "title": "The Litany of Loreto: fifty-four titles, annotated",
        "description": "Each Marian invocation traced to its scriptural and patristic root.",
        "type": "article",
    },
    "office.html": {
        "title": "Office of Readings: a Marian sourcebook",
        "description": "Fifteen second-readings drawn from the patristic and magisterial canon for the Marian feasts.",
        "type": "article",
    },
    "akathist.html": {
        "title": "The Akathist Hymn: Greek and English facing",
        "description": "Twenty-four stanzas with the prooemion, in parallel Greek and English translation.",
        "type": "article",
    },
    "defense.html": {
        "title": "Twelve Protestant objections, twelve patristic replies",
        "description": "Marian doctrinal defense drawn from the Fathers, structured objection by objection.",
        "type": "article",
    },
    "ot-types.html": {
        "title": "Twenty-eight Old Testament types of Our Lady",
        "description": "The Burning Bush, the Ark, the Gate, the Tower: Marian types exegeted from the Old Testament.",
        "type": "article",
    },
    "nt-texts.html": {
        "title": "Three load-bearing New Testament Marian passages",
        "description": "Luke 1, John 2, and John 19, read with patristic care.",
        "type": "article",
    },
    "feasts.html": {
        "title": "Eighteen Marian feasts of the liturgical year",
        "description": "Date, rank, history, and the proper of the day for the eighteen Marian feasts.",
        "type": "article",
    },
    "apparitions.html": {
        "title": "Seven principal Church-approved apparitions",
        "description": "From Guadalupe to Akita: locus, message, and ecclesial recognition for the seven principal apparitions.",
        "type": "article",
    },
    "iconography.html": {
        "title": "Four canonical Marian icon-types with provenance",
        "description": "Hodegetria, Eleousa, Orans, and Theotokos enthroned: the four canonical Marian icon-types.",
        "type": "article",
    },
    "search.html": {
        "title": "Search the library",
        "description": "Client-side fuzzy search across the entire Marian corpus.",
        "type": "website",
    },
    "about.html": {
        "title": "About: methodology and provenance",
        "description": "How quotations are tagged, sourced, and translated in the Mediatrix study library.",
        "type": "website",
    },
    "devotions.html": {
        "title": "Marian devotional practices, in liturgical order",
        "description": "Consecration, scapular, medal, First Saturdays, Rosary, Angelus: eight Marian devotions with origin, form, and conditions.",
        "type": "article",
    },
    "catena.html": {
        "title": "The Threads of Witness",
        "description": "The sixty-five anthology witnesses re-gathered by doctrinal pole — Foundational, Co-Redemptrix, Mediatrix — and followed chronologically down the centuries.",
        "type": "article",
    },
    "concordance.html": {
        "title": "Concordance of Witnesses",
        "description": "A chronological concordance of the anthology's sixty-five Marian witnesses, with doctrinal pole, evidential provenance, and Wikidata/VIAF authority links.",
        "type": "article",
    },
    "scripture.html": {
        "title": "Index of Holy Scripture",
        "description": "Every biblical passage the library expounds or cites, gathered in the order of the Catholic canon: the Old Testament types and the load-bearing New Testament texts as primary treatments, with every page that comments on each verse.",
        "type": "article",
    },
    "timeline.html": {
        "title": "Chronological Witness Timeline",
        "description": "Sixty-five Marian witnesses arrayed across the centuries, with the dogmatic landmarks — Ephesus, Chalcedon, the Lateran, Ineffabilis Deus, Munificentissimus Deus — interleaved at their actual years to frame the doctrinal arc.",
        "type": "article",
    },
}

# Short, navigable names for the BreadcrumbList trail (the full SEO titles
# are too long to render well as a breadcrumb). index.html is the root and
# carries no breadcrumb of its own.
BREADCRUMB_NAMES = {
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
    "search.html": "Search",
    "about.html": "About",
    "devotions.html": "Devotions",
    "catena.html": "Threads of Witness",
    "concordance.html": "Concordance",
    "scripture.html": "Scripture Index",
    "timeline.html": "Witness Timeline",
}

# Critical fonts to preload. Picked the two faces that render first-fold
# text on every page (Cinzel display + Source Serif body roman).
CRITICAL_FONTS = [
    "fonts/cinzel-v26-060f4e56.woff2",
    "fonts/sourceserif4-v14-0bbe31e2.woff2",
]

# Speculation Rules: prefetch same-origin links on hover/pointerdown so
# in-session navigation is near-instant. prefetch (not prerender) keeps the
# CF Web Analytics beacon from firing for pages the reader never actually
# visits, and runs no page scripts speculatively. Chromium honours it;
# Safari/Firefox ignore the unknown script type with no ill effect. Allowed
# under the existing CSP script-src 'unsafe-inline'.
SPECULATION_RULES = dedent("""
    <script type="speculationrules">
    {
      "prefetch": [
        {
          "where": { "href_matches": "/*" },
          "eagerness": "moderate"
        }
      ]
    }
    </script>
""").strip()

MARK_START = "<!-- SEO -->"
MARK_END = "<!-- /SEO -->"


def page_url(page: str) -> str:
    """Canonical URL for a page: extensionless, matching the URL form CF Pages
    actually serves (it 308-redirects /page.html -> /page, so .html canonicals
    point at redirecting URLs and Google discards the signal). index.html is
    the origin root."""
    if page == "index.html":
        return f"{ORIGIN}/"
    return f"{ORIGIN}/{page.removesuffix('.html')}"


def build_authority_graph() -> str:
    """Emit a schema.org @graph of the anthology's authors with their Wikidata +
    VIAF `sameAs` links, from the curated tools/authority-map.json.

    Gated on `verified: true` — an unverified (machine-proposed) map is never
    emitted, so auto-matched authority links cannot leak into the live site.
    """
    if not AUTHORITY_MAP_PATH.exists():
        return ""
    data = json.loads(AUTHORITY_MAP_PATH.read_text(encoding="utf-8"))
    if not data.get("verified"):
        return ""
    nodes = []
    for r in data.get("authorities", []):
        qid = r.get("qid")
        if not qid:
            continue
        same_as = [f"https://www.wikidata.org/wiki/{qid}"]
        if r.get("viaf"):
            same_as.append(f"https://viaf.org/viaf/{r['viaf']}/")
        nodes.append(
            {
                "@type": "CreativeWork" if r.get("is_work") else "Person",
                "name": r["name"],
                "sameAs": same_as,
            }
        )
    if not nodes:
        return ""
    graph = {"@context": "https://schema.org", "@graph": nodes}
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(graph, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def build_block(page: str, meta: dict) -> str:
    title = meta["title"].replace('"', "&quot;")
    desc = meta["description"].replace('"', "&quot;")
    og_type = meta["type"]
    canonical = page_url(page)

    preload_links = "\n".join(
        f'<link rel="preload" as="font" type="font/woff2" crossorigin href="{f}" />'
        for f in CRITICAL_FONTS
    )

    json_ld_index = dedent(f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "WebSite",
          "name": "{SITE_NAME}",
          "alternateName": "An Editorial Marian Study Library",
          "url": "{ORIGIN}/",
          "description": "{desc}",
          "inLanguage": "en",
          "publisher": {{
            "@type": "Organization",
            "name": "{PUBLISHER}",
            "email": "{PUBLISHER_EMAIL}"
          }},
          "potentialAction": {{
            "@type": "SearchAction",
            "target": "{ORIGIN}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string"
          }}
        }}
        </script>
    """).strip()

    json_ld_article = dedent(f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "Article",
          "headline": "{title}",
          "description": "{desc}",
          "datePublished": "{DATE_PUBLISHED}",
          "inLanguage": "en",
          "author": {{ "@type": "Organization", "name": "{PUBLISHER}" }},
          "publisher": {{ "@type": "Organization", "name": "{PUBLISHER}" }},
          "image": "{OG_IMAGE}",
          "mainEntityOfPage": "{canonical}"
        }}
        </script>
    """).strip()

    json_ld = json_ld_index if page == "index.html" else json_ld_article

    # BreadcrumbList: Mediatrix (root) -> this page. The site is flat, so the
    # trail is two levels. index.html is the root and gets no breadcrumb.
    breadcrumb_json = ""
    crumb = BREADCRUMB_NAMES.get(page)
    if crumb:
        breadcrumb_json = dedent(f"""
            <script type="application/ld+json">
            {{
              "@context": "https://schema.org",
              "@type": "BreadcrumbList",
              "itemListElement": [
                {{ "@type": "ListItem", "position": 1, "name": "{SITE_NAME}", "item": "{ORIGIN}/" }},
                {{ "@type": "ListItem", "position": 2, "name": "{crumb}", "item": "{canonical}" }}
              ]
            }}
            </script>
        """).strip()
        json_ld = json_ld + "\n" + breadcrumb_json

    # Authority @graph: only on the anthology, where the 56 authors live.
    if page == "anthology.html":
        authority_graph = build_authority_graph()
        if authority_graph:
            json_ld = json_ld + "\n" + authority_graph

    apple_icons = dedent("""
        <link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon-180.png" />
        <link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png" />
        <link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png" />
    """).strip()

    return dedent(f"""
        {MARK_START}
        <link rel="canonical" href="{canonical}" />
        <link rel="alternate" type="application/rss+xml" title="Mediatrix — recent revisions" href="{ORIGIN}/feed.xml" />
        <meta name="description" content="{desc}" />

        {apple_icons}

        <meta property="og:type" content="{og_type}" />
        <meta property="og:title" content="{title}" />
        <meta property="og:description" content="{desc}" />
        <meta property="og:url" content="{canonical}" />
        <meta property="og:site_name" content="{SITE_NAME}" />
        <meta property="og:locale" content="en_US" />
        <meta property="og:image" content="{OG_IMAGE}" />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta property="og:image:alt" content="Mediatrix: a Marian study library. Stella Maris in gold on cream paper." />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="{title}" />
        <meta name="twitter:description" content="{desc}" />
        <meta name="twitter:image" content="{OG_IMAGE}" />

        {preload_links}

        {json_ld}

        {SPECULATION_RULES}
        {MARK_END}
    """).strip()


# Place the block right after the <title>...</title> tag.
TITLE_RE = re.compile(r"(<title>[^<]*</title>)", re.IGNORECASE)
EXISTING_BLOCK_RE = re.compile(
    re.escape(MARK_START) + r".*?" + re.escape(MARK_END),
    re.DOTALL,
)


def inject(page_path: Path, meta: dict) -> tuple[bool, str]:
    html = page_path.read_text(encoding="utf-8")
    block = build_block(page_path.name, meta)
    indented_block = "\n" + block + "\n"

    if EXISTING_BLOCK_RE.search(html):
        new_html = EXISTING_BLOCK_RE.sub(block, html, count=1)
        return new_html != html, new_html
    m = TITLE_RE.search(html)
    if not m:
        return False, html
    insertion_point = m.end()
    new_html = html[:insertion_point] + indented_block + html[insertion_point:]
    return True, new_html


def remove(page_path: Path) -> tuple[bool, str]:
    html = page_path.read_text(encoding="utf-8")
    new_html = EXISTING_BLOCK_RE.sub("", html)
    new_html = re.sub(r"\n{3,}", "\n\n", new_html)
    return new_html != html, new_html


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="report missing / stale, write nothing")
    g.add_argument("--remove", action="store_true", help="strip the SEO block from every page")
    args = ap.parse_args()

    pages_on_disk = sorted(p.name for p in SITE.glob("*.html"))
    missing_in_table = [p for p in pages_on_disk if p not in PAGES]
    missing_on_disk = [p for p in PAGES if p not in pages_on_disk]

    if missing_in_table:
        print(f"  warn: pages on disk but not in metadata table: {missing_in_table}")
    if missing_on_disk:
        print(f"  warn: pages in table but not on disk: {missing_on_disk}")

    changed = 0
    for page, meta in PAGES.items():
        path = SITE / page
        if not path.exists():
            continue
        if args.remove:
            did_change, new_html = remove(path)
        else:
            did_change, new_html = inject(path, meta)
        action = "remove" if args.remove else ("inject" if MARK_START not in path.read_text(encoding="utf-8") else "refresh")
        if args.check:
            html = path.read_text(encoding="utf-8")
            status = "ok" if MARK_START in html and not args.remove else "missing"
            print(f"  {status:7}  {page}")
            continue
        if did_change:
            path.write_text(new_html, encoding="utf-8")
            changed += 1
            print(f"  {action:7}  {page}")
        else:
            print(f"  noop     {page}")
    if not args.check:
        print(f"\n{changed} file(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
