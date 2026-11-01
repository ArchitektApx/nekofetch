#!/usr/bin/env python3
"""
Renders the README hero: real nekofetch output in a terminal window, with one of
the bundled cats animated in the logo spot. Needs Pillow, zsh and a JetBrainsMono
Nerd Font, and looks for fonts where macOS keeps them (set FONT=path elsewhere).

  python3 tools/screenshot.py [cat] [out.gif]     cat: typing, sleepy, yay, ...
"""

import contextlib
import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageSequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.expanduser("~/Library/Fonts")
FONT = os.environ.get("FONT") or next(iter(sorted(glob.glob(f"{FONTS}/JetBrainsMono*NerdFontMono-Regular.ttf"))), "")
BOLD = FONT.replace("-Regular", "-Bold")
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"

SIZE = 26
BG = (30, 31, 41)
FG = (248, 248, 242)
LOGO_W, LOGO_H = 30, 16
PAD_TOP = 2  # layout.jsonc logo padding


def capture():
    blank = "\n".join([" " * LOGO_W] * LOGO_H)
    env = dict(
        os.environ,
        COLUMNS="120",
        LANG="en_US.UTF-8",
        TERM_PROGRAM="ghostty",
        TERM_PROGRAM_VERSION="1.4.0",
        GHOSTTY_RESOURCES_DIR="/x",
    )
    env.pop("TMUX", None)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    # through a shell, so fastfetch's Shell row shows zsh rather than python
    args = ["-p", "none", "--", "--pipe", "false", "--logo-type", "data-raw", "--logo", blank]
    cmd = " ".join(shlex.quote(a) for a in [sys.executable, "-m", "nekofetch", *args])
    return subprocess.run(
        ["zsh", "-c", cmd + "; true"], capture_output=True, text=True, env=env, cwd=tempfile.gettempdir(), check=False
    ).stdout  # outside any git repo


def emulate(text, cols=130, rows=40):
    """Tiny terminal: cursor moves, CR/LF and 24-bit SGR. Returns rows of cells."""
    grid = [[(" ", FG, False, None) for _ in range(cols)] for _ in range(rows)]
    x = y = 0
    fg, bold, bg = FG, False, None
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\033":
            m = re.match(r"\033\[([\d;?]*)([A-Za-z])", text[i:])
            if not m:
                i += 1
                continue
            args, cmd = m.group(1), m.group(2)
            nums = [int(n) if n.isdigit() else 0 for n in args.replace("?", "").split(";")] if args else []
            n = nums[0] if nums and nums[0] else 1
            if cmd == "A":
                y = max(0, y - n)
            elif cmd == "B":
                y += n
            elif cmd == "C":
                x += n
            elif cmd == "D":
                x = max(0, x - n)
            elif cmd == "G":
                x = n - 1
            elif cmd == "m":
                k = 0
                nums = nums or [0]
                while k < len(nums):
                    v = nums[k]
                    if v == 0:
                        fg, bold, bg = FG, False, None
                    elif v == 1:
                        bold = True
                    elif v == 22:
                        bold = False
                    elif v == 39:
                        fg = FG
                    elif v == 38 and k + 4 < len(nums) and nums[k + 1] == 2:
                        fg = tuple(nums[k + 2 : k + 5])
                        k += 4
                    elif v == 48 and k + 4 < len(nums) and nums[k + 1] == 2:
                        bg = tuple(nums[k + 2 : k + 5])
                        k += 4
                    elif v == 49:
                        bg = None
                    elif 30 <= v <= 37 or 90 <= v <= 97:
                        pass
                    k += 1
            i += len(m.group(0))
            continue
        if ch == "\n":
            y += 1
            x = 0
        elif ch == "\r":
            x = 0
        elif y < rows and x < cols:
            grid[y][x] = (ch, fg, bold, bg)
            x += 1
        i += 1
    while grid and all(c[0] == " " for c in grid[-1]):
        grid.pop()
    return grid


FALLBACKS = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Supplemental/EuphemiaCAS.ttc"]


def glyph_font(ch, fonts):
    """The first font that has a glyph for ch."""
    for f in fonts:
        tofu = f.getmask("\U0010fffd").getbbox()
        box = f.getmask(ch).getbbox()
        if box and box != tofu:
            return f
    return fonts[0]


