#!/usr/bin/env python3
"""
gen-icons.py: generate raster icons referenced by the SEO meta tags.

Outputs (all into ./site/):
  - favicon-16.png        16x16 raster of the Stella Maris
  - favicon-32.png        32x32 raster of the Stella Maris
  - apple-touch-icon-180.png  180x180 raster of the Stella Maris on cream
  - og.png                1200x630 social-preview card (Stella Maris + wordmark)

Strategy:
  - For the favicon variants: rasterize site/favicon.svg via macOS qlmanage,
    then resize via Pillow.
  - For og.png: draw natively in Pillow. The star is reconstructed from the
    same polygon coordinates used in favicon.svg, scaled to fit. Text is set
    in Georgia (or Times New Roman fallback), a system serif that ships with
    macOS, since the project's Cinzel woff2 cannot be loaded by Pillow.

Re-run any time the favicon or branding changes. Idempotent (overwrites).

Requires: Pillow (already in stdlib of most macOS Python installs), qlmanage
(part of macOS). No network access.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
TMP = Path("/tmp/mediatrix-icons")

CREAM = (249, 246, 239)
NAVY = (12, 35, 64)
GOLD = (201, 151, 0)
GOLD_DARK = (140, 107, 0)


def _font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []
    sup = Path("/System/Library/Fonts/Supplemental")
    if bold and italic:
        candidates += [sup / "Georgia Bold Italic.ttf", sup / "Times New Roman Bold Italic.ttf"]
    elif bold:
        candidates += [sup / "Georgia Bold.ttf", sup / "Times New Roman Bold.ttf"]
    elif italic:
        candidates += [sup / "Georgia Italic.ttf", sup / "Times New Roman Italic.ttf"]
    else:
        candidates += [sup / "Georgia.ttf", sup / "Times New Roman.ttf"]
    candidates += [Path("/System/Library/Fonts/Helvetica.ttc")]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_stella_maris(img: Image.Image, cx: int, cy: int, radius: int, gold=GOLD) -> None:
    """Draw the 8-pointed Stella Maris (gold) centered at (cx, cy)."""
    draw = ImageDraw.Draw(img)
    r_long = radius
    r_short = int(radius * 0.85)
    waist = int(radius * 0.12)

    # Four long cardinal points (top, right, bottom, left)
    long_points = [
        [(cx, cy - r_long), (cx + waist, cy), (cx, cy + waist), (cx - waist, cy)],
        [(cx + r_long, cy), (cx, cy + waist), (cx - waist, cy), (cx, cy - waist)],
        [(cx, cy + r_long), (cx - waist, cy), (cx, cy - waist), (cx + waist, cy)],
        [(cx - r_long, cy), (cx, cy - waist), (cx + waist, cy), (cx, cy + waist)],
    ]

    # Four short diagonal points
    diag = r_short / (2 ** 0.5)
    diag_waist = waist / (2 ** 0.5)
    diag_points = [
        [(cx + diag, cy - diag), (cx + diag_waist, cy + diag_waist),
         (cx - diag_waist, cy - diag_waist), (cx + diag_waist, cy - diag_waist)],
        [(cx + diag, cy + diag), (cx - diag_waist, cy + diag_waist),
         (cx - diag_waist, cy - diag_waist), (cx + diag_waist, cy + diag_waist)],
        [(cx - diag, cy + diag), (cx - diag_waist, cy - diag_waist),
         (cx + diag_waist, cy + diag_waist), (cx - diag_waist, cy + diag_waist)],
        [(cx - diag, cy - diag), (cx + diag_waist, cy - diag_waist),
         (cx + diag_waist, cy + diag_waist), (cx - diag_waist, cy + diag_waist)],
    ]

    for pts in long_points + diag_points:
        draw.polygon(pts, fill=gold)

    # Center circle
    cr = max(2, int(radius * 0.07))
    draw.ellipse((cx - cr, cy - cr, cx + cr, cy + cr), fill=gold)


def gen_favicons() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    for f in TMP.glob("*.png"):
        f.unlink()
    subprocess.run(
        ["qlmanage", "-t", "-s", "512", "-o", str(TMP), str(SITE / "favicon.svg")],
        check=True, capture_output=True,
    )
    src = TMP / "favicon.svg.png"
    if not src.exists():
        print("  fail: qlmanage did not produce a thumbnail")
        sys.exit(1)
    big = Image.open(src).convert("RGBA")

    for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"),
                       (180, "apple-touch-icon-180.png")]:
        out = SITE / name
        if name.startswith("apple-touch"):
            canvas = Image.new("RGBA", (size, size), CREAM + (255,))
            star = big.resize((size, size), Image.LANCZOS)
            canvas.alpha_composite(star)
            canvas.convert("RGB").save(out, "PNG", optimize=True)
        else:
            big.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
        print(f"  wrote   {out.relative_to(REPO)}")


def gen_og() -> None:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)

    # Hairline gold frame at 36 px inset
    inset = 36
    draw.rectangle((inset, inset, W - inset, H - inset), outline=GOLD, width=1)

    # Stella Maris, centered horizontally, upper-third vertically
    _draw_stella_maris(img, cx=W // 2, cy=int(H * 0.32), radius=120)

    # Wordmark in serif (Georgia bold as Cinzel surrogate)
    font_word = _font(96, bold=True)
    font_sub = _font(34, italic=True)
    font_tag = _font(22)

    word = "Mediatrix"
    w_w, w_h = draw.textbbox((0, 0), word, font=font_word)[2:]
    draw.text(((W - w_w) // 2, int(H * 0.58)), word, font=font_word, fill=NAVY)

    sub = "An Editorial Marian Study Library"
    s_w, _ = draw.textbbox((0, 0), sub, font=font_sub)[2:]
    draw.text(((W - s_w) // 2, int(H * 0.74)), sub, font=font_sub, fill=NAVY)

    tag = "SUB TUUM PRAESIDIUM CONFUGIMUS, SANCTA DEI GENITRIX"
    t_w, _ = draw.textbbox((0, 0), tag, font=font_tag)[2:]
    draw.text(((W - t_w) // 2, int(H * 0.86)), tag, font=font_tag, fill=GOLD_DARK)

    out = SITE / "og.png"
    img.save(out, "PNG", optimize=True)
    print(f"  wrote   {out.relative_to(REPO)} ({W}x{H})")


def main() -> int:
    print("=== favicon variants ===")
    gen_favicons()
    print("=== og.png ===")
    gen_og()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
