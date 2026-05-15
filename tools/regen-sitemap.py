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
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
ORIGIN = "https://mediatrix-marian-library.pages.dev"
OG_IMAGE = f"{ORIGIN}/og.png"


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
    pages = sorted(SITE.glob("*.html"))
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
        loc = f"{ORIGIN}/" if page == "index.html" else f"{ORIGIN}/{page}"
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
