#!/usr/bin/env python3
"""
gen-feed.py: regenerate site/feed.xml (RSS 2.0) from the page metadata.

A reference library is not a blog, but a feed lets readers and Catholic
aggregators subscribe to know when a section is revised. Each content page
is one <item>; the page's git commit date is its <pubDate>. Items are
ordered most-recently-revised first.

Single-sources page titles/descriptions from inject-seo.py's PAGES table
(imported via importlib because the filename carries a hyphen) and reuses
the same git-mtime logic as regen-sitemap.py. index.html (the hero) and
search.html (a tool, not content) are excluded.

Idempotent. Safe to re-run on every deploy.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import subprocess
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
ORIGIN = "https://stella-maris.pages.dev"
FEED_TITLE = "Mediatrix — a Marian study library"
FEED_DESC = (
    "Revisions to the Mediatrix study library: sixteen hand-designed pages "
    "on Mary as Mediatrix and Co-Redemptrix, drawn from patristic, medieval, "
    "and magisterial witness."
)
EXCLUDE = {"index.html", "search.html", "404.html"}


def load_inject_seo():
    """Import inject-seo.py (hyphenated filename) for its PAGES table and
    page_url rule, so feed links match the canonicals exactly."""
    spec = importlib.util.spec_from_file_location("inject_seo", REPO / "tools" / "inject-seo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_lastmod_date(rel_path: str) -> dt.date:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            check=True, capture_output=True, text=True, cwd=REPO,
        )
        s = r.stdout.strip()
        if s:
            return dt.date.fromisoformat(s)
    except (subprocess.CalledProcessError, ValueError):
        pass
    return dt.date.today()


def rfc822(d: dt.date) -> str:
    # RSS pubDate must be RFC-822. Anchor to midnight UTC.
    return format_datetime(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc))


def main() -> int:
    inject_seo = load_inject_seo()
    pages = inject_seo.PAGES

    items = []
    for page, meta in pages.items():
        if page in EXCLUDE:
            continue
        path = SITE / page
        if not path.exists():
            continue
        rel = path.relative_to(REPO).as_posix()
        d = git_lastmod_date(rel)
        items.append((d, page, meta))

    # Most-recently-revised first; tie-break alphabetically for stable output.
    items.sort(key=lambda t: (t[0], t[1]), reverse=True)

    build_date = rfc822(max((d for d, _, _ in items), default=dt.date.today()))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(FEED_TITLE)}</title>",
        f"    <link>{ORIGIN}/</link>",
        f'    <atom:link href="{ORIGIN}/feed.xml" rel="self" type="application/rss+xml" />',
        f"    <description>{escape(FEED_DESC)}</description>",
        "    <language>en</language>",
        f"    <lastBuildDate>{build_date}</lastBuildDate>",
        f"    <generator>tools/gen-feed.py</generator>",
    ]

    for d, page, meta in items:
        loc = inject_seo.page_url(page)
        out += [
            "    <item>",
            f"      <title>{escape(meta['title'])}</title>",
            f"      <link>{loc}</link>",
            f'      <guid isPermaLink="true">{loc}</guid>',
            f"      <description>{escape(meta['description'])}</description>",
            f"      <pubDate>{rfc822(d)}</pubDate>",
            "    </item>",
        ]

    out += ["  </channel>", "</rss>"]

    feed = SITE / "feed.xml"
    feed.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  wrote {feed.relative_to(REPO)} ({len(items)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
