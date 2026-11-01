"""uwu mode. Uses uwuipy when it's installed alongside nekofetch
(uv tool install --with uwuipy ...), otherwise a small built-in uwuifier that's
good enough for one-liners. Lines arrive with their placeholders already filled."""

from __future__ import annotations

import importlib
import random
import re

FACES = ("owo", "uwu", ">w<", "^w^", ":3", "x3", "(・`ω\u00b4・)", "nya~", "(˘ω˘)", "✧w✧")
WORDS = {
    "you": "yuu",
    "your": "yur",
    "the": "da",
    "this": "dis",
    "that": "dat",
    "what": "wat",
    "love": "wuv",
    "small": "smol",
    "cute": "kawaii",
    "hello": "hewwo",
    "now": "nyow",
    "no": "nyo",
    "stop": "stawp",
    "with": "wif",
    "have": "haz",
    "is": "iz",
}
STUTTER_CHANCE = 0.15


def _word(word: str, rng: random.Random) -> str:
    lower = word.lower()
    if lower in WORDS:
        out = WORDS[lower]
    else:
        out = re.sub(r"[rl]", "w", word)
        out = re.sub(r"[RL]", "W", out)
        out = re.sub(r"n([aeiou])", r"ny\1", out)
        out = re.sub(r"ove\b", "uv", out)
    if out[:1].isalpha() and rng.random() < STUTTER_CHANCE:  # s-stutter
        out = f"{out[0]}-{out}"
    return out


def builtin(text: str, rng: random.Random) -> str:
    out = re.sub(r"[A-Za-z']+", lambda m: _word(m.group(0), rng), text).replace("!", "!!").rstrip()
    return f"{out} {rng.choice(FACES)}"


def uwuify(text: str, seed: int | None = None) -> str:
    rng = random.Random(seed)
    try:
        uwuipy = importlib.import_module("uwuipy")  # optional
        return str(uwuipy.Uwuipy(seed=seed).uwuify(text))
    except Exception:  # noqa: BLE001  not installed, or an API we don't know: use ours
        return builtin(text, rng)
