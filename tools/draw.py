#!/usr/bin/env python3
"""
Draws the default nekofetch images: small pixel-art catgirls, one animated GIF
per scene. Everything is drawn from code, so the art is ours to license (CC0).

  python3 tools/draw.py [datadir]    needs Pillow; default: src/nekofetch/data
"""

import os
import sys
from collections import Counter

from PIL import Image, ImageDraw

W = H = 64  # canvas in art pixels
SCALE = 6  # 384x384 output

INK = (43, 33, 53, 255)  # silhouette outline


def hexc(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def shade(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))), max(0, min(255, int(c[2] * f))), c[3])


SKIN = hexc("ffe3d2")
SKIN_SH = hexc("f5c4b0")
BLUSH = hexc("ff9cb8")
WHITE = hexc("ffffff")
EAR_IN = hexc("ffb3c9")
MOUTH = hexc("8a3a52")


class Neko:
    """One character: hair, eyes, outfit. Scenes pose her."""

    def __init__(self, hair, eyes, shirt, collar="d9405f", bell="ffd36b"):
        self.hair = hexc(hair)
        self.hair_hi = shade(self.hair, 1.15)
        self.hair_sh = shade(self.hair, 0.78)
        self.eyes = hexc(eyes)
        self.eyes_dk = shade(self.eyes, 0.55)
        self.eyes_lt = shade(self.eyes, 1.35)
        self.shirt = hexc(shirt)
        self.shirt_sh = shade(self.shirt, 0.82)
        self.collar = hexc(collar)
        self.bell = hexc(bell)


class Canvas:
    """Layers drawn back to front; each layer gets its own outline."""

    def __init__(self):
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def layer(self, outline=INK):
        return Layer(self, outline)

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.img.putpixel((x, y), c)


class Layer:
    def __init__(self, canvas, outline):
        self.canvas = canvas
        self.outline = outline
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        src = self.img
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if self.outline:
            a = src.getchannel("A").load()
            o = out.load()
            for y in range(H):
                for x in range(W):
                    if a[x, y]:
                        continue
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < H and a[nx, ny]:
                            o[x, y] = self.outline
                            break
        out.alpha_composite(src)
        self.canvas.img.alpha_composite(out)

    # drawing helpers ---------------------------------------------------------
    def ellipse(self, box, c):
        self.d.ellipse(box, fill=c)

    def poly(self, pts, c):
        self.d.polygon(pts, fill=c)

    def rect(self, box, c):
        self.d.rectangle(box, fill=c)

    def line(self, pts, c, w=1):
        self.d.line(pts, fill=c, width=w)

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.img.putpixel((x, y), c)

    def sprite(self, x, y, rows, colors):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in colors:
                    self.px(x + i, y + j, colors[ch])


# --- body parts --------------------------------------------------------------


def back_hair(cv, n, dy=0, long=True):
    with cv.layer() as l:
        l.ellipse((14, 13 + dy, 50, 47 + dy), n.hair_sh)
        if long:
            l.poly(
                [
                    (15, 30 + dy),
                    (49, 30 + dy),
                    (51, 58 + dy),
                    (45, 55 + dy),
                    (40, 58 + dy),
                    (24, 58 + dy),
                    (19, 55 + dy),
                    (13, 58 + dy),
                ],
                n.hair_sh,
            )


def ears(cv, n, dy=0, twitch=0):
    with cv.layer() as l:
        l.poly([(16, 26 + dy), (17 - twitch, 4 + dy + twitch), (30, 16 + dy)], n.hair)
        l.poly([(48, 26 + dy), (47, 4 + dy), (34, 16 + dy)], n.hair)
        l.poly([(19, 22 + dy), (19 - twitch, 9 + dy + twitch), (27, 17 + dy)], EAR_IN)
        l.poly([(45, 22 + dy), (45, 9 + dy), (37, 17 + dy)], EAR_IN)


def head(cv, _n, dy=0):
    with cv.layer() as l:
        l.ellipse((16, 13 + dy, 48, 47 + dy), SKIN)
        l.poly([(22, 43 + dy), (42, 43 + dy), (37, 46 + dy), (27, 46 + dy)], SKIN_SH)


