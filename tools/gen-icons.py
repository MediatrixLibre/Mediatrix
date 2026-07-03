#!/usr/bin/env python3
"""
gen-icons.py: generate raster icons referenced by the SEO meta tags + manifest.

Two-tier branding (deliberate):
  - favicon (browser tab, 16/32 px): the simple Stella Maris star (favicon.svg).
    A detailed device would be mud at favicon size.
  - app icon (home-screen / PWA, 180/512 px): the crowned Marian "M" device
    (apple-touch-icon-source.svg). The home-screen icon is what the user reads.

Outputs (all into ./site/):
  - favicon-16.png            16x16  star  (from favicon.svg)
  - favicon-32.png            32x32  star  (from favicon.svg)
  - apple-touch-icon-180.png  180x180 crowned-M (from apple-touch-icon-source.svg)
  - icon-512.png              512x512 crowned-M (from apple-touch-icon-source.svg)
  - og.png                    1200x630 social-preview card (star + wordmark)

Strategy:
  - Rasterize the relevant SVG via macOS qlmanage at 512 px, resize via Pillow.
  - App icons are composited onto a full-bleed navy square (matches the source
    SVG's outer gradient stop) so iOS/Android home-screen masks never reveal
    transparent corners.
  - For og.png: draw natively in Pillow (star reconstructed from polygon coords;
    text in Georgia / Times New Roman, a macOS system serif, since Cinzel woff2
    cannot be loaded by Pillow).

Re-run any time the favicon OR the app icon changes. Idempotent (overwrites).

Requires: Pillow, qlmanage (part of macOS). No network access.
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
NAVY_EDGE = (5, 12, 30)   # = #050C1E, outer stop of the app-icon bg gradient
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


def _rasterize(svg_name: str) -> Image.Image:
    """qlmanage-rasterize a site SVG at 512 px, return an RGBA Image."""
    TMP.mkdir(parents=True, exist_ok=True)
    for f in TMP.glob("*.png"):
        f.unlink()
    subprocess.run(
        ["qlmanage", "-t", "-s", "512", "-o", str(TMP), str(SITE / svg_name)],
        check=True, capture_output=True,
    )
    src = TMP / f"{svg_name}.png"
    if not src.exists():
        print(f"  fail: qlmanage did not produce a thumbnail for {svg_name}")
        sys.exit(1)
    return Image.open(src).convert("RGBA")


def gen_favicons() -> None:
    """Star favicons (browser tab) from favicon.svg — transparent background."""
    big = _rasterize("favicon.svg")
    for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png")]:
        out = SITE / name
        big.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
        print(f"  wrote   {out.relative_to(REPO)}")


def gen_app_icons() -> None:
    """Crowned-M app icons (home screen / PWA) from apple-touch-icon-source.svg.

    Composited onto a full-bleed navy square so iOS/Android home-screen masks
    never reveal transparent corners.
    """
    big = _rasterize("apple-touch-icon-source.svg")
    for size, name in [(180, "apple-touch-icon-180.png"), (512, "icon-512.png")]:
        out = SITE / name
        canvas = Image.new("RGBA", (size, size), NAVY_EDGE + (255,))
        device = big.resize((size, size), Image.LANCZOS)
        canvas.alpha_composite(device)
        # 256-color palette: the device is flat gold on a navy gradient, so
        # quantization is visually lossless (mean error <0.5/255, checked
        # side-by-side) and roughly halves the file (164KB -> ~87KB @512).
        quantized = canvas.convert("RGB").quantize(
            colors=256, method=Image.MEDIANCUT, dither=Image.Dither.NONE
        )
        quantized.save(out, "PNG", optimize=True)
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
    print("=== favicon variants (star) ===")
    gen_favicons()
    print("=== app icons (crowned M) ===")
    gen_app_icons()
    print("=== og.png ===")
    gen_og()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
