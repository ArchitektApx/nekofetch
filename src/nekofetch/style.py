"""Colors (Dracula), shared by every row nekofetch prints."""

import os
import re
import sys
from typing import TextIO


def rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


RESET = "\033[0m"
GREY = rgb(98, 114, 164)
PINK = rgb(255, 121, 198)
PURPLE = rgb(189, 147, 249)
CYAN = rgb(139, 233, 253)
GREEN = rgb(80, 250, 123)
YELLOW = rgb(241, 250, 140)
RED = rgb(255, 85, 85)
DOT = f" {GREY}·{RESET} "

CAT = "ᓚ₍ ^. .^₎"

_ANSI = re.compile(r"\033\[[\d;]*m")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def echo(*parts: object, sep: str = " ", file: TextIO | None = None) -> None:
    """print(), minus the colors when they'd end up in a file, a pipe or under NO_COLOR."""
    file = file or sys.stdout
    text = sep.join(str(p) for p in parts)
    if os.environ.get("NO_COLOR") or not getattr(file, "isatty", lambda: False)():
        text = strip_ansi(text)
    print(text, file=file)
