#!/usr/bin/env python3
"""
gen-llms-full.py — generate site/llms-full.txt, the whole library in one file.

llms.txt (hand-maintained) is the map; llms-full.txt is the territory: the
extracted main-content text of every editorial page, in reading order, for
AI agents that want the corpus without crawling twenty pages. Companion
convention to llms.txt (llmstxt.org).

Extraction: the <main> region of each committed page, with script/style/
svg/nav/form dropped, headings rendered as markdown #s, blockquotes as >,
list items as -, and entities unescaped. Deterministic: derives only from
committed HTML + the inject-seo PAGES table (no timestamps), so re-runs on
an unchanged tree are byte-identical.

Runs as part of `make seo`, so it regenerates whenever page SEO does and
cannot silently go stale.

Python 3.9+, stdlib only.
"""
from __future__ import annotations

import html as html_mod
import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
OUT = SITE / "llms-full.txt"

# search.html is a tool, not content; everything else ships.
EXCLUDE = {"search.html"}

HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}
SKIP_SUBTREES = {"script", "style", "svg", "nav", "form", "button", "template"}
BLOCK_TAGS = {"p", "li", "blockquote", "dt", "dd", "figcaption", "tr",
              "h1", "h2", "h3", "h4", "h5", "h6", "article", "section", "div"}


class MainTextExtractor(HTMLParser):
    """Collect readable text from the <main> subtree of a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = 0
        self.skip_depth = 0
        self.heading: str | None = None
        self.parts: list[str] = []
        self.line: list[str] = []

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.line)).strip()
        self.line = []
        if not text:
            return
        if self.heading:
            self.parts.append(f"\n{self.heading} {text}\n")
        else:
            self.parts.append(text + "\n")

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.in_main += 1
            return
        if not self.in_main:
            return
        if tag in SKIP_SUBTREES:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in HEADINGS:
            self._flush()
            self.heading = HEADINGS[tag]
        elif tag == "blockquote":
            self._flush()
            self.line.append("> ")
        elif tag == "li":
            self._flush()
            self.line.append("- ")
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "main" and self.in_main:
            self._flush()
            self.in_main -= 1
            return
        if not self.in_main:
            return
        if tag in SKIP_SUBTREES:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in HEADINGS:
            self._flush()
            self.heading = None
        elif tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self.in_main and not self.skip_depth:
            self.line.append(data)

    def text(self) -> str:
        self._flush()
        joined = "".join(self.parts)
        return re.sub(r"\n{3,}", "\n\n", joined).strip()


def load_inject_seo():
    spec = importlib.util.spec_from_file_location("inject_seo", REPO / "tools" / "inject-seo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    inject_seo = load_inject_seo()

    out = [
        "# Mediatrix — full text",
        "",
        "> A hand-set Marian study library: Mary's cooperation in the work of",
        "> salvation, the Mediatrix and Co-Redemptrix questions, and the four",
        "> Marian dogmas, drawn from patristic, medieval, and magisterial witness.",
        "",
        f"This file is the complete extracted text of every content page at",
        f"{inject_seo.ORIGIN}/ in reading order (companion to /llms.txt, which",
        "maps the site). Quotations carry their provenance tier inline",
        "(verbatim / liturgical / traditional / magisterial / disputed); see",
        "/about for the methodology. Cite anthology records by their stable",
        f"anchor, e.g. {inject_seo.ORIGIN}/anthology#s45.",
        "",
        "---",
    ]

    total = 0
    for page, meta in inject_seo.PAGES.items():
        if page in EXCLUDE:
            continue
        path = SITE / page
        if not path.exists():
            continue
        parser = MainTextExtractor()
        parser.feed(path.read_text(encoding="utf-8"))
        body = parser.text()
        if not body:
            continue
        url = inject_seo.page_url(page)
        out += [
            "",
            f"# {html_mod.unescape(meta['title'])}",
            "",
            f"URL: {url}",
            f"Summary: {html_mod.unescape(meta['description'])}",
            "",
            body,
            "",
            "---",
        ]
        total += 1

    OUT.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    size_kb = OUT.stat().st_size // 1024
    print(f"  wrote {OUT.relative_to(REPO)} ({total} pages, {size_kb}KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
