"""The environment nekofetch runs in, behind one object so tests can fake it."""

from __future__ import annotations

import contextlib
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch.paths import read_text, write_text, xdg

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


TMUX_MAX_AGE = 300  # seconds
REMEMBER_FIELDS = 4


def run(*cmd: str, timeout: float = 2) -> str:
    """stdout of a command, or "" when it is missing, fails to start or hangs."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def which(name: str) -> str | None:
    """shutil.which, without the 5 ms it takes to import shutil on every shell start."""
    for d in os.environ.get("PATH", os.defpath).split(os.pathsep):
        path = os.path.join(d or ".", name)  # noqa: PTH118  cheaper than pathlib here
        if os.path.isfile(path) and os.access(path, os.X_OK):  # noqa: PTH113
            return path
    return None


@dataclass(frozen=True)
class Env:
    vars: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    which: Callable[[str], str | None] = field(default_factory=lambda: which)

    def get(self, key: str, default: str = "") -> str:
        return self.vars.get(key, default)

    @property
    def in_tmux(self) -> bool:
        return "TMUX" in self.vars

    @property
    def remote(self) -> bool:
        return bool(self.get("SSH_CONNECTION") or self.get("SSH_TTY"))

    @property
    def home(self) -> Path:
        return Path(self.get("HOME") or Path.home())

    def tmux_passthrough(self, *, fresh: bool = False) -> bool:
        """Whether tmux lets image escape codes through to the terminal.
        Remembered per tmux server for a few minutes, since asking tmux costs ~5 ms."""
        value = self.remember(
            f"tmux-passthrough {self.get('TMUX')}",
            lambda: run("tmux", "show", "-gv", "allow-passthrough").strip(),
            max_age=0 if fresh else TMUX_MAX_AGE,
        )
        return value in ("on", "all")

    def remember(self, key: str, compute: Callable[[], str], *, stamp: str = "", max_age: float | None = None) -> str:
        """A small persistent cache for answers that cost a subprocess on every shell start.

        An entry is reused while its `stamp` (e.g. a binary's mtime) is unchanged and,
        with `max_age`, while it is younger than that many seconds."""
        path = xdg(self.vars, "XDG_CACHE_HOME") / "nekofetch" / "remember"
        now = time.time()
        entries: dict[str, tuple[str, float, str]] = {}
        for line in read_text(path).splitlines():
            parts = line.split("\t")
            if len(parts) == REMEMBER_FIELDS:
                with contextlib.suppress(ValueError):
                    entries[parts[0]] = (parts[1], float(parts[2]), parts[3])
        hit = entries.get(key)
        if hit and hit[0] == stamp and (max_age is None or now - hit[1] < max_age):
            return hit[2]
        value = " ".join(compute().split())  # one line, no tabs: the file format needs it
        entries[key] = (stamp, now, value)
        write_text(path, "".join(f"{k}\t{s}\t{t}\t{v}\n" for k, (s, t, v) in entries.items()))
        return value

    def stamp(self, path: str | Path) -> str:
        """Changes whenever the file does (or appears or disappears)."""
        try:
            return str(Path(path).stat().st_mtime_ns)
        except OSError:
            return ""

    def kitten(self) -> str | None:
        """kitty's helper binary; also installed alongside kitty.app on macOS."""
        for p in (
            self.which("kitten"),
            "/Applications/kitty.app/Contents/MacOS/kitten",
            str(self.home / ".local/kitty.app/bin/kitten"),
        ):
            if p and Path(p).exists():
                return p
        return None
