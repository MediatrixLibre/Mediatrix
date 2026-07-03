#!/usr/bin/env python3
"""
gen-ics.py — generate site/marian-feasts.ics, a subscribable calendar of
the twenty Marian feasts.

Single-sources the feast list from site/data/feasts.json (the corpus-built
data layer). The eighteen fixed feasts become yearly-recurring all-day
events; the two moveable memorials (Mother of the Church, Immaculate Heart)
are reckoned from Easter (Butcher's algorithm, Gregorian) and emitted as
one event per year across a ten-year window from BASE_YEAR.

Deterministic on purpose: DTSTAMP is pinned to the BASE_YEAR epoch and the
moveable window is anchored to BASE_YEAR, not "today", so re-runs produce
byte-identical output until the data or the window constant changes.
Regenerate (and bump BASE_YEAR) roughly once a decade, or whenever the
feast data moves.

Run: python3 tools/gen-ics.py   (or `make ics`)
Python 3.9+, stdlib only.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
FEASTS_JSON = SITE / "data" / "feasts.json"
OUT = SITE / "marian-feasts.ics"

ORIGIN = "https://stella-maris.pages.dev"
BASE_YEAR = 2026
MOVEABLE_YEARS = 10
DTSTAMP = f"{BASE_YEAR}0101T000000Z"  # pinned: deterministic output

# Liturgical rank per feast, mirroring the banner list in index.html.
RANKS = {
    "Solemnity of Mary, Mother of God": "Solemnity · Holy Day of Obligation",
    "Presentation of the Lord": "Feast · Candlemas",
    "Our Lady of Lourdes": "Optional Memorial · World Day of the Sick",
    "Annunciation of the Lord": "Solemnity",
    "Our Lady of Fátima": "Optional Memorial",
    "Our Lady, Help of Christians": "Optional Memorial",
    "Visitation of the Blessed Virgin Mary": "Feast",
    "Our Lady of Mount Carmel": "Optional Memorial",
    "Dedication of Saint Mary Major": "Optional Memorial",
    "Assumption of the Blessed Virgin Mary": "Solemnity · Holy Day · dogma 1950",
    "Queenship of the Blessed Virgin Mary": "Memorial",
    "Nativity of the Blessed Virgin Mary": "Feast",
    "Most Holy Name of Mary": "Optional Memorial",
    "Our Lady of Sorrows": "Memorial",
    "Our Lady of the Rosary": "Memorial",
    "Presentation of the Blessed Virgin Mary": "Memorial",
    "Immaculate Conception": "Solemnity · Holy Day · dogma 1854",
    "Our Lady of Guadalupe": "Feast (Americas) · Patroness of the Americas",
    "Mary, Mother of the Church": "Memorial · Monday after Pentecost",
    "Immaculate Heart of Mary": "Memorial · Saturday after the Sacred Heart",
}

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}

# Offsets from Easter Sunday for the moveable memorials.
MOVEABLE_OFFSETS = {
    "Mary, Mother of the Church": 50,   # Monday after Pentecost
    "Immaculate Heart of Mary": 69,     # Saturday after the Sacred Heart
}


def easter(year: int) -> dt.date:
    """Butcher's algorithm, Gregorian calendar."""
    a, b, c = year % 19, year // 100, year % 100
    d, e, f = b // 4, b % 4, (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def esc(text: str) -> str:
    """RFC 5545 TEXT escaping."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")


def vevent(uid: str, dtstart: str, summary: str, description: str, rrule: str = "") -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{DTSTAMP}",
        f"DTSTART;VALUE=DATE:{dtstart}",
    ]
    if rrule:
        lines.append(f"RRULE:{rrule}")
    lines += [
        f"SUMMARY:{esc(summary)}",
        f"DESCRIPTION:{esc(description)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return lines


def main() -> int:
    feasts = json.loads(FEASTS_JSON.read_text(encoding="utf-8"))
    records = feasts.get("feasts", feasts)

    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mediatrix//Marian Feasts//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Marian Feasts · Mediatrix",
        f"X-WR-CALDESC:The twenty Marian feasts of the liturgical year\\, from {ORIGIN}/feasts",
        "REFRESH-INTERVAL;VALUE=DURATION:P1W",
        "X-PUBLISHED-TTL:P1W",
    ]

    n_fixed = n_moveable = 0
    for rec in records:
        name = rec["name"]
        rank = RANKS.get(name, "")
        desc = (rank + "\n" if rank else "") + f"{ORIGIN}/feasts"
        if name in MOVEABLE_OFFSETS:
            offset = MOVEABLE_OFFSETS[name]
            for year in range(BASE_YEAR, BASE_YEAR + MOVEABLE_YEARS):
                day = easter(year) + dt.timedelta(days=offset)
                out += vevent(
                    uid=f"{slug(name)}-{year}@stella-maris.pages.dev",
                    dtstart=day.strftime("%Y%m%d"),
                    summary=name,
                    description=f"{desc}\nMoveable: {rec['date']} (Easter reckoning)",
                )
                n_moveable += 1
        else:
            month_name, day_s = rec["date"].rsplit(" ", 1)
            month, day = MONTHS[month_name], int(day_s)
            out += vevent(
                uid=f"{slug(name)}@stella-maris.pages.dev",
                dtstart=f"{BASE_YEAR}{month:02d}{day:02d}",
                summary=name,
                description=desc,
                rrule="FREQ=YEARLY",
            )
            n_fixed += 1

    out.append("END:VCALENDAR")
    OUT.write_text("\r\n".join(out) + "\r\n", encoding="utf-8")
    print(f"  wrote {OUT.relative_to(REPO)} ({n_fixed} recurring + {n_moveable} moveable events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
