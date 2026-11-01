"""The one line nekofetch adds to your shell config, and taking it out again.

Shell configs are precious: they're read and written as bytes, in place (so
permissions, symlinks and hard links survive), and a file we can't read is
never treated as empty.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch.paths import xdg

if TYPE_CHECKING:
    from collections.abc import Callable

    from nekofetch.system import Env

MARK = "# added by nekofetch setup"


@dataclass(frozen=True)
class Shell:
    name: str
    rc: Callable[[Env], Path]
    command: str
    # lines a new rc file needs so it doesn't change how the shell starts up
    preamble: Callable[[Env], list[str]] = lambda _env: []

    def line(self) -> str:
        return f"{self.command} {MARK}"


def _bash_rc(env: Env) -> Path:
    # macOS terminals start login shells, which read .bash_profile instead of .bashrc
    return env.home / (".bash_profile" if sys.platform == "darwin" else ".bashrc")


def _bash_preamble(env: Env) -> list[str]:
    # bash reads only the first of .bash_profile, .bash_login and .profile, so a new
    # .bash_profile would hide the other two; keep loading the one that was in use
    if sys.platform == "darwin":
        for name in (".bash_login", ".profile"):
            if (env.home / name).exists():
                return [f"[ -f ~/{name} ] && . ~/{name} {MARK}"]
    return []


SHELLS = {
    "zsh": Shell(
        "zsh",
        lambda env: Path(env.get("ZDOTDIR") or env.home) / ".zshrc",
        "[[ -o interactive ]] && command -v nekofetch >/dev/null && nekofetch",
    ),
    "bash": Shell("bash", _bash_rc, "[[ $- == *i* ]] && command -v nekofetch >/dev/null && nekofetch", _bash_preamble),
    "fish": Shell(
        "fish",
        lambda env: xdg(env.vars, "XDG_CONFIG_HOME") / "fish/config.fish",
        "status is-interactive; and type -q nekofetch; and nekofetch",
    ),
}


def current(env: Env) -> Shell | None:
    return SHELLS.get(Path(env.get("SHELL")).name)


def _read(path: Path) -> bytes | None:
    """The file's bytes; None when it doesn't exist. Other errors propagate."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def has_hook(path: Path) -> bool:
    try:
        return MARK.encode() in (_read(path) or b"")
    except OSError:
        return False


def add_hook(shell: Shell, env: Env) -> Path:
    """Appends our line in place. Raises OSError when the file can't be read or written."""
    path = shell.rc(env)
    text = _read(path)
    if text is not None and MARK.encode() in text:
        return path
    lines = shell.preamble(env) if text is None else []
    lines.append(shell.line())
    lead = (b"" if text.endswith(b"\n") else b"\n") + b"\n" if text else b""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(lead + "\n".join(lines).encode() + b"\n")
    return path


def remove_hooks(env: Env) -> list[Path]:
    """Takes our lines out of every shell config that has them. Nothing else is touched."""
    removed: list[Path] = []
    for path in dict.fromkeys(s.rc(env) for s in SHELLS.values()):
        try:
            text = _read(path)
        except OSError:
            continue
        if not text or MARK.encode() not in text:
            continue
        kept: list[bytes] = []
        for line in text.splitlines(keepends=True):
            if MARK.encode() not in line:
                kept.append(line)
            elif kept and kept[-1].strip() == b"":
                kept.pop()  # the blank line add_hook put in front of it
        if not b"".join(kept).strip():
            path.unlink()  # nothing but our lines: we created it
        else:
            with path.open("r+b") as f:  # in place, like add_hook
                f.write(b"".join(kept))
                f.truncate()
        removed.append(path)
    return removed
