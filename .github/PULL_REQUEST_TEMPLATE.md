<!-- A quiet template for editorial pull requests. -->

## What changes

<!-- One paragraph. The substance of the change, not the keystrokes. -->

## Why

<!-- The editorial or doctrinal reason. Provenance, accuracy, restraint,
     liturgical correctness. If this is a typographic or palette change,
     reference the rule it serves in site/design.md or site/SPEC.md. -->

## Provenance

<!-- For any new quotation or claim:
     - Source (work, section, edition)
     - Provenance tag: verbatim / traditional / disputed / liturgical / magisterial
     - Translator (if not in the public domain) -->

## Pre-merge checklist

- [ ] `make check` passes locally (no dead anchors, no raw hex outside `:root`, no `href="#"`)
- [ ] `make build-data && make verify-data` succeeds if any markdown changed
- [ ] No new external CDN reference (fonts, scripts, styles)
- [ ] No new dependency in `tools/` (stdlib only)
- [ ] Vestment, rhythm, and type tokens conform to `site/design.md`
- [ ] If a new page was added: `site/sitemap.xml` updated, `site/SPEC.md` inventory updated

<!-- Sub tuum praesidium confugimus, Sancta Dei Genitrix. -->
