#!/usr/bin/env python3
"""
indexnow-ping.py: notify IndexNow-supporting search engines that the
Mediatrix pages have been updated.

IndexNow is a free protocol supported by Bing, Yandex, Naver, Seznam,
and Mojeek. One POST tells all of them; crawlers fetch within hours.

Reads the URL list from site/sitemap.xml so the canonical list of pages
stays single-sourced. The key file lives at site/<KEY>.txt and must
remain reachable at https://<host>/<KEY>.txt for the request to be
accepted.

Run after a deploy:
    python3 tools/indexnow-ping.py             # uses default host
    python3 tools/indexnow-ping.py --dry-run   # print the payload only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
HOST = "stella-maris.pages.dev"
KEY = "77509ec8556148efa7ada482267dddce"


def read_sitemap_urls() -> list[str]:
    sitemap = SITE / "sitemap.xml"
    if not sitemap.exists():
        sys.exit("  sitemap.xml not found; run regen-sitemap.py first")
    text = sitemap.read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print payload without sending")
    args = ap.parse_args()

    urls = read_sitemap_urls()
    if not urls:
        sys.exit("  no URLs in sitemap")

    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls + [f"https://{HOST}/sitemap.xml"],
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    req = urllib.request.Request(
        "https://api.indexnow.org/IndexNow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  IndexNow: HTTP {r.status}")
            print(f"  submitted {len(payload['urlList'])} URLs")
            print("  consumers: Bing, Yandex, Naver, Seznam, Mojeek")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        print(f"  body: {e.read().decode()[:300]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
