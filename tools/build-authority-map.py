#!/usr/bin/env python3
"""
build-authority-map.py — propose Wikidata + VIAF authority links for anthology authors.

Phase 2 of the quote-fidelity programme. For each record in anthology.json
this queries the Wikidata API, scores candidate entities against the record's
own dates and type, and writes a PROPOSED mapping to tools/authority-map.json.

It deliberately does not emit anything into the site. Authority links in a
source-fidelity library must be human-verified before they go live (the
"Cyril of Jerusalem vs Cyril of Alexandria" problem is decided by dates, not
by surname). This tool's job is to do the legwork and surface the signals a
reviewer needs: candidate QID, label, description, Wikidata birth/death years
vs the anthology's dates, VIAF id (from claim P214), and a confidence band.

VIAF is read from each entity's Wikidata P214 claim, so no separate VIAF API
call is needed.

Output record per author:
  {
    "name": "<anthology name>",
    "qid": "Q…" | null,
    "viaf": "…" | null,
    "wd_label": "...", "wd_description": "...",
    "wd_birth": 354, "wd_death": 430,
    "anthology_dates": "354 - 430",
    "is_human": true, "is_work": false,
    "confidence": "high" | "medium" | "low" | "none",
    "reasons": [...],
    "alternatives": [ {qid,label,description,birth,death}, ... ]
  }

Usage:
  ./tools/build-authority-map.py                 # query + write proposal
  ./tools/build-authority-map.py --limit 5       # first 5 records (smoke test)
  ./tools/build-authority-map.py --print         # also print a summary table

Python 3.9+, stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANTHOLOGY = REPO / "site" / "data" / "anthology.json"
OUT = REPO / "tools" / "authority-map.json"

API = "https://www.wikidata.org/w/api.php"
UA = "Mediatrix-authority-linker/1.0 (https://stella-maris.pages.dev)"

HUMAN_QID = "Q5"
# Wikidata items that mark a record as a textual work rather than a person.
WORK_TYPES = {
    "Q47461344",  # written work
    "Q7725634",   # literary work
    "Q1980247",   # chapter
    "Q2135540",   # legal/official document-ish
    "Q1238720",   # papal encyclical
    "Q49848",     # document
    "Q207628",    # musical composition
    "Q35160",     # hymn (approx)
}

HONORIFIC_RE = re.compile(
    r"^(St\.|Sts\.|Bl\.|Ven\.|Pope St\.|Pope Bl\.|Pope|Blessed|Saint)\s+", re.IGNORECASE
)


def clean_name(name: str) -> str:
    """Derive a Wikidata search string from an anthology name."""
    n = name
    # Drop trailing editorial annotations: "— Greek, late 3rd century", "§62", "(Padre)".
    n = re.split(r"\s+[—-]\s+", n)[0]          # cut at em/en dash clause
    n = re.sub(r"§\s*\d+", "", n)               # section marks
    n = re.sub(r"\(([^)]*)\)", r"\1", n)        # unwrap parentheticals: (Padre) -> Padre
    n = HONORIFIC_RE.sub("", n).strip()
    # "Second Vatican Council, Lumen Gentium" -> "Lumen Gentium" (the work)
    if "," in n and "Lumen Gentium" in n:
        n = "Lumen Gentium"
    return n.strip()


def extract_years(dates: str) -> list[int]:
    """Pull plausible 3-4 digit years out of an anthology dates string."""
    if not dates:
        return []
    s = dates.replace("–", "-").replace("—", "-")
    return [int(y) for y in re.findall(r"\b(\d{3,4})\b", s)]


def api_get(params: dict) -> dict:
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def search_entities(query: str, limit: int = 8) -> list[str]:
    data = api_get(
        {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": limit,
        }
    )
    return [hit["id"] for hit in data.get("search", [])]


def base_name(clean: str) -> str:
    """'Irenaeus of Lyons' -> 'Irenaeus'; 'Albert the Great' -> 'Albert'.

    The actual person's Wikidata label is frequently the short form, while the
    long form matches articles/books *about* them. Searching both forms and
    merging the candidate pools lets the date+type scorer pick the real entity.
    """
    parts = clean.split()
    for i, p in enumerate(parts):
        if p.lower() in {"of", "the"} and i > 0:
            return " ".join(parts[:i])
    return clean


def candidate_qids(name: str) -> list[str]:
    full = clean_name(name)
    qids = search_entities(full, limit=8)
    base = base_name(full)
    if base and base.lower() != full.lower():
        for q in search_entities(base, limit=6):
            if q not in qids:
                qids.append(q)
    return qids


def get_entities(qids: list[str]) -> dict:
    """Batch wbgetentities (<=50 per call). Returns {qid: claims/labels dict}."""
    out: dict[str, dict] = {}
    for i in range(0, len(qids), 45):
        chunk = qids[i : i + 45]
        data = api_get(
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "labels|descriptions|claims",
                "languages": "en",
            }
        )
        out.update(data.get("entities", {}))
        time.sleep(0.1)
    return out


def _claim_year(entity: dict, prop: str) -> int | None:
    try:
        claims = entity["claims"][prop]
        for c in claims:
            ts = c["mainsnak"]["datavalue"]["value"]["time"]  # e.g. "+0354-00-00T..."
            m = re.search(r"([+-]\d{1,})-", ts)
            if m:
                return int(m.group(1))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _claim_values(entity: dict, prop: str) -> list[str]:
    out = []
    try:
        for c in entity["claims"][prop]:
            v = c["mainsnak"]["datavalue"]["value"]
            if isinstance(v, dict) and "id" in v:
                out.append(v["id"])
            elif isinstance(v, str):
                out.append(v)
    except (KeyError, TypeError):
        pass
    return out


def _label(entity: dict) -> str:
    return entity.get("labels", {}).get("en", {}).get("value", "")


def _desc(entity: dict) -> str:
    return entity.get("descriptions", {}).get("en", {}).get("value", "")


# Description keywords. wbsearchentities frequently returns scholarship ABOUT
# a Father (articles, books) ranked above the Father himself; these let the
# scorer push such items below the real person/work.
WRONG_DESC = (
    "scientific article", "article published", "book about", "journal",
    "research paper", "encyclopedia", "thesis", "dissertation", "building",
    "church in", "village", "commune", "river", "film", "album", "painting",
    "sculpture", "parish", "diocese", "basilica",
)
PERSON_DESC = (
    "saint", "bishop", "archbishop", "theologian", "pope", "priest", "monk",
    "abbot", "cardinal", "mystic", "friar", "martyr", "nun", "religious",
    "philosopher", "doctor of the church", "father of the church", "deacon",
    "hermit", "preacher", "apologist", "patriarch", "founder",
)
WORK_DESC = (
    "hymn", "prayer", "encyclical", "constitution", "dogmatic", "document",
    "apostolic", "treatise", "liturg", "text", "creed", "council",
)


def is_work_entity(entity: dict, desc: str) -> bool:
    if set(_claim_values(entity, "P31")) & WORK_TYPES:
        return True
    return any(w in desc for w in WORK_DESC)


def score(record_years: list[int], expect_work: bool, entity: dict) -> tuple[int, list[str]]:
    """Return (score, reasons). Higher is better."""
    reasons: list[str] = []
    s = 0
    instance_of = _claim_values(entity, "P31")
    desc = _desc(entity).lower()
    is_human = HUMAN_QID in instance_of
    is_work = is_work_entity(entity, desc)

    # Wrong-type description (article/book/place) — strong penalty, applied first.
    if any(w in desc for w in WRONG_DESC):
        s -= 40; reasons.append(f"wrong type by description: '{desc[:44]}'")

    # Type alignment
    if expect_work:
        if is_work:
            s += 45; reasons.append("is a work (type/description)")
        elif is_human:
            s -= 20; reasons.append("expected a work but candidate is a person")
    else:
        if is_human:
            s += 30; reasons.append("is a human")
        else:
            s -= 18; reasons.append("not marked as human")
        if any(w in desc for w in PERSON_DESC):
            s += 14; reasons.append("description matches a religious figure")

    # Date alignment (persons)
    if record_years and not expect_work:
        b = _claim_year(entity, "P569")
        d = _claim_year(entity, "P570")
        wd_years = [y for y in (b, d) if y is not None]
        if wd_years:
            best = min(abs(ry - wy) for ry in record_years for wy in wd_years)
            if best <= 3:
                s += 50; reasons.append(f"dates match within {best}y")
            elif best <= 20:
                s += 32; reasons.append(f"dates match within {best}y (circa tolerance)")
            elif best <= 60:
                s += 5; reasons.append(f"dates loosely match ({best}y off)")
            else:
                s -= 30; reasons.append(f"dates conflict ({best}y off)")
        else:
            reasons.append("candidate has no birth/death dates")

    # Has a VIAF id (a sign it's an authority-grade person/work)
    if _claim_values(entity, "P214"):
        s += 8; reasons.append("has VIAF id")

    return s, reasons


def confidence_band(best_score: int, margin: int) -> str:
    if best_score >= 70 and margin >= 20:
        return "high"
    if best_score >= 45:
        return "medium"
    if best_score > 0:
        return "low"
    return "none"


def first_viaf(entity: dict) -> str | None:
    v = _claim_values(entity, "P214")
    return v[0] if v else None


def resolve_record(rec: dict, entity_cache: dict) -> dict:
    name = rec["name"]
    query = clean_name(name)
    years = extract_years(rec.get("dates", ""))
    # A record is "work-like" if it has no clean personal date range or its name is a known work.
    expect_work = (
        len(years) < 2
        and any(k in name for k in ("Praesidium", "Akathist", "Lumen Gentium", "Hymn"))
    )

    cand_qids = search_entities(query)
    scored = []
    for qid in cand_qids:
        ent = entity_cache.get(qid)
        if not ent:
            continue
        sc, reasons = score(years, expect_work, ent)
        scored.append((sc, qid, ent, reasons))
    scored.sort(key=lambda t: t[0], reverse=True)

    if not scored:
        return {
            "name": name, "query": query, "qid": None, "viaf": None,
            "confidence": "none", "reasons": ["no Wikidata candidates"],
            "anthology_dates": rec.get("dates", ""), "alternatives": [],
        }

    best_score, best_qid, best_ent, best_reasons = scored[0]
    margin = best_score - (scored[1][0] if len(scored) > 1 else 0)
    instance_of = _claim_values(best_ent, "P31")

    return {
        "name": name,
        "query": query,
        "qid": best_qid,
        "viaf": first_viaf(best_ent),
        "wd_label": _label(best_ent),
        "wd_description": _desc(best_ent),
        "wd_birth": _claim_year(best_ent, "P569"),
        "wd_death": _claim_year(best_ent, "P570"),
        "anthology_dates": rec.get("dates", ""),
        "is_human": HUMAN_QID in instance_of,
        "is_work": bool(set(instance_of) & WORK_TYPES),
        "score": best_score,
        "margin": margin,
        "confidence": confidence_band(best_score, margin),
        "reasons": best_reasons,
        "alternatives": [
            {
                "qid": q,
                "label": _label(e),
                "description": _desc(e),
                "birth": _claim_year(e, "P569"),
                "death": _claim_year(e, "P570"),
                "score": sc,
            }
            for sc, q, e, _ in scored[1:4]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only process first N records")
    ap.add_argument("--print", action="store_true", dest="do_print", help="print summary table")
    args = ap.parse_args()

    anthology = json.loads(ANTHOLOGY.read_text(encoding="utf-8"))
    saints = anthology["saints"]
    if args.limit:
        saints = saints[: args.limit]

    # Pass 1: search every record, collect candidate QIDs.
    print(f"  searching Wikidata for {len(saints)} records…", file=sys.stderr)
    per_record_candidates: dict[int, list[str]] = {}
    all_qids: set[str] = set()
    for rec in saints:
        try:
            qids = candidate_qids(rec["name"])
        except Exception as e:  # network hiccup on one record shouldn't kill the run
            print(f"    ! search failed for {rec['name']}: {e}", file=sys.stderr)
            qids = []
        per_record_candidates[rec["num"]] = qids
        all_qids.update(qids)
        time.sleep(0.12)

    # Pass 2: batch-fetch all candidate entities once.
    print(f"  fetching {len(all_qids)} candidate entities…", file=sys.stderr)
    entity_cache = get_entities(sorted(all_qids)) if all_qids else {}

    # Pass 3: score using the cache (re-uses per-record candidate order).
    results = []
    for rec in saints:
        # rebuild scored list from cached entities + this record's candidates
        years = extract_years(rec.get("dates", ""))
        name = rec["name"]
        expect_work = (
            len(years) < 2
            and any(k in name for k in ("Praesidium", "Akathist", "Lumen Gentium", "Hymn"))
        )
        scored = []
        for qid in per_record_candidates.get(rec["num"], []):
            ent = entity_cache.get(qid)
            if not ent:
                continue
            sc, reasons = score(years, expect_work, ent)
            scored.append((sc, qid, ent, reasons))
        scored.sort(key=lambda t: t[0], reverse=True)
        if not scored:
            results.append({
                "num": rec["num"], "name": name, "query": clean_name(name),
                "qid": None, "viaf": None, "confidence": "none",
                "reasons": ["no Wikidata candidates"], "anthology_dates": rec.get("dates", ""),
                "alternatives": [],
            })
            continue
        bs, bq, be, br = scored[0]
        margin = bs - (scored[1][0] if len(scored) > 1 else 0)
        io = _claim_values(be, "P31")
        results.append({
            "num": rec["num"], "name": name, "query": clean_name(name),
            "qid": bq, "viaf": first_viaf(be),
            "wd_label": _label(be), "wd_description": _desc(be),
            "wd_birth": _claim_year(be, "P569"), "wd_death": _claim_year(be, "P570"),
            "anthology_dates": rec.get("dates", ""),
            "is_human": HUMAN_QID in io, "is_work": bool(set(io) & WORK_TYPES),
            "score": bs, "margin": margin,
            "confidence": confidence_band(bs, margin), "reasons": br,
            "alternatives": [
                {"qid": q, "label": _label(e), "description": _desc(e),
                 "birth": _claim_year(e, "P569"), "death": _claim_year(e, "P570"), "score": sc}
                for sc, q, e, _ in scored[1:4]
            ],
        })

    bands = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for r in results:
        bands[r["confidence"]] += 1

    payload = {
        "generated_by": "tools/build-authority-map.py",
        "source": "wikidata + viaf(P214)",
        "record_count": len(results),
        "confidence_summary": bands,
        "verified": False,
        "authorities": results,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(REPO)} ({len(results)} records)", file=sys.stderr)
    print(f"  confidence: {bands}", file=sys.stderr)

    if args.do_print:
        print()
        for r in results:
            qid = r["qid"] or "-"
            print(f"  [{r['confidence']:>6}] {r['name']:<34} {qid:<11} {r.get('wd_label','')[:28]:<28} {r.get('wd_description','')[:34]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
