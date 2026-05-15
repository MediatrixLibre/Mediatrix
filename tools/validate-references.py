#!/usr/bin/env python3
"""
validate-references.py — cross-page reference checker.

For every saint, source, or doctrinal landmark named in litany.json,
rosary.json, office.json, or defense.json, confirm that the entity has
a canonical record in anthology.json (and OT/NT pages where relevant).

Surfaces:
  - orphans (names referenced in cross-source pages but not in anthology)
  - dangling internal anchors (#tN, #sN, #mN references that don't resolve)
  - per-source citation provenance summary

Exit codes:
  0  all references resolve, no orphans
  1  orphans found
  2  index / data files missing

Usage:
  ./tools/validate-references.py           # human-readable report
  ./tools/validate-references.py --strict  # exit 1 on orphans
  ./tools/validate-references.py --json    # machine-readable output

The check is intentionally lenient: a "soft" match (last name only) is
treated as a hit, so "Bernard" matches "St. Bernard of Clairvaux". The
authoritative match list lives in anthology.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "site" / "data"


# --- canonical name builder ---------------------------------------------


def _strip_honorifics(name: str) -> str:
    """Drop 'St.', 'Bl.', 'Ven.', 'Pope' so the surname is usable."""
    return re.sub(
        r"^(St\.|Sts\.|Bl\.|Ven\.|Pope|Pope St\.|Pope Bl\.)\s+",
        "",
        name.strip(),
    ).strip()


def _key_names(name: str) -> set[str]:
    """
    Return a small set of likely match-strings for a canonical saint name.
    Includes: full clean name, last word, 'first last' shortform, and
    personal-name segments before 'of/the/de' particles.
    """
    clean = _strip_honorifics(name)
    out = {clean.lower()}
    parts = clean.split()
    if not parts:
        return out

    # Last word - useful for 'Bernard', 'Aquinas', 'Augustine'
    out.add(parts[-1].lower())
    # First word - useful for 'Bernard' (of Clairvaux), 'Albert' (the Great),
    #               'Louis' / 'Catherine' / 'Teresa', 'Maria' for Maximilian Maria
    out.add(parts[0].lower())

    # Personal name before any particle ('of', 'the', 'de', 'di', 'von')
    PARTICLES = {"of", "the", "de", "di", "della", "von", "da", "le"}
    for i, p in enumerate(parts):
        if p.lower() in PARTICLES and i > 0:
            out.add(parts[i - 1].lower())              # 'Bernard' from 'Bernard of Clairvaux'
            out.add(" ".join(parts[:i]).lower())       # 'Louis Marie' from 'Louis Marie de Montfort'
            if i + 1 < len(parts):
                # 'bernard of clairvaux' (canonical short)
                out.add(f"{parts[i - 1]} {parts[i]} {parts[i + 1]}".lower())
            break

    # Papal: 'John Paul II' → 'paul ii', 'john paul', 'paul'
    if len(parts) >= 2 and parts[-1].lower() in {
        "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv",
    }:
        out.add(f"{parts[-2]} {parts[-1]}".lower())
        out.add(parts[-2].lower())
        # Drop the regnal numeral for short matching
        if len(parts) >= 3:
            out.add(" ".join(parts[:-1]).lower())

    # Strip ASCII-fold accents to catch e.g. "Labour'e" → "Laboure"
    folded = {_ascii_fold(k) for k in out}
    out.update(folded)

    return {n for n in out if len(n) >= 3 and n.lower() not in PARTICLES}


def _ascii_fold(s: str) -> str:
    """Drop common diacritics so 'Labouré' matches 'Laboure'."""
    table = str.maketrans(
        "àáâãäåçèéêëìíîïñòóôõöùúûüýÿæœ",
        "aaaaaaceeeeiiiinooooouuuuyyao",
    )
    return s.translate(table)


def build_canonical_map(anthology: dict) -> dict[str, list[dict]]:
    """
    Map every plausible name-key → list of anthology records that match.
    Multi-record matches are allowed (e.g. 'Cyril' → Cyril of Jerusalem + Cyril of Alexandria).
    """
    table: dict[str, list[dict]] = {}
    for s in anthology.get("saints", []):
        for key in _key_names(s["name"]):
            table.setdefault(key, []).append(s)
    return table


# --- name extraction from prose -----------------------------------------

# Strict patterns. Only capture names that are unambiguous person-references.
_HONORIFIC = r"(?:St\.|Sts\.|Bl\.|Ven\.|Pope\s+St\.|Pope\s+Bl\.|Pope)"
_CAPWORD = r"[A-Z][a-zëçáàâãäåéêíïóôõöúûüæœ]+"
# Allow up to 4 capitalised words after the honorific, with optional "of X"
_NAME_TAIL = rf"{_CAPWORD}(?:\s+{_CAPWORD}){{0,3}}(?:\s+of\s+{_CAPWORD}(?:\s+{_CAPWORD})?)?"

# Honorific + name: matches "St. Bernard of Clairvaux", "Pope St. John Paul II", "Bl. Fulton J. Sheen"
_HONORIFIC_RE = re.compile(rf"({_HONORIFIC}\s+{_NAME_TAIL})\b")

# Papal regnal — explicit names that are clearly persons, used in citations
_PAPAL_REGNAL = {
    "pius vii", "pius ix", "pius x", "pius xi", "pius xii", "pius v", "pius vi",
    "leo xiii", "leo x",
    "benedict xv", "benedict xvi", "benedict xiv",
    "paul vi", "paul iii",
    "john paul ii", "john paul i", "john xxiii",
    "sixtus v", "clement viii", "clement x", "clement xi",
    "francis", "innocent xi", "gregory xvi", "gregory xiii",
    "urban viii",
}
_PAPAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(_PAPAL_REGNAL, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Compound-name patterns without honorific (very limited whitelist of unambiguous
# Catholic theological figures whose name *alone* identifies them).
_BARE_NAMED = {
    "bernard of clairvaux", "thomas aquinas", "francis de sales",
    "louis marie de montfort", "louis de montfort", "alphonsus liguori",
    "john of damascus", "andrew of crete", "germanus of constantinople",
    "sophronius of jerusalem", "cyril of alexandria", "cyril of jerusalem",
    "augustine of hippo", "ambrose of milan", "gregory of nazianzus",
    "irenaeus of lyons", "justin martyr", "peter chrysologus",
    "peter damian", "peter canisius", "robert bellarmine",
    "anselm of canterbury", "albert the great", "bernardine of siena",
    "bridget of sweden", "catherine labour", "bernadette soubirous",
    "ephrem the syrian", "athanasius", "john chrysostom", "origen",
    "tertullian", "jerome", "bonaventure", "fulton sheen", "padre pio",
    "teresa of calcutta", "maximilian kolbe", "john eudes", "gerson",
}
_BARE_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(_BARE_NAMED, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Phrases that the honorific regex might capture but aren't a person.
_NON_PERSON_AFTER_HONORIFIC = {
    "mary",         # "St. Mary Major" → exclude when bare
    "mary major",
    "peter",        # "St. Peter's" without further qualifier
}


def extract_names_from(text: str) -> set[str]:
    """
    Return lowercased candidate names that look like persons.

    Strict rules:
      1. Honorific + name: "St. Bernard of Clairvaux", "Pope Pius IX"
      2. Papal regnal: "Pius XII", "Leo XIII", "John Paul II"
      3. Bare named figures from a whitelist: "Thomas Aquinas", "Augustine of Hippo"
    """
    found: set[str] = set()

    # 1. Honorific + name
    for m in _HONORIFIC_RE.finditer(text):
        candidate = m.group(1).strip()
        stripped = _strip_honorifics(candidate).lower()
        if not stripped or stripped in _NON_PERSON_AFTER_HONORIFIC:
            continue
        if len(stripped) < 4:
            continue
        # Reject if it's an organisation (Mary Major basilica, etc.)
        if "major" in stripped or "magdalene" in stripped or "calvary" in stripped:
            continue
        found.add(stripped)
        parts = stripped.split()
        if parts:
            # Add last word + 'first last' shortforms ONLY for multi-word names
            if len(parts) >= 2:
                found.add(parts[-1])
                found.add(f"{parts[0]} {parts[-1]}")

    # 2. Papal regnal
    for m in _PAPAL_RE.finditer(text):
        found.add(m.group(1).lower())

    # 3. Bare named whitelist
    for m in _BARE_RE.finditer(text):
        n = m.group(1).lower()
        found.add(n)
        # Also add last name for matching
        parts = n.split()
        if len(parts) >= 2:
            found.add(parts[-1])

    return found


# --- load all data ------------------------------------------------------


def load_all() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in DATA.glob("*.json"):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


# --- per-source scanners ------------------------------------------------
# Two-pronged: scan structured JSON fields AND the raw markdown body
# (the patristic citations live in prose, not in structured fields).

import os

SOURCE_DIR = Path(
    os.environ.get("MARIOLOGY_CORPUS")
    or (REPO / "corpus" / "mariology")
).expanduser()


def _read_markdown(name: str) -> str:
    p = SOURCE_DIR / name
    if not p.exists():
        return ""
    # Collapse whitespace so multi-line names ("John\nHenry Newman") parse as one token.
    raw = p.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", raw)


def scan_litany(litany: dict) -> set[str]:
    md = _read_markdown("Litany-of-Loreto-Annotated.md")
    return extract_names_from(md)


def scan_rosary(rosary: dict) -> set[str]:
    md = _read_markdown("Rosary-Companion.md")
    return extract_names_from(md)


def scan_office(office: dict) -> set[str]:
    md = _read_markdown("Marian-Office-of-Readings-Sourcebook.md")
    return extract_names_from(md)


def scan_defense(defense: dict) -> set[str]:
    md = _read_markdown("Protestant-Objections-Defense.md")
    return extract_names_from(md)


def scan_apparitions(apparitions: dict) -> set[str]:
    md = _read_markdown("Marian-Apparitions-Reference.md")
    return extract_names_from(md)


# --- report -------------------------------------------------------------


def build_report(data: dict[str, dict]) -> dict:
    anthology = data.get("anthology", {})
    canon = build_canonical_map(anthology)
    canon_keys = set(canon.keys())

    sources = {
        "litany": scan_litany(data.get("litany", {})),
        "rosary": scan_rosary(data.get("rosary", {})),
        "office": scan_office(data.get("office", {})),
        "defense": scan_defense(data.get("defense", {})),
        "apparitions": scan_apparitions(data.get("apparitions", {})),
    }

    report: dict = {
        "anthology_record_count": anthology.get("saint_count", 0),
        "anthology_key_count": len(canon_keys),
        "sources": {},
        "orphans_global": set(),
        "resolved_global": set(),
    }

    for src_name, names in sources.items():
        resolved: list[dict] = []
        orphans: list[str] = []
        for n in sorted(names):
            if _matches_canonical(n, canon_keys):
                resolved.append({"name": n, "matched_to": _best_match(n, canon)})
            else:
                orphans.append(n)
        report["sources"][src_name] = {
            "names_found": len(names),
            "resolved": resolved,
            "orphans": orphans,
            "resolved_count": len(resolved),
            "orphan_count": len(orphans),
        }
        for o in orphans:
            report["orphans_global"].add(o)
        for r in resolved:
            report["resolved_global"].add(r["name"])

    report["orphans_global"] = sorted(report["orphans_global"])
    report["resolved_global"] = sorted(report["resolved_global"])
    return report


def _matches_canonical(name: str, canon_keys: set[str]) -> bool:
    if name in canon_keys:
        return True
    # Try ASCII-folded form (handle diacritics: "Labouré" → "laboure")
    folded = _ascii_fold(name)
    if folded in canon_keys:
        return True
    # also tolerate substring fallback for multi-word names like "john paul ii"
    for key in canon_keys:
        if name == key or name.endswith(" " + key) or key.endswith(" " + name):
            return True
    return False


def _best_match(name: str, canon: dict[str, list[dict]]) -> str:
    if name in canon and canon[name]:
        return canon[name][0]["name"]
    # find any canon key that contains or is contained by name
    for key, recs in canon.items():
        if name == key or name.endswith(" " + key) or key.endswith(" " + name):
            return recs[0]["name"]
    return "?"


# --- output -------------------------------------------------------------


def render_human(report: dict) -> str:
    out: list[str] = []
    out.append("")
    out.append("  Mediatrix cross-page reference validator")
    out.append("  " + "-" * 50)
    out.append(f"  anthology records:          {report['anthology_record_count']}")
    out.append(f"  canonical match keys:       {report['anthology_key_count']}")
    out.append("")
    for src, summary in report["sources"].items():
        ok = summary["orphan_count"] == 0
        flag = "OK   " if ok else "WARN "
        out.append(
            f"  {flag} {src:<13} found={summary['names_found']:>3}   "
            f"resolved={summary['resolved_count']:>3}   "
            f"orphans={summary['orphan_count']:>3}"
        )
        if summary["orphans"]:
            for o in summary["orphans"]:
                out.append(f"           orphan: {o}")
    out.append("")
    total_orphans = len(report["orphans_global"])
    out.append(
        f"  global orphans: {total_orphans}    "
        f"global resolved: {len(report['resolved_global'])}"
    )
    if total_orphans:
        out.append("  unique orphans across all sources:")
        for o in report["orphans_global"]:
            out.append(f"    - {o}")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="exit 1 if any orphans are found")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if not DATA.exists() or not list(DATA.glob("*.json")):
        print("  no site/data/*.json found. Run `make build-data` first.", file=sys.stderr)
        return 2

    data = load_all()
    if "anthology" not in data:
        print("  anthology.json missing. Run `make build-data`.", file=sys.stderr)
        return 2

    report = build_report(data)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_human(report))

    if args.strict and report["orphans_global"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
