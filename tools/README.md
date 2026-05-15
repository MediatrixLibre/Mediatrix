# Mediatrix data pipeline

The site at `site/*.html` is hand-designed and editorial. This `tools/`
folder is the **data pipeline** that turns the canonical thirteen-file
markdown corpus into normalised JSON at `site/data/*.json`, plus a single
`site/data/search-index.json` that the search page consumes.

The corpus location is set by the `MARIOLOGY_CORPUS` environment variable;
if unset, the pipeline falls back to `./corpus/mariology/` inside the repo.
Set the variable in your shell or in `.env.local` (see `.env.example`).

The pages do **not** require the JSON to render. The JSON is for:

1. **Regeneration** when the canonical markdown updates
2. **Cross-page validation** (verify every saint named in the litany is
   in the anthology, etc.)
3. **Search index rebuild** (one cron / one make target away)
4. **Future hydration** if a v2 wants template-driven pages

The markdown is the tree; the JSON is the catalogue of the tree.

---

## The five commands

```sh
make build-data     # regenerate every site/data/*.json from the markdown
make verify-data    # verify outputs exist + record counts
make clean-data     # rm site/data/*.json
python3 tools/build-mediatrix.py --list           # list available extractors
python3 tools/build-mediatrix.py anthology        # rebuild a single source
```

---

## What it parses

Thirteen markdown files at `$MARIOLOGY_CORPUS/`, emitting one JSON per source
plus the master search index:

| Source file | JSON | Record count |
|---|---|---:|
| `Mediatrix-Coredemptrix-Library.md` | `library.json` | 12 eras |
| `OT-Types-of-Our-Lady-Exegesis.md` | `ot-types.json` | 26 types |
| `NT-Load-Bearing-Texts.md` | `nt-texts.json` | 3 passages + 2 syntheses |
| `Marian-Concise-Anthology.md` | `anthology.json` | 49 saints |
| `Rosary-Companion.md` | `rosary.json` | 20 mysteries |
| `Protestant-Objections-Defense.md` | `defense.json` | 12 objections |
| `Marian-Feasts-Liturgical-Calendar.md` | `feasts.json` | 20 feasts |
| `Marian-Apparitions-Reference.md` | `apparitions.json` | 10 apparitions |
| `Litany-of-Loreto-Annotated.md` | `litany.json` | 54 titles · 6 groups |
| `Marian-Office-of-Readings-Sourcebook.md` | `office.json` | 15 + 3 supplementary |
| `Akathist-Hymn-Translated-Annotated.md` | `akathist.json` | 24 stanzas + prooemion |
| `Marian-Iconography-Reference.md` | `iconography.json` | 39 sections |
| `_Perfect-Prompts-Mariology-Build.md` | `prompts.json` | 12 prompts |
| — | `search-index.json` | 218 entries |

Total: **~232 KB JSON**.

---

## Architecture

```
tools/
├── build-mediatrix.py     ← main script: argparse, runner, search-index, all extractors
├── lib/
│   ├── __init__.py
│   └── parser.py          ← parsing primitives shared by every extractor
└── README.md              ← this file
```

`lib/parser.py` supplies:
- `parse_frontmatter(text) → (dict, body)` — simple YAML head matter
- `split_sections(text) → Section` — tree of H1/H2/H3 sections
- `extract_blockquotes(body) → list[str]` — contiguous `> ` blocks
- `extract_metadata_lines(body) → dict` — `- **Key:** value` lines
- `parse_provenance(line)` / `parse_pole(line)` — provenance and pole detection
- `parse_numbered_header(title)` — `"1. The Annunciation" → (1, "The Annunciation")`
- `strip_markdown()`, `normalize_whitespace()`, `read_source()`

`build-mediatrix.py` exports one `extract_<name>()` function per source.
Each is pure: same markdown in → same JSON out. No state, no side effects.

---

## JSON shape

Every output is wrapped with this provenance metadata:

```json
{
  "schema_version": 1,
  "source_file": "Marian-Concise-Anthology.md",
  "source_mtime": "2026-05-15T04:22:00",
  "generated_at": "2026-05-15T15:24:13",
  "title": "The Marian Concise Anthology, ...",
  "saints": [ ... ],
  "saint_count": 49
}
```

Sample anthology saint record:

```json
{
  "num": 23,
  "name": "St. Bernard of Clairvaux",
  "dates": "1090 - 1153",
  "language": "Latin, \"Marian Doctor\"",
  "era_title": "Part V — Medieval Doctors",
  "era_slug": "medieval",
  "original_language": "latin",
  "original": "Totum nos habere voluit per Mariam.",
  "english": "He willed that we should have everything through Mary.",
  "source": "Sermon on the Aqueduct (In Nativitate B. Mariae), §7.",
  "provenance": "verbatim",
  "pole": "M"
}
```

Sample search-index entry:

```json
{
  "slug": "anthology.html#s23",
  "kind": "saint",
  "title": "St. Bernard of Clairvaux",
  "subtitle": "1090 - 1153 · Latin, \"Marian Doctor\"",
  "body": "He willed that we should have everything through Mary. Totum nos habere voluit per Mariam. Sermon on the Aqueduct (In Nativitate B. Mariae), §7."
}
```

---

## Hard rules

1. **The pipeline is pure.** Same markdown in → same JSON out. No
   network, no external dependencies, no time-based side effects. Python
   stdlib only.
2. **The markdown is canonical.** Pipeline reads; it never writes back
   into the vault.
3. **JSON files are generated, not edited.** If a value is wrong, fix
   the markdown and rerun. Hand-edits to `site/data/*.json` will be
   overwritten on next build.
4. **Schema versioning.** Every output carries `schema_version`.
   Increment when breaking changes are made.
5. **Provenance preserved.** Every saint card / type / objection that
   was tagged VERBATIM / TRADITIONAL / DISPUTED / LITURGICAL /
   MAGISTERIAL in the markdown is tagged identically in JSON.

---

## Extending the pipeline

To add a new source file or a new field to an existing extractor:

1. Add or edit the `extract_<name>()` function in `build-mediatrix.py`
2. Register it in the `EXTRACTORS` dict at the bottom of the file
3. Rebuild: `python3 tools/build-mediatrix.py <name>` (single) or
   `make build-data` (all)
4. Verify: `make verify-data`
5. Update `tools/README.md`'s record-count table

To change the search-index shape, edit `build_search_index()`.

---

## Why pure stdlib?

A devotional library should be readable in twenty years. Every external
dependency is a future break. The pipeline therefore uses only Python's
standard library: no PyYAML, no Markdown, no Jinja, no requests. The
trade-off is a small, hand-rolled frontmatter and Markdown reader in
`lib/parser.py`, under three hundred lines, no surprises.

---

*Sub tuum praesidium confugimus, Sancta Dei Genitrix.*