def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else "typing"
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "assets", "screenshot.gif")
    if not FONT:
        sys.exit("needs a JetBrainsMono Nerd Font (or set FONT=path)")
    font = ImageFont.truetype(FONT, SIZE)
    bold = ImageFont.truetype(BOLD, SIZE) if os.path.exists(BOLD) else font
    cw = round(font.getlength("M"))
    ch = round(SIZE * 1.35)

    raw = capture()
    grid = emulate(raw)
    # window size: the widest row of output, plus a little room
    cols = max((max((i for i, c in enumerate(r) if c[0] != " "), default=0) for r in grid), default=0) + 3
    rows = len(grid) + 1

    margin, bar = 36, 44
    W = margin * 2 + cols * cw
    H = bar + margin + rows * ch + margin // 2
    base = Image.new("RGBA", (W + 60, H + 60), (0, 0, 0, 0))
    # soft shadow
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((30, 36, 30 + W, 36 + H), 16, fill=(0, 0, 0, 110))
    from PIL import ImageFilter

    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    base.alpha_composite(shadow)
    win = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    d.rounded_rectangle((0, 0, W - 1, H - 1), 14, fill=(*BG, 255), outline=(68, 71, 90, 255))
    for k, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse((20 + k * 24, 16, 34 + k * 24, 30), fill=c)
    title = "~ nekofetch"
    d.text(
        ((W - font.getlength(title) * 0.75) / 2, 13),
        title,
        font=ImageFont.truetype(FONT, int(SIZE * 0.75)),
        fill=(98, 114, 164),
    )

    emoji_font = None
    if os.path.exists(EMOJI):
        with contextlib.suppress(OSError):
            emoji_font = ImageFont.truetype(EMOJI, 160)

    fallbacks = [ImageFont.truetype(f, SIZE) for f in FALLBACKS if os.path.exists(f)]
    # backgrounds span exactly what the rounded powerline caps span, so pills line up
    text_y = (ch - SIZE) / 2 - 2
    _, cap_top, _, cap_bottom = font.getbbox("\ue0b6")
    bg_top, bg_bottom = text_y + cap_top, text_y + cap_bottom - 1
    ox, oy = margin, bar + margin // 2
    for r, row in enumerate(grid):
        c = 0
        while c < len(row):
            chr_, fg, b, bg = row[c]
            px, py = ox + c * cw, oy + r * ch
            if bg:
                d.rectangle((px, py + bg_top, px + cw, py + bg_bottom), fill=bg)
            if chr_ != " ":
                if 0x1F000 <= ord(chr_) <= 0x1FAFF and emoji_font:
                    e = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
                    ImageDraw.Draw(e).text((0, 0), chr_, font=emoji_font, embedded_color=True)
                    e = e.crop(e.getbbox()).resize((SIZE, SIZE), Image.LANCZOS)
                    win.alpha_composite(e, (int(px), int(py + (ch - SIZE) / 2)))
                else:
                    f = glyph_font(chr_, [bold if b else font, *fallbacks])
                    d.text((px, py + text_y), chr_, font=f, fill=fg)
            c += 1

    # the cat, in the logo cells
    gif = Image.open(os.path.join(ROOT, "src", "nekofetch", "data", "images", f"neko-{cat}.gif"))
    side = min(LOGO_W * cw, LOGO_H * ch)
    lx = ox + (LOGO_W * cw - side) // 2
    ly = oy + PAD_TOP * ch + (LOGO_H * ch - side) // 2
    frames, durations = [], []
    for f in ImageSequence.Iterator(gif):
        frame = base.copy()
        w = win.copy()
        w.alpha_composite(f.convert("RGBA").resize((side, side), Image.NEAREST), (int(lx), int(ly)))
        frame.alpha_composite(w, (30, 24))
        frames.append(frame)
        durations.append(f.info.get("duration", 300))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pal = [
        fr.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        for fr in frames
    ]
    # transparent outside the window
    for p, fr in zip(pal, frames, strict=True):
        pl = p.getpalette()[: 255 * 3]
        p.putpalette(pl + [0] * (768 - len(pl)))
        p.paste(255, mask=Image.eval(fr.getchannel("A"), lambda a: 255 if a < 100 else 0))
    pal[0].save(
        out_path, save_all=True, append_images=pal[1:], duration=durations, loop=0, transparency=255, disposal=2
    )
    frames[0].save(os.path.splitext(out_path)[0] + ".png")
    print(out_path, f"{os.path.getsize(out_path) // 1024} KB")


if __name__ == "__main__":
    main()
