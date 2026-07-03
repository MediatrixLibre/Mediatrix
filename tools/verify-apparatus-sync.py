#!/usr/bin/env python3
"""
verify-apparatus-sync.py — derived-page + card-count sync gate.

catena.html, concordance.html, scripture.html, and timeline.html are
committed build artifacts derived from anthology.json + anthology.html
chrome by the apparatus builders, then finished by inject-seo.py. Two
failure modes have actually bitten this repo, and this gate guards both:

  1. STALE DERIVED PAGES — anthology.html (or its data) was edited and
     committed without rebuilding the apparatus, so the derived pages
     silently shipped old chrome/content. (Real case: the pole-filter
     script added to anthology.html never reached catena/concordance/
     scripture; timeline shipped anthology's canonical + og identity to
     production because `make apparatus` ran without `make seo`.)
     Caught by rebuilding into a temp dir — INCLUDING the SEO injection
     pass — and diffing byte-for-byte against the committed files.

  2. CARD/DATA SPLIT — a witness hand-added to anthology.html without a
     matching corpus/JSON record (or vice versa), so counts and deep
     links disagree across layers. (Real case: St. Bartolo Longo existed
     as a 65th card while every other layer said 64.) Caught by asserting
     the anthology card anchors are exactly s1..sN for the JSON's N
     records.

Needs no corpus: everything derives from committed files, so it runs on
any checkout.

Exit codes:
  0  derived pages in sync AND card anchors match the data
  1  drift detected
  2  a builder or the SEO injector failed

Usage:
  ./tools/verify-apparatus-sync.py
  ./tools/verify-apparatus-sync.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
TOOLS = REPO / "tools"

BUILDERS = ["build-apparatus.py", "build-scripture-index.py", "build-timeline.py"]
DERIVED_PAGES = ["catena.html", "concordance.html", "scripture.html", "timeline.html"]
DERIVED_DATA = ["data/scripture-index.json"]

CARD_ID_RE = re.compile(r'<article class="saint-card" id="(s[^"]*)"')


def run_builders(out_dir: Path) -> list[str]:
    """Run the three apparatus builders into out_dir. Returns error strings."""
    errors = []
    env = {**os.environ, "MEDIATRIX_APPARATUS_OUT": str(out_dir)}
    for b in BUILDERS:
        r = subprocess.run(
            [sys.executable, str(TOOLS / b)],
            env=env, capture_output=True, text=True,
        )
        if r.returncode != 0:
            errors.append(f"{b} failed:\n{r.stderr or r.stdout}")
    return errors


def inject_seo(out_dir: Path) -> list[str]:
    """Apply inject-seo.py's per-page SEO block to the freshly built pages,
    exactly as `make seo` would, so the diff compares finished artifacts."""
    spec = importlib.util.spec_from_file_location("inject_seo", TOOLS / "inject-seo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    errors = []
    for page in DERIVED_PAGES:
        path = out_dir / page
        if not path.exists():
            errors.append(f"{page}: builder produced no file")
            continue
        meta = mod.PAGES.get(page)
        if meta is None:
            errors.append(f"{page}: missing from inject-seo PAGES table")
            continue
        _, new_html = mod.inject(path, meta)
        path.write_text(new_html, encoding="utf-8")
    return errors


def diff_artifacts(out_dir: Path) -> list[str]:
    problems = []
    for rel in DERIVED_PAGES + DERIVED_DATA:
        fresh, committed = out_dir / rel, SITE / rel
        if not fresh.exists():
            problems.append(f"{rel}: fresh build missing")
            continue
        if not committed.exists():
            problems.append(f"{rel}: committed file missing")
            continue
        if fresh.read_bytes() != committed.read_bytes():
            problems.append(f"{rel}: differs (fresh-build vs committed)")
    return problems


def check_cards() -> list[str]:
    problems = []
    data = json.loads((SITE / "data" / "anthology.json").read_text(encoding="utf-8"))
    records = data.get("saints", [])
    n = len(records)
    html = (SITE / "anthology.html").read_text(encoding="utf-8")
    ids = CARD_ID_RE.findall(html)
    if len(ids) != n:
        problems.append(f"anthology.html has {len(ids)} saint-cards but anthology.json has {n} records")
    expected = {f"s{i}" for i in range(1, n + 1)}
    actual = set(ids)
    for extra in sorted(actual - expected):
        problems.append(f"card anchor {extra!r} has no matching record (expected s1..s{n})")
    for missing in sorted(expected - actual, key=lambda s: int(s[1:])):
        problems.append(f"record {missing} has no card in anthology.html")
    if len(ids) != len(actual):
        problems.append("duplicate card anchors in anthology.html")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    card_problems = check_cards()

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        build_errors = run_builders(out_dir) or inject_seo(out_dir)
        if build_errors:
            for e in build_errors:
                print(f"  ! {e}")
            return 2
        sync_problems = diff_artifacts(out_dir)

    report = {
        "cards_match_data": not card_problems,
        "derived_in_sync": not sync_problems,
        "card_problems": card_problems,
        "sync_problems": sync_problems,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print()
        print("  Mediatrix apparatus-sync gate")
        print("  " + "-" * 50)
        print(f"  cards match data:    {'PASS' if report['cards_match_data'] else 'FAIL'}")
        for p in card_problems:
            print(f"      ! {p}")
        print(f"  derived in sync:     {'PASS' if report['derived_in_sync'] else 'FAIL'}")
        for p in sync_problems:
            print(f"      ! {p}")
        if sync_problems:
            print("      -> run `make apparatus` (which chains `make seo`) and commit the result.")
        if card_problems:
            print("      -> new witnesses go through the corpus: edit the corpus markdown,")
            print("         `make build-data`, hand-set the card with the matching sN anchor.")
        print()

    return 0 if report["cards_match_data"] and report["derived_in_sync"] else 1


if __name__ == "__main__":
    sys.exit(main())
