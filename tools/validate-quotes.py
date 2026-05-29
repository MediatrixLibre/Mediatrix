#!/usr/bin/env python3
"""
validate-quotes.py — provenance & source integrity gate for the anthology.

Phase 1 of the quote-fidelity programme. Where validate-references.py checks
that every *name* referenced across pages resolves to an anthology record,
this checks that every *quote* in anthology.json is properly sourced and
provenance-tagged. It does NOT verify quote text against primary sources
(that is Phase 3, which needs an external corpus); it enforces that the
metadata which makes such verification possible is present and well-formed.

Severity tiers:
  ERROR    blocks --strict (push/CI gate). A correctness defect.
             - missing/empty `source` citation
             - `provenance` not in the controlled vocabulary
             - record is unrenderable (neither `english` nor `original` text)
  WARN     reported, does not block. A fidelity gap to backfill.
             - a `verbatim` quote in a non-English tongue with no `original`
             - missing/empty `original_language`
  NOTICE   informational. Surfaced for editorial attention.
             - `disputed` provenance (attribution the library itself flags)
             - English-language records that render from `original`
               (empty `english`) — a modelling inconsistency, not a defect

Exit codes:
  0  no errors (warnings/notices allowed unless --strict-warn)
  1  one or more ERRORs (only enforced under --strict)
  2  data files missing

Usage:
  ./tools/validate-quotes.py              # human-readable report
  ./tools/validate-quotes.py --strict     # exit 1 if any ERROR
  ./tools/validate-quotes.py --strict-warn # exit 1 if any ERROR or WARN
  ./tools/validate-quotes.py --json       # machine-readable output

No external dependencies. Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "site" / "data"

# The controlled provenance vocabulary. Adding a value here is a deliberate
# editorial act; an unrecognised value in the data is treated as an error so
# typos and silent drift cannot slip a mis-tagged quote past the gate.
ALLOWED_PROVENANCE = {
    "verbatim",      # exact words of the author, in the cited edition
    "liturgical",    # text of the Church's public prayer (Missal, Office)
    "traditional",   # long-attributed but without a single critical source
    "magisterial",   # official teaching document (encyclical, council)
    "disputed",      # attribution the library itself flags as contested
}

# original_language values that mean "the original IS English", so an empty
# `english` field is acceptable (the page renders from `original`).
ENGLISH_LANGS = {"", "english", "en"}


def _txt(rec: dict, key: str) -> str:
    v = rec.get(key, "")
    return v.strip() if isinstance(v, str) else ""


def check_record(rec: dict) -> dict:
    """Return {'errors': [...], 'warnings': [...], 'notices': [...]} for one record."""
    errors: list[str] = []
    warnings: list[str] = []
    notices: list[str] = []

    name = rec.get("name", f"#{rec.get('num', '?')}")
    source = _txt(rec, "source")
    provenance = _txt(rec, "provenance")
    original = _txt(rec, "original")
    english = _txt(rec, "english")
    orig_lang = _txt(rec, "original_language").lower()

    # ERROR: every quote must cite a source.
    if not source:
        errors.append("missing source citation")

    # ERROR: provenance must be a recognised value.
    if not provenance:
        errors.append("missing provenance tag")
    elif provenance not in ALLOWED_PROVENANCE:
        errors.append(f"unknown provenance '{provenance}' (allowed: {', '.join(sorted(ALLOWED_PROVENANCE))})")

    # ERROR: must render *something*.
    if not english and not original:
        errors.append("unrenderable: neither english nor original text")

    # WARN: a verbatim quote in a non-English tongue should carry the original.
    is_english_origin = orig_lang in ENGLISH_LANGS
    if provenance == "verbatim" and not is_english_origin and not original:
        warnings.append(f"verbatim {orig_lang or '?'} quote has no original-language text")

    # WARN: original_language should be labelled.
    if not orig_lang:
        warnings.append("missing original_language")

    # NOTICE: disputed attribution.
    if provenance == "disputed":
        notices.append("disputed attribution (editorial review)")

    # NOTICE: English-language record rendering from `original` (empty english).
    if is_english_origin and original and not english:
        notices.append("english-language record renders from `original` (empty `english`)")

    return {"name": name, "errors": errors, "warnings": warnings, "notices": notices}


def build_report(anthology: dict) -> dict:
    saints = anthology.get("saints", [])
    per_record = [check_record(r) for r in saints]

    errors = [(r["name"], m) for r in per_record for m in r["errors"]]
    warnings = [(r["name"], m) for r in per_record for m in r["warnings"]]
    notices = [(r["name"], m) for r in per_record for m in r["notices"]]

    return {
        "record_count": len(saints),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "notice_count": len(notices),
        "errors": errors,
        "warnings": warnings,
        "notices": notices,
    }


def render_human(report: dict) -> str:
    out: list[str] = []
    out.append("")
    out.append("  Mediatrix quote integrity gate")
    out.append("  " + "-" * 50)
    out.append(f"  anthology records:   {report['record_count']}")
    out.append(f"  errors:              {report['error_count']}")
    out.append(f"  warnings:            {report['warning_count']}")
    out.append(f"  notices:             {report['notice_count']}")
    out.append("")

    def _section(label: str, rows: list) -> None:
        if not rows:
            return
        out.append(f"  {label}:")
        for name, msg in rows:
            out.append(f"    - {name}: {msg}")
        out.append("")

    _section("ERRORS (block --strict)", report["errors"])
    _section("WARNINGS (fidelity backlog)", report["warnings"])
    _section("NOTICES", report["notices"])

    if report["error_count"] == 0:
        out.append("  integrity: PASS (no errors)")
    else:
        out.append(f"  integrity: FAIL ({report['error_count']} error(s))")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--strict", action="store_true", help="exit 1 if any ERROR")
    ap.add_argument(
        "--strict-warn",
        action="store_true",
        help="exit 1 if any ERROR or WARNING (use once the backlog is cleared)",
    )
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    path = DATA / "anthology.json"
    if not path.exists():
        print("  anthology.json missing. Run `make build-data` first.", file=sys.stderr)
        return 2

    anthology = json.loads(path.read_text(encoding="utf-8"))
    report = build_report(anthology)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_human(report))

    if (args.strict or args.strict_warn) and report["error_count"]:
        return 1
    if args.strict_warn and report["warning_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
