#!/usr/bin/env python3
"""Animated strip of all bundled cats for the README: assets/gallery.gif (needs Pillow)."""

import glob
import os

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIDE, GAP = 160, 16
cats = [
    [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(p))]
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "nekofetch", "data", "images", "neko-*.gif")))
]
W = len(cats) * SIDE + (len(cats) - 1) * GAP
out = []
for i in range(12):
    frame = Image.new("RGBA", (W, SIDE), (0, 0, 0, 0))
    for k, frames in enumerate(cats):
        frame.alpha_composite(frames[i % len(frames)].resize((SIDE, SIDE), Image.NEAREST), (k * (SIDE + GAP), 0))
    p = frame.convert("RGB").quantize(colors=255, dither=Image.Dither.NONE)
    pal = p.getpalette()[: 255 * 3]
    p.putpalette(pal + [0] * (768 - len(pal)))
    p.paste(255, mask=Image.eval(frame.getchannel("A"), lambda a: 255 if a < 128 else 0))
    out.append(p)
path = os.path.join(ROOT, "assets", "gallery.gif")
out[0].save(path, save_all=True, append_images=out[1:], duration=320, loop=0, transparency=255, disposal=2)
print(path, os.path.getsize(path) // 1024, "KB")
