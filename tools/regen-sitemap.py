#!/usr/bin/env python3
"""
regen-sitemap.py: regenerate site/sitemap.xml from the HTML files on disk.

- One entry per `site/*.html`.
- `<lastmod>` reads each file's git mtime; falls back to today if not tracked.
- Drops `changefreq` and `priority` (Google ignores both).
- Includes `<image:image>` for any page that references og.png.

Idempotent. Safe to re-run on every deploy.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
ORIGIN = "https://stella-maris.pages.dev"
OG_IMAGE = f"{ORIGIN}/og.png"

# Not pages: error page + Google Search Console verification stub.
EXCLUDE = {"404.html"}


def load_page_url():
    """Import page_url from inject-seo.py (hyphenated filename) so the
    sitemap, the feed, and the canonicals all share one URL rule."""
    spec = importlib.util.spec_from_file_location("inject_seo", REPO / "tools" / "inject-seo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.page_url


def git_lastmod(rel_path: str) -> str:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            check=True, capture_output=True, text=True, cwd=REPO,
        )
        s = r.stdout.strip()
        if s:
            return s
    except subprocess.CalledProcessError:
        pass
    return dt.date.today().isoformat()


def main() -> int:
    page_url = load_page_url()
    pages = [
        p for p in sorted(SITE.glob("*.html"))
        if p.name not in EXCLUDE and not p.name.startswith("googleb")
    ]
    # Conventional ordering: index first, then alphabetical
    pages.sort(key=lambda p: (p.name != "index.html", p.name))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemaps-image/1.1">',
    ]
    for p in pages:
        rel = p.relative_to(REPO).as_posix()
        page = p.name
        loc = page_url(page)
        lastmod = git_lastmod(rel)
        out += [
            "  <url>",
            f"    <loc>{loc}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            "    <image:image>",
            f"      <image:loc>{OG_IMAGE}</image:loc>",
            "      <image:title>Mediatrix: a Marian study library</image:title>",
            "    </image:image>",
            "  </url>",
        ]
    out.append("</urlset>")

    sitemap = SITE / "sitemap.xml"
    sitemap.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"  wrote {sitemap.relative_to(REPO)} ({len(pages)} urls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
