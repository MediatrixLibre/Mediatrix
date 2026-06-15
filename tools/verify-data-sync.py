#!/usr/bin/env python3
"""
verify-data-sync.py — reproducible-build + data-in-sync gate.

site/data/*.json are committed build artifacts generated from the markdown
corpus by build-mediatrix.py. Two failure modes have actually bitten this
repo, and this gate guards both:

  1. NON-REPRODUCIBLE BUILD — a parser bug made provenance hash-seed
     dependent, so two builds of the same corpus disagreed. Catch it by
     building twice with different PYTHONHASHSEED and diffing.

  2. STALE / DRIFTED ARTIFACTS — the committed JSON silently diverged from
     what the corpus now produces (corpus edited without rebuild, or JSON
     hand-edited). Catch it by diffing a fresh build against the committed
     files.

Timestamp fields (generated_at, source_mtime) are expected to differ and are
ignored in every comparison.

Requires MARIOLOGY_CORPUS to point at the corpus (same as build-mediatrix.py).

Exit codes:
  0  reproducible AND in sync
  1  non-reproducible build OR committed artifacts drifted
  2  corpus not found / build failed

Usage:
  MARIOLOGY_CORPUS=... ./tools/verify-data-sync.py
  MARIOLOGY_CORPUS=... ./tools/verify-data-sync.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "site" / "data"
BUILD = REPO / "tools" / "build-mediatrix.py"
IGNORE_KEYS = {"generated_at", "source_mtime"}
# Data sidecars NOT generated from the markdown corpus (they derive from the
# committed HTML + already-built data), so they are out of scope for this
# corpus-reproducibility gate. Their own builders own their integrity.
NON_CORPUS_DATA = {"scripture-index.json"}


def _strip_ts(obj):
    if isinstance(obj, dict):
        return {k: _strip_ts(v) for k, v in obj.items() if k not in IGNORE_KEYS}
    if isinstance(obj, list):
        return [_strip_ts(x) for x in obj]
    return obj


def _load_dir(d: Path) -> dict[str, object]:
    out = {}
    for f in sorted(d.glob("*.json")):
        if f.name in NON_CORPUS_DATA:
            continue
        out[f.name] = _strip_ts(json.loads(f.read_text(encoding="utf-8")))
    return out


def build_into(out_dir: Path, hashseed: str) -> None:
    env = {**os.environ, "MEDIATRIX_DATA_OUT": str(out_dir), "PYTHONHASHSEED": hashseed}
    if "MARIOLOGY_CORPUS" not in env:
        raise SystemExit("  MARIOLOGY_CORPUS not set; point it at the corpus.")
    r = subprocess.run(
        [sys.executable, str(BUILD)],
        env=env, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"  build failed (seed {hashseed}):\n{r.stderr or r.stdout}")


def diff_sets(a: dict, b: dict, label_a: str, label_b: str) -> list[str]:
    problems = []
    files = sorted(set(a) | set(b))
    for f in files:
        if f not in a:
            problems.append(f"{f}: present in {label_b} but missing in {label_a}")
        elif f not in b:
            problems.append(f"{f}: present in {label_a} but missing in {label_b}")
        elif a[f] != b[f]:
            problems.append(f"{f}: differs ({label_a} vs {label_b})")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        d1, d2 = Path(td) / "a", Path(td) / "b"
        d1.mkdir(); d2.mkdir()
        build_into(d1, "1")
        build_into(d2, "2")
        build1, build2 = _load_dir(d1), _load_dir(d2)
        committed = _load_dir(DATA)

    repro_problems = diff_sets(build1, build2, "build#1", "build#2")
    sync_problems = diff_sets(build1, committed, "fresh-build", "committed")

    report = {
        "reproducible": not repro_problems,
        "in_sync": not sync_problems,
        "reproducibility_problems": repro_problems,
        "sync_problems": sync_problems,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print()
        print("  Mediatrix data-sync gate")
        print("  " + "-" * 50)
        print(f"  reproducible build:  {'PASS' if report['reproducible'] else 'FAIL'}")
        if repro_problems:
            for p in repro_problems:
                print(f"      ! {p}")
        print(f"  committed in sync:   {'PASS' if report['in_sync'] else 'FAIL'}")
        if sync_problems:
            for p in sync_problems:
                print(f"      ! {p}")
            print("      -> run `make build-data` and commit the result.")
        print()

    return 0 if report["reproducible"] and report["in_sync"] else 1


if __name__ == "__main__":
    sys.exit(main())
