"""Génère les icônes LeanLens (logo192/512, favicon) à partir du motif lens.

Usage :  python brand/make_icons.py
Sortie : brand/logo192.png, brand/logo512.png, brand/favicon.ico
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BLUE = (30, 94, 255, 255)        # #1E5EFF
BLUE_SOFT = (111, 160, 255, 255)  # #6FA0FF
FONT = r"C:\Windows\Fonts\arialbd.ttf"


def draw_mark(size: int, with_text: bool = False) -> Image.Image:
    """Motif 'lentille' centré (anneau + pupille + reflet)."""
    scale = size / 110
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = 40 * scale
    cx = cy = size * 0.42 if with_text else size / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLUE, width=max(2, int(4.4 * scale)))
    # pupille (elliptique, légère rotation simulée par rx/ry)
    d.ellipse([cx - r * 0.48, cy - r * 0.30, cx + r * 0.48, cy + r * 0.30], fill=BLUE)
    # reflet
    gr = r * 0.16
    d.ellipse([cx + r * 0.48 - gr, cy - r * 0.52 - gr, cx + r * 0.48 + gr, cy - r * 0.52 + gr], fill=BLUE_SOFT)
    if with_text:
        font = ImageFont.truetype(FONT, int(15 * scale))
        d.text((cx + r * 1.35, cy), "LeanLens", font=font, fill=BLUE, anchor="lm")
    return img


def main() -> None:
    # logo192 : motif + mot (format bandeau proche du logo d'origine)
    banner = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    mark = draw_mark(192, with_text=False)
    banner.alpha_composite(mark)
    d = ImageDraw.Draw(banner)
    font = ImageFont.truetype(FONT, 34)
    d.text((96, 158), "LeanLens", font=font, fill=BLUE, anchor="mm")
    banner.save(HERE / "logo192.png")

    # logo512 : motif seul (icône app)
    draw_mark(512).save(HERE / "logo512.png")

    # favicon multi-résolutions
    sizes = [(16, 16), (32, 32), (48, 48)]
    frames = [draw_mark(s[0]).resize(s, Image.LANCZOS) for s in sizes]
    frames[-1].save(HERE / "favicon.ico", sizes=sizes)
    print("icônes générées : logo192.png, logo512.png, favicon.ico")


if __name__ == "__main__":
    main()
