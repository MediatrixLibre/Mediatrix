# Mediatrix — Design System

_The canonical styling contract. Every page must conform. Tokens live in `styles/mediatrix.css` only — never in inline `<style>` or hard-coded hex._

---

## 1. Tokens

### 1.1 Colour

| Token | Hex | Role |
|---|---|---|
| `--m-navy` | `#0C2340` | Primary ink, headings, rule lines |
| `--m-blue` | `#1E3A6E` | Marian blue — promoted to primary accent |
| `--m-gold` | `#C99700` | Crown of twelve stars, drop caps, active state, verse numbers |
| `--m-gold-text` | `#8C6B00` | Darkened gold for foreground text (5.4:1 on cream) |
| `--m-rose` | `#B66D87` | Mystical rose, disputed-badge |
| `--m-rose-deep` | `#8C4566` | Mater dolorosa |
| `--warm-grey-1` | `#EEEDEB` | Page background |
| `--warm-grey-2` | `#D9D7D3` | Hairline rules |
| `--warm-grey-3` | `#686A6E` | Light-mode metadata |
| `--warm-grey-4` | `#54585A` | Secondary text |
| `--cream` | `#F9F6EF` | Body paper panel |
| `--bone` | `#D9CFBE` | Vigil primary ink |
| `--verified` | `#3AAF66` | Verified ✓ marker |
| `--ink-deep` | `#0A1628` | Vigil page bg |
| `--ink-panel` | `#1F2842` | Vigil paper |

### 1.2 Vestment washes

`data-vestment="<name>"` on `<body>` sets section mood via a faint wash. Default is **`blue`**, Mediatrix is Marian by default. Other vestments override per page.

| Vestment | Use | Swatch |
|---|---|---|
| `blue` | Marian feasts · default | `#1E3A6E` |
| `white` | Christmas · Easter · solemnities | `#C99700` gold tint |
| `violet` | Advent · Lent | `#4A2C6F` |
| `rose` | Gaudete · Laetare | `#B66D87` |
| `red` | Passion · martyrs · Pentecost · `defense.html` | `#8B1A1A` |
| `green` | Ordinary Time | `#00843D` |

### 1.3 Rhythm

| Token | Value | Use |
|---|---|---|
| `--rhythm-half` | `0.75rem` | Stanza gutters, metadata gaps |
| `--rhythm` | `1.5rem` | Base block gap |
| `--rhythm-x2` | `3rem` | Section padding |
| `--rhythm-x3` | `4.5rem` | Between top-level sections |

### 1.4 Measures

| Token | Value | Use |
|---|---|---|
| `--measure-prose` | `68ch` | Reading column |
| `--measure-wide` | `1100px` | Masthead, index grids, footers |
| `--measure-reader` | `84ch` | Slightly wider reading column |

### 1.5 Type

| Family | Role | Weights loaded |
|---|---|---|
| **Cinzel** | Display: H1, H2, book titles, mystery titles | 500, 600, 700 |
| **Source Serif 4** | Prose, blockquotes, antiphons, italics for Greek/Latin | 400, 500, 600; italic 400, 500 (opsz 8..60) |
| **Source Sans 3** | Eyebrow kickers, meta, small-caps, nav | 400, 500, 600 |
| **JetBrains Mono** | Verse numbers, counts, keyboard hints | 400, 500 |

Italic Source Serif for Greek/Hebrew/Latin glosses and pull-quotes; never mono italic, never Cinzel italic.

Pairing rules:
- H1 Cinzel + kicker Source Sans small-caps above it
- H2 Cinzel 500, never bold
- Inline `<em>` in prose = Source Serif italic
- Numerics in counts, timestamps = JetBrains Mono, `font-variant-numeric: tabular-nums`
- Never mix Cinzel with Source Sans in the same heading

Type scale:
- H1: `clamp(2.6rem, 6vw, 4.5rem)` · Cinzel 600
- H2: `1.65rem` · Cinzel 500
- H3: `1.15rem` · Source Serif 600
- Body: `1.0625rem` · Source Serif 400 · line-height 1.62
- Meta / small-caps: `0.72rem` · Source Sans 500 · letter-spacing `0.28em` · uppercase
- Verse number: `0.74rem` · JetBrains Mono · gold

---

## 2. Modes

### 2.1 Day (default)

Cream page, navy ink, gold accent. `data-mode="day"` on `<html>` or omit.

### 2.2 Vigil

Dark reading mode for night office. `Mediatrix.setMode("vigil")` persists per-user in `localStorage.mediatrix.mode`, broadcast cross-tab via `storage`.

Swaps via `[data-mode="vigil"]` in `mediatrix.css`, not per-page:
- page bg → `--ink-deep`
- primary surface → `--ink-panel`
- body text → `--cream-night`
- accent → `--gold-night`
- rule lines → `rgba(232,180,78,0.28)`

Every page includes `#mode-toggle` in the masthead. Label flips Day ↔ Vigil.

---

## 3. Shell components

### 3.1 Masthead

```html
<header class="mast">
  <a class="mast__back" href="index.html">← Library</a>
  <a class="mast__word" href="index.html">
    Mediatrix
    <em>A Marian study library</em>
  </a>
  <div class="mast__tools">
    <button id="mode-toggle" type="button">Vigil</button>
    <a href="rosary.html">Rosary</a>
    <a href="search.html">Search</a>
  </div>
</header>
```