def bangs(cv, n, dy=0):
    with cv.layer() as l:
        l.d.pieslice((14, 7 + dy, 50, 43 + dy), 180, 360, fill=n.hair)  # top of the head
        # fringe: strands with a little part in the middle
        tips = [
            (15, 28),
            (18, 23),
            (21, 27),
            (24, 22),
            (27, 26),
            (29, 21),
            (31, 25),
            (33, 19),
            (34, 25),
            (37, 21),
            (40, 26),
            (43, 22),
            (46, 27),
            (49, 23),
        ]
        l.poly([(14, 20 + dy)] + [(x, y + dy) for x, y in tips] + [(50, 20 + dy)], n.hair)
        # side locks framing the cheeks
        l.poly([(14, 20 + dy), (19, 22 + dy), (19, 38 + dy), (17, 48 + dy), (14, 40 + dy)], n.hair)
        l.poly([(50, 20 + dy), (45, 22 + dy), (45, 38 + dy), (47, 48 + dy), (50, 40 + dy)], n.hair)
        # shine band
        for x, y in ((21, 15), (22, 14), (23, 14), (24, 13), (25, 13), (39, 13), (40, 13), (41, 14)):
            l.px(x, y + dy, n.hair_hi)
        for x, y in ((24, 22), (29, 21), (37, 21), (43, 22)):
            l.line([(x, y + dy - 5), (x, y + dy - 1)], n.hair_sh)


EYE_OPEN = [
    "......k.",
    ".kkkkkk.",
    "kkddddkk",
    "kdwwdddk",
    "kdwwdddk",
    "kddddddk",
    "kiiiiiik",
    "kilwliik",
    ".kiiiik.",
]
EYE_WIDE = [
    ".kkkkkk.",
    "kkddddkk",
    "kdwwdddk",
    "kdwwdddk",
    "kddddddk",
    "kiiiiiik",
    "kiiiiiik",
    "kilwliik",
    ".kiiiik.",
]
EYE_HAPPY = [  # ^ ^
    "........",
    "..kkkk..",
    ".kk..kk.",
    "kk....kk",
    "k......k",
]
EYE_CLOSED = [  # sleepy curve
    "........",
    "........",
    "k......k",
    "kk....kk",
    ".kkkkkk.",
]


def face(cv, n, dy=0, eyes="open", mouth="cat", blush=True):
    pal = {"k": INK, "d": n.eyes_dk, "i": n.eyes, "l": n.eyes_lt, "w": WHITE}
    with cv.layer(outline=None) as l:
        sprite = {"open": EYE_OPEN, "happy": EYE_HAPPY, "closed": EYE_CLOSED, "wide": EYE_WIDE}[eyes]
        ey = 28 + dy if eyes in ("open", "wide") else 31 + dy
        l.sprite(20, ey, sprite, pal)
        l.sprite(36, ey, [r[::-1] for r in sprite], pal)
        if blush:
            for x in (19, 21, 41, 43):
                l.px(x, 38 + dy, BLUSH)
                l.px(x + 1, 38 + dy, BLUSH)
                l.px(x, 39 + dy, shade(BLUSH, 1.05))
        m = {
            "cat": ["k.k.k", ".k.k."],  # :3 / w
            "open": [".kkk.", "kmmmk", ".kmk."],
            "small": [".kk.."],
            "chew": ["kkkk.", ".mm.."],
            "o": [".k.", "kmk", ".k."],
        }[mouth]
        mx = 30 if mouth != "o" else 31
        l.sprite(mx, 40 + dy, m, {"k": MOUTH, "m": hexc("e86a86")})


def body(cv, n, dy=0):
    with cv.layer() as l:
        l.poly([(21, 63), (24, 47 + dy), (40, 47 + dy), (43, 63)], n.shirt)
        l.line([(32, 50 + dy), (32, 63)], n.shirt_sh)
    with cv.layer() as l:
        l.rect((25, 45 + dy, 39, 47 + dy), n.collar)
        l.ellipse((30, 47 + dy, 34, 51 + dy), n.bell)
        l.px(31, 48 + dy, shade(n.bell, 1.2))
        l.px(32, 50 + dy, shade(n.bell, 0.6))


def tail(cv, n, phase=0):
    sway = [0, 2, 3, 2][phase % 4]
    with cv.layer() as l:
        pts = [(44, 60), (50, 56), (53, 49 - sway), (55, 43 - sway)]
        l.line(pts, n.hair, w=3)
        l.ellipse((53, 40 - sway, 57, 44 - sway), n.hair_hi)


def paw(l, x, y, c, pad=EAR_IN):
    l.ellipse((x, y, x + 6, y + 5), c)
    l.px(x + 2, y + 1, pad)
    l.px(x + 4, y + 1, pad)


