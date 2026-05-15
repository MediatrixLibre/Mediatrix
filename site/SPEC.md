# Mediatrix — Build Spec

_An editorial Marian study library. Fifteen pages derived from a thirteen-file markdown corpus (`$MARIOLOGY_CORPUS/`). Editorial Catholic register, Marian palette._

> **How to use this file:** before each work loop, read §6 Acceptance, then diff it against the tree. The Tier lists in §3 are ordered. Ship the topmost unmet item first.

---

## 1. Inventory

### 1.1 Shared machinery (do not fork)

| File | Contract |
|---|---|
| `site/styles/mediatrix.css` | Token table (Marian blue, ND gold, rose, vestment washes, vigil mode). Cinzel / Source Serif 4 / Source Sans 3 / JetBrains Mono. Rhythm scale. Masthead, colophon, hero, section grid, saint-card, mystery, title-card, apparition components. **Every page links this.** |
| `site/styles/fonts.css` | 27 self-hosted woff2 with unicode-range subset rules. No Google CDN. |
| `site/scripts/mediatrix.js` | Day/Vigil mode with cross-tab sync. Recents + resume via `pushRecent({slug,title,subtitle,vestment,scrollRatio})` — `slug` required. **Every page loads this before any page script.** |
| `site/favicon.svg` | Stella Maris (8-pointed Marian star) in gold. The only symbolic glyph the library admits. |

### 1.2 Pages

| Page | Source | Vestment | State |
|---|---|---|---|
| `index.html` | (none — hero) | blue | ⛔ pending |
| `library.html` | `Mediatrix-Coredemptrix-Library.md` | blue | ⛔ pending |
| `ot-types.html` | `OT-Types-of-Our-Lady-Exegesis.md` | blue | ⛔ pending |
| `nt-texts.html` | `NT-Load-Bearing-Texts.md` | blue | ⛔ pending |
| `anthology.html` | `Marian-Concise-Anthology.md` | blue | ⛔ pending |
| `rosary.html` | `Rosary-Companion.md` | white | ⛔ pending |
| `defense.html` | `Protestant-Objections-Defense.md` | red | ⛔ pending |
| `feasts.html` | `Marian-Feasts-Liturgical-Calendar.md` | blue | ⛔ pending |
| `apparitions.html` | `Marian-Apparitions-Reference.md` | blue | ⛔ pending |
| `litany.html` | `Litany-of-Loreto-Annotated.md` | blue | ⛔ pending |
| `office.html` | `Marian-Office-of-Readings-Sourcebook.md` | blue | ⛔ pending |
| `akathist.html` | `Akathist-Hymn-Translated-Annotated.md` | blue | ⛔ pending |
| `iconography.html` | `Marian-Iconography-Reference.md` | blue | ⛔ pending |
| `search.html` | (client-side) | blue | ⛔ pending |
| `about.html` | (methodology) | blue | ⛔ pending |

---

## 2. Source-of-truth contract

The thirteen markdown files at `$MARIOLOGY_CORPUS/` are canonical. The site never edits them. Per-page HTML is hand-designed; content is transcribed with editorial restraint (no padding, no invented stats). The provenance flag in each source entry (VERBATIM / TRADITIONAL / DISPUTED / LITURGICAL / MAGISTERIAL) is preserved via `.prov` badges in the page.

## 2.1 Data layer

A Python pipeline at `tools/build-mediatrix.py` parses the same 13 markdown files into normalised JSON at `site/data/*.json` (14 files: one per source plus `search-index.json`). Each JSON carries `schema_version`, `source_file`, `source_mtime`, and `generated_at` for provenance tracking, and the structured records (`saints[]`, `titles[]`, `types[]`, `mysteries[]`, etc.) extracted from the markdown.

Pages do **not** depend on the JSON at runtime — they are hand-designed against the markdown directly. The JSON exists for:
- regeneration when the canonical markdown updates (`make build-data`)
- cross-page validation
- search-index rebuild (`site/data/search-index.json` has 218 indexed entries across saints, titles, types, mysteries, feasts, apparitions, objections, NT passages, and akathist stanzas)
- future template-driven hydration if a v2 wants it

The pipeline is pure: same markdown in → same JSON out. Python stdlib only, no external deps. See `tools/README.md` for full architecture.

---

## 3. Work remaining — priority order

### Tier A — Invariants every page must satisfy

- **A1.** Every `<body>` has `data-vestment` (default `blue`) and `data-screen-label`.
- **A2.** Masthead grammar: `<a class="mast__back">`, `<a class="mast__word">Mediatrix<em>A Marian study library</em></a>`, `<div class="mast__tools">` with `#mode-toggle` + exactly two topic-appropriate cross-links.
- **A3.** Colophon grammar: page-specific small-caps count on the left, full nav list on the right, *Sub tuum praesidium* in `.colophon__sub` on every page.
- **A4.** `<main id="main">` on every page; skip-link in `<body>` first child.
- **A5.** `Mediatrix.pushRecent({slug, title, subtitle, vestment, scrollRatio: 0})` fires on load. `index.html` does not push itself.
- **A6.** Tokens only — no raw hex outside `:root`. Grep before commit.
- **A7.** No `href="#"` in primary nav. Pending material renders as `<span class="pending">`.
- **A8.** Every `<script>` block opens and closes; `grep "^document\." site/*.html` is empty.
- **A9.** Greek / Hebrew / Latin renders as `<em>` inside `.greek`/`.hebrew`/`.latin` spans, Source Serif italic, never transliterated.
- **A10.** Provenance flagged via `.prov verbatim|traditional|disputed|liturgical|magisterial`.

### Tier B — Content fidelity

- **B1.** Every quotation traces to a critical edition (PG / PL / SC / CSEL / CCSL / Leonine / Quaracchi / AAS). Where the source markdown says "DISPUTED", the page says DISPUTED — never silently elevated.
- **B2.** Hebrew numerals where the OT-types page uses them; Greek for NT and Akathist; Latin for Litany and Office.
- **B3.** Inline scripture refs link to `nt-texts.html#<anchor>` for the three load-bearing texts; everything else is plain `cite`.

### Tier C — Considered-and-declining

- No build step inside `site/`. Hand-set HTML, full stop.
- No framework, no transpiler, no bundler.
- No external fetches; fonts and data are local.
- No login, no analytics, no share buttons.
- No audio, no decorative imagery, no AI-generated illustration.
- No saint detail pages; the anthology is the index, no further drill-down.
- No per-mystery detail page; the rosary is one scroll.

---

## 4. Acceptance

A loop is complete when **every one** of these is demonstrably true:

1. Every link from `index.html` lands on a working page; no `href="#"` in primary nav.
2. `Mediatrix.pushRecent({slug,…})` fires on every content page; after visiting three distinct pages the index Recently-read strip shows all three with correct vestment and subtitle.
3. Vigil toggle on any page persists across all pages and across reloads.
4. Every `<body>` has `data-vestment` and `data-screen-label`.
5. `grep -n "^document\." site/*.html` is empty.
6. `python3 -m http.server -d site 8000` → every page loads clean in Chrome/Safari with zero console errors.
7. *Sub tuum praesidium* appears in the colophon on every page.
8. Stella Maris (favicon.svg + `.stella-rule` on the index) is the only ornament.