Cross-link choice (from the page's topic):
- **Library / Anthology** → Rosary + Search
- **Rosary** → Litany + Anthology
- **Litany** → Akathist + Anthology
- **Feasts / Apparitions** → Litany + Library
- **NT / OT / Defense** → Library + Anthology
- **Iconography / Office / Akathist** → Litany + Library
- **About / Search** → Library + Anthology
- **Index** → no `mast__back`; tools show two cross-links plus Vigil toggle

### 3.2 Colophon

```html
<footer class="colophon">
  <span class="small-caps">[page-specific count]</span>
  <span class="colophon__nav">
    <a href="index.html">Home</a><span>·</span>
    <a href="library.html">Library</a><span>·</span>
    <a href="anthology.html">Anthology</a><span>·</span>
    <a href="rosary.html">Rosary</a><span>·</span>
    <a href="litany.html">Litany</a><span>·</span>
    <a href="feasts.html">Feasts</a><span>·</span>
    <a href="apparitions.html">Apparitions</a><span>·</span>
    <a href="search.html">Search</a>
  </span>
  <span class="colophon__sub">
    <strong>Sub tuum praesidium</strong>
    Beneath thy protection we take refuge, O holy Mother of God.
  </span>
</footer>
```

The first `<span>` is page-specific (e.g. `54 Titles · 6 Sections`). The second is the same nav on every page. The third, *Sub tuum praesidium*, is the prayer that anchors the colophon. Every page closes beneath her protection.

### 3.3 Body attributes

```html
<body data-vestment="blue" data-screen-label="Litany · 54 titles">
```

### 3.4 Required scripts

In `<head>` after fonts:

```html
<link rel="stylesheet" href="styles/fonts.css" />
<link rel="stylesheet" href="styles/mediatrix.css?v=1" />
<script src="scripts/mediatrix.js?v=1"></script>
```

At the foot of `<body>`, inside `<script>…</script>`:

```html
<script>
  document.getElementById("mode-toggle").addEventListener("click", function () {
    Mediatrix.toggleMode();
    document.getElementById("mode-toggle").textContent =
      document.documentElement.dataset.mode === "vigil" ? "Day" : "Vigil";
  });
  document.getElementById("mode-toggle").textContent =
    document.documentElement.dataset.mode === "vigil" ? "Day" : "Vigil";

  Mediatrix.pushRecent({
    slug: "litany.html",
    title: "Litany of Loreto",
    subtitle: "54 titles, six structural groups",
    vestment: "blue",
    scrollRatio: 0,
  });
</script>
```

---

## 4. Editorial voice

Non-negotiable:

- **Priestly, quiet, specific.** Every claim earns its place.
- **No exclamation points** anywhere in body copy.
- **No em-dashes used for drama.** Em-dashes for true parentheticals only.
- **No emoji.** Ever.
- **No "AI-slop" filler** — no invented stats, no padding iconography, no decorative gradients, no drop-shadow flourishes.
- **Italic Source Serif** for Greek / Hebrew / Latin only, not for casual emphasis.
- **Numbers are specific.** 54 titles, 28 Old Testament types, 57 saints, 7 apparitions, 18 feasts, 20 mysteries, 7 popover-cards across four surfaces. Never "many" or "several".
- **Stella Maris is the only ornament.** The 8-pointed gold star at the masthead, the favicon, and the `.stella-rule` divider. No further iconography.

When a section feels thin, solve with composition, not more content. *Mille volte no per ogni sì.*

---

## 5. Linking conventions

- Within-page anchors: lowercase-hyphenated section slug.
- Cross-page references: relative paths (`library.html#augustine`).
- Critical-edition citations render in `.saint-source` small-caps: `PG 26.1071 · CCSL 14.234`.
- Provenance: `<span class="prov verbatim">verbatim</span>` etc.
- Pending material: `<span class="pending">forthcoming</span>` (never `href="#"`).

---

## 6. Scripting rules

- Every `<script>` block has matching `<script>…</script>` tags. `grep -n "^document\." site/*.html` must be empty.
- `Mediatrix` global is the only state bus. No direct `localStorage` writes in pages.
- No framework. No build. No transpilers. Hand-set letterpress.
- External fetches: none.

---

## 7. Accessibility

- Colour contrast: navy on cream ≥ 12:1, gold-text on cream ≥ 5.4:1 for body, ≥ 3:1 for large display.
- Focus rings never removed — `:focus-visible` with the gold `--focus-ring` token.
- `aria-disabled="true"` on pending chips, no `href`.
- Skip-to-content link on every page.
- Every interactive element is `<button>`, `<a>`, or `<input>` — never a clickable `<div>`.

---

## 8. Checklist for a new page

- [ ] `<body data-vestment="…" data-screen-label="…">`
- [ ] Masthead with `#mode-toggle` and two topic-appropriate cross-links
- [ ] Only token-based colours (no raw hex outside `:root`)
- [ ] Colophon includes page-specific count + full nav + *Sub tuum praesidium*
- [ ] `Mediatrix.pushRecent({slug, title, subtitle, vestment, scrollRatio: 0})` fires on load
- [ ] Vigil toggle wired and labelled
- [ ] No `href="#"` in primary nav
- [ ] Every `<script>` block opens and closes
- [ ] Copy follows editorial voice (no exclamation, no emoji, no filler)
- [ ] Page loads clean — no console errors

*Sub tuum praesidium confugimus, Sancta Dei Genitrix.*