# --- props -------------------------------------------------------------------


def desk(cv, top=50):
    with cv.layer() as l:
        l.rect((0, top, 63, 63), hexc("c79a6d"))
        l.line([(0, top + 1), (63, top + 1)], hexc("dbb489"))


def keyboard(cv, top=50, lit=None):
    with cv.layer() as l:
        l.poly([(12, top + 10), (16, top + 2), (50, top + 2), (54, top + 10)], hexc("3a3f5c"))
        keys = hexc("5b6187")
        for row, (x0, x1) in enumerate(((17, 48), (16, 50), (15, 51))):
            y = top + 4 + row * 2
            for x in range(x0, x1, 3):
                l.rect((x, y, x + 1, y), hexc("ffd6f0") if lit and (x, row) in lit else keys)


def zzz(cv, frame):
    with cv.layer(outline=None) as l:
        c = hexc("bd93f9")
        for i, (x, y) in enumerate(((47, 22), (52, 14), (57, 6))):
            if i > frame % 4:
                break
            s = 2 + i
            l.line([(x, y), (x + s, y), (x, y + s), (x + s, y + s)], c)


def heart(l, x, y, c=hexc("ff79c6")):
    l.sprite(x, y, [".k.k.", "kkkkk", "kkkkk", ".kkk.", "..k.."], {"k": c})


def onigiri(cv, x, y, bites=0):
    with cv.layer() as l:
        l.poly([(x, y + 12), (x + 7, y), (x + 14, y + 12)], WHITE)
        l.rect((x + 4, y + 7, x + 10, y + 12), hexc("2f3a2f"))
        if bites:  # one bite out of the tip, getting bigger
            r = 1 + bites
            l.ellipse((x + 7 - r, y - r + 1, x + 7 + r, y + r + 1), (0, 0, 0, 0))


# --- scenes ------------------------------------------------------------------


def scene_typing(n, f):
    cv = Canvas()
    tail(cv, n, f)
    back_hair(cv, n)
    body(cv, n)
    ears(cv, n, twitch=1 if f == 2 else 0)
    head(cv, n)
    face(cv, n, eyes="wide" if f % 2 else "open", mouth="o")
    bangs(cv, n)
    desk(cv)
    lit = {(20, 0), (32, 1), (41, 2)} if f % 2 else {(26, 1), (38, 0), (44, 2)}
    keyboard(cv, lit=lit)
    with cv.layer() as l:
        up = f % 2
        paw(l, 20, 49 - (2 if up else 0), SKIN)
        paw(l, 37, 49 - (0 if up else 2), SKIN)
    return cv.img


