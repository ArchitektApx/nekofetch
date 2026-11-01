"""GitHub social preview (1280x640): the README screenshot plus name and tagline.

python3 tools/social.py      needs Pillow and the screenshot (tools/screenshot.py)
"""

import glob
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 640
BG_TOP, BG_BOTTOM = (24, 24, 34), (40, 28, 52)
PINK, PURPLE, GREY, WHITE = (255, 121, 198), (189, 147, 249), (139, 145, 180), (248, 248, 242)
FONTS = os.path.expanduser("~/Library/Fonts")


def font(style: str, size: int) -> ImageFont.FreeTypeFont:
    path = next(iter(sorted(glob.glob(f"{FONTS}/JetBrainsMono*NerdFontMono-{style}.ttf"))))
    return ImageFont.truetype(path, size)


def cat(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """The kaomoji, glyph by glyph: no single font has all of them (macOS fonts)."""
    mono = font("Regular", 30)
    special = {
        "ᓚ": ImageFont.truetype("/System/Library/Fonts/Supplemental/EuphemiaCAS.ttc", 30),
        "₍": ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 30),
        "₎": ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 30),
    }
    for ch in "ᓚ₍ ^. .^₎":
        d.text((x, y), ch, font=special.get(ch, mono), fill=PURPLE, anchor="ls")
        x += round(mono.getlength("M"))


def main():
    card = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(card)
    for y in range(H):  # soft vertical gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM, strict=True)))

    shot = Image.open(os.path.join(ROOT, "assets", "screenshot.png")).convert("RGBA")
    shot = shot.crop(shot.getbbox())  # drop the transparent margin around the window and shadow
    scale = min(800 / shot.width, 560 / shot.height)
    shot = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)
    x, y = W - shot.width - 40, (H - shot.height) // 2
    card.paste(shot, (x, y), shot)

    # the text block, centered vertically: (text, font, color, space after)
    title, tag, small = font("Bold", 64), font("Regular", 30), font("Regular", 22)
    lines = [
        ("nekofetch", title, PINK, 14),
        ("fastfetch, but", tag, WHITE, 6),
        ("with catgirls.", tag, WHITE, 34),
        ("macOS · Linux", small, GREY, 8),
        ("kitty · Ghostty", small, GREY, 8),
        ("iTerm2 · WezTerm", small, GREY, 40),
    ]
    cat_height = 30
    total = sum(f.size + gap for _, f, _, gap in lines) + cat_height
    left, y = 56, (H - total) // 2
    for text, f, color, gap in lines:
        d.text((left, y), text, font=f, fill=color)
        y += f.size + gap
    cat(d, left, y + cat_height)

    out = os.path.join(ROOT, "assets", "social-preview.png")
    card.save(out, optimize=True)
    print(out, f"{os.path.getsize(out) // 1024} KB")


if __name__ == "__main__":
    main()