def scene_sleepy(n, f):
    cv = Canvas()
    dy = 3 + (1 if f in (1, 2) else 0)  # breathing
    tail(cv, n, f // 2)
    desk(cv, top=58)
    pillow(cv)
    back_hair(cv, n, dy=dy, long=False)
    ears(cv, n, dy=dy, twitch=1 if f == 3 else 0)
    head(cv, n, dy=dy)
    face(cv, n, dy=dy, eyes="closed", mouth="small")
    bangs(cv, n, dy=dy)
    with cv.layer() as l:  # paws hugging the pillow
        paw(l, 8, 46, SKIN)
        paw(l, 50, 46, SKIN)
    zzz(cv, f)
    return cv.img


def pillow(cv):
    """One big soft pillow, so nobody mistakes it for anything else."""
    cloth, shade_, seam = hexc("eeeaf8"), hexc("d6d0ea"), hexc("bdb5d8")
    with cv.layer() as l:
        l.d.rounded_rectangle((3, 44, 60, 62), radius=4, fill=cloth)
        l.d.rounded_rectangle((3, 55, 60, 62), radius=4, fill=shade_)
        l.line([(6, 58), (57, 58)], seam)


def scene_onigiri(n, f):
    cv = Canvas()
    tail(cv, n, f)
    back_hair(cv, n)
    body(cv, n)
    ears(cv, n)
    head(cv, n)
    face(cv, n, eyes="happy", mouth="chew" if f % 2 else "cat")
    bangs(cv, n)
    onigiri(cv, 25, 46, bites=f // 2)
    with cv.layer() as l:
        paw(l, 20, 54, SKIN)
        paw(l, 38, 54, SKIN)
    if f % 2:
        with cv.layer(outline=None) as l:  # mogu mogu motion marks
            for x, y in ((10, 38), (12, 42), (52, 38), (50, 42)):
                l.line([(x, y), (x + 2, y)], hexc("bd93f9"))
    return cv.img


def scene_yay(n, f):
    cv = Canvas()
    dy = -2 if f % 2 else 0
    tail(cv, n, f)
    with cv.layer() as l:  # arms up behind the head
        l.line([(24, 50 + dy), (10, 30 + dy - f % 2), (8, 22 + dy)], SKIN, w=4)
        l.line([(40, 50 + dy), (54, 30 + dy - f % 2), (56, 22 + dy)], SKIN, w=4)
        paw(l, 5, 17 + dy, SKIN)
        paw(l, 53, 17 + dy, SKIN)
    back_hair(cv, n, dy=dy)
    body(cv, n, dy=dy)
    ears(cv, n, dy=dy)
    head(cv, n, dy=dy)
    face(cv, n, dy=dy, eyes="happy", mouth="open")
    bangs(cv, n, dy=dy)
    if f % 2:
        with cv.layer(outline=None) as l:
            for x, y in ((3, 4), (58, 8), (30, 2)):
                l.sprite(x, y, [".y.", "yyy", ".y."], {"y": hexc("f1fa8c")})
    return cv.img


def scene_pat(n, f):
    cv = Canvas()
    press = 2 if f % 2 else 0
    tail(cv, n, f)
    back_hair(cv, n, dy=press)
    body(cv, n)
    ears(cv, n, dy=press, twitch=1 if f % 2 else 0)
    head(cv, n, dy=press)
    face(cv, n, dy=press, eyes="happy", mouth="cat")
    bangs(cv, n, dy=press)
    with cv.layer() as l:  # a human hand resting on her head, fingers toward us
        hy = press
        hand, crease = hexc("ffd1b8"), hexc("e6ad95")
        l.rect((27, 0, 43, 3 + hy), hexc("6272a4"))  # sleeve
        l.ellipse((24, 1 + hy, 44, 11 + hy), hand)  # back of the hand
        for i, x in enumerate((25, 29, 33, 37)):  # fingers
            l.rect((x, 6 + hy, x + 3, 13 + hy + (i in (1, 2))), hand)
        l.ellipse((40, 5 + hy, 46, 11 + hy), hand)  # thumb
        for x in (28, 32, 36):
            l.line([(x, 8 + hy), (x, 13 + hy)], crease)
    with cv.layer(outline=None) as l:
        rise = f * 3
        heart(l, 6, 40 - rise)
        heart(l, 53, 34 - rise, hexc("bd93f9"))
    return cv.img


def scene_peek(n, f):
    cv = Canvas()
    blink = f == 2
    # she leans in from the left behind a wall
    with cv.layer() as l:
        l.rect((40, 0, 63, 63), hexc("44475a"))
        for y in range(4, 64, 8):
            l.line([(40, y), (63, y)], hexc("3a3c4e"))
    ox = -10 + min(f, 1) * 4
    sub = Canvas()
    back_hair(sub, n)
    ears(sub, n, twitch=1 if f == 3 else 0)
    head(sub, n)
    face(sub, n, eyes="closed" if blink else "open", mouth="cat")
    bangs(sub, n)
    body(sub, n)
    shifted = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shifted.alpha_composite(sub.img.crop((0, 0, W, H)), (ox + 8, 0))
    wall = cv.img
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(shifted)
    out.alpha_composite(wall)
    with Layer(Canvas(), INK) as _:
        pass
    # paw holding the wall edge
    cv2 = Canvas()
    cv2.img = out
    with cv2.layer() as l:
        paw(l, 36, 44, SKIN)
    return cv2.img


CAST = {
    "typing": (Neko("f2cfa0", "3fc9b0", "f7f2ea"), scene_typing, 4, 260),
    "sleepy": (Neko("ff9f5a", "6a8cff", "8be9fd"), scene_sleepy, 4, 500),
    "onigiri": (Neko("b9a0ff", "a678ff", "3b3552", collar="ff79c6"), scene_onigiri, 6, 300),
    "yay": (Neko("ff9ecf", "ff6fa8", "f8f8f2"), scene_yay, 2, 320),
    "pat": (Neko("e8e6f2", "8fb8ff", "bd93f9", collar="44475a"), scene_pat, 4, 380),
    "peek": (Neko("3b3552", "ffb86c", "ff5555", collar="f8f8f2"), scene_peek, 4, 450),
}


def save_png(frame, path):
    frame.resize((W * SCALE, H * SCALE), Image.NEAREST).save(path, optimize=True)


def halve(frame):
    """64x64 -> 32x32: each 2x2 block becomes its most common color, outlines first."""
    out = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    px = frame.load()
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            block = [px[x + dx, y + dy] for dy in (0, 1) for dx in (0, 1)]
            opaque = [p for p in block if p[3] > 127]
            if len(opaque) < 2:
                continue
            color = INK if INK in opaque else Counter(opaque).most_common(1)[0][0]
            out.putpixel((x // 2, y // 2), color)
    return out


def save_blocks(frame, path):
    """Half-block truecolor art: one cell is two pixels, ▀ in the top color on the bottom color.
    Color codes are only written when the color changes, which keeps the files small."""
    w, h = frame.size
    px = frame.load()
    rows = []
    for y in range(0, h, 2):
        row, state = "", None
        for x in range(w):
            top, bottom = px[x, y], px[x, y + 1]
            if top[3] and bottom[3]:
                want, char = (f"38;2;{top[0]};{top[1]};{top[2]};48;2;{bottom[0]};{bottom[1]};{bottom[2]}"), "▀"
            elif top[3] or bottom[3]:
                c = top if top[3] else bottom
                want, char = f"0;38;2;{c[0]};{c[1]};{c[2]}", "▀" if top[3] else "▄"
            else:
                want, char = "0", " "
            if want != state:
                row += f"\033[{want}m"
                state = want
            row += char
        rows.append(row.rstrip(" ") + "\033[0m")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")


# braille dot bit for (x, y) inside a 2x4 cell
BRAILLE = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (0, 3): 0x40,
    (1, 3): 0x80,
}


def save_braille(frame, path):
    """Braille line art for the text-only fallback: a dot for every pixel that isn't light."""
    w, h = frame.size
    px = frame.load()

    def dot(x, y):
        r, g, b, a = px[x, y]
        return a > 127 and 0.299 * r + 0.587 * g + 0.114 * b < 185

    rows = []
    for cy in range(0, h, 4):
        cells = [
            chr(0x2800 + sum(bit for (dx, dy), bit in BRAILLE.items() if dot(cx + dx, cy + dy)))
            for cx in range(0, w, 2)
        ]
        rows.append("".join(cells).rstrip("\u2800"))
    while rows and not rows[-1]:
        rows.pop()
    with open(path, "w", encoding="utf-8") as f:
        f.write("$1" + "\n$1".join(rows) + "\n")


def save_gif(frames, path, ms):
    big = [f.resize((W * SCALE, H * SCALE), Image.NEAREST) for f in frames]
    # GIF transparency is one bit; quantize each frame and keep alpha as a key color
    out = []
    for f in big:
        alpha = f.getchannel("A")
        p = f.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        pal = p.getpalette()[: 255 * 3]
        p.putpalette(pal + [0] * (768 - len(pal)))  # index 255 exists, so it can be the key
        mask = Image.eval(alpha, lambda a: 255 if a < 128 else 0)
        p.paste(255, mask=mask)
        p.info["transparency"] = 255
        out.append(p)
    out[0].save(
        path, save_all=True, append_images=out[1:], duration=ms, loop=0, transparency=255, disposal=2, optimize=False
    )


def main():
    """Writes images/, blocks/ and neko.txt into the data folder (or the folder given)."""
    data = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "nekofetch", "data")
    )
    images, blocks = os.path.join(data, "images"), os.path.join(data, "blocks")
    os.makedirs(images, exist_ok=True)
    os.makedirs(blocks, exist_ok=True)
    for name, (n, fn, count, ms) in CAST.items():
        frames = [fn(n, f) for f in range(count)]
        save_gif(frames, os.path.join(images, f"neko-{name}.gif"), ms)
        save_png(frames[0], os.path.join(images, f"neko-{name}.png"))  # for PNG-only terminals
        # for terminals without images: half-block art, large and small
        save_blocks(frames[0], os.path.join(blocks, f"neko-{name}-large.ans"))
        save_blocks(halve(frames[0]), os.path.join(blocks, f"neko-{name}-small.ans"))
        if name == "yay":  # the text-only cat
            save_braille(frames[0], os.path.join(data, "neko.txt"))
        print(f"neko-{name}  {count} frames")


if __name__ == "__main__":
    main()
