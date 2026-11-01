"""Which terminal are we in? A table of known terminals, checked in order.

Each entry says how to recognise the terminal, where its version comes from and
which renderers (see renderers.py) it handles best. Adding a terminal is adding
an entry. Detection looks through tmux, since most terminals leave their own
variables in the environment tmux inherits.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch.style import GREY, RESET
from nekofetch.system import Env, run

if TYPE_CHECKING:
    from collections.abc import Callable

KONSOLE_VERSION_LEN = 6  # AABBCC, as in 240802


def term_program_version(env: Env) -> str:
    # inside tmux, TERM_PROGRAM_VERSION is tmux's own version
    return "" if env.in_tmux else env.get("TERM_PROGRAM_VERSION")


def ghostty_version(env: Env) -> str:
    if version := term_program_version(env):
        return version
    if bin_dir := env.get("GHOSTTY_BIN_DIR"):
        binary = str(Path(bin_dir) / "ghostty")
        out = env.remember(f"version {binary}", lambda: run(binary, "--version"), stamp=env.stamp(binary)).split()
        return out[1] if len(out) > 1 and out[0] == "Ghostty" else ""
    return ""


def kitty_version(env: Env) -> str:
    kitten = env.kitten()
    if not kitten:
        return ""
    out = env.remember(f"version {kitten}", lambda: run(kitten, "--version"), stamp=env.stamp(kitten)).split()
    return out[1] if len(out) > 1 else ""


def konsole_version(env: Env) -> str:
    v = env.get("KONSOLE_VERSION")  # 240802 means 24.08.2
    return f"{int(v[:2])}.{v[2:4]}.{int(v[4:])}" if len(v) == KONSOLE_VERSION_LEN and v.isdigit() else v


def no_version(_env: Env) -> str:
    return ""


@dataclass(frozen=True)
class Terminal:
    name: str
    matches: Callable[[Env], bool]
    renderers: tuple[str, ...] = ()
    version: Callable[[Env], str] = term_program_version


def prog(*names: str) -> Callable[[Env], bool]:
    return lambda env: env.get("TERM_PROGRAM") in names


def has(*keys: str) -> Callable[[Env], bool]:
    return lambda env: any(env.get(k) for k in keys)


def term(*prefixes: str) -> Callable[[Env], bool]:
    return lambda env: env.get("TERM").startswith(prefixes)


def any_of(*checks: Callable[[Env], bool]) -> Callable[[Env], bool]:
    return lambda env: any(c(env) for c in checks)


KITTY_GRAPHICS = ("kitty", "kitty-direct")

TERMINALS = (
    Terminal(
        "Ghostty",
        any_of(prog("ghostty"), has("GHOSTTY_RESOURCES_DIR", "GHOSTTY_BIN_DIR"), term("xterm-ghostty")),
        KITTY_GRAPHICS,
        ghostty_version,
    ),
    Terminal("kitty", any_of(has("KITTY_WINDOW_ID"), term("xterm-kitty")), KITTY_GRAPHICS, kitty_version),
    Terminal("WezTerm", any_of(prog("WezTerm"), has("WEZTERM_EXECUTABLE")), ("iterm",)),
    Terminal(
        "iTerm2",
        any_of(prog("iTerm.app"), lambda env: env.get("LC_TERMINAL") == "iTerm2"),
        ("iterm",),
        lambda env: term_program_version(env) or env.get("LC_TERMINAL_VERSION"),
    ),
    Terminal("Konsole", has("KONSOLE_VERSION"), ("sixel",), konsole_version),
    Terminal("foot", term("foot"), ("sixel",), no_version),
    Terminal("Windows Terminal", has("WT_SESSION"), ("sixel",), no_version),
    Terminal(
        "Alacritty", any_of(has("ALACRITTY_WINDOW_ID", "ALACRITTY_SOCKET"), term("alacritty")), version=no_version
    ),
    Terminal("VS Code", prog("vscode")),
    Terminal("Terminal.app", prog("Apple_Terminal")),
    Terminal("JetBrains", lambda env: env.get("TERMINAL_EMULATOR") == "JetBrains-JediTerm", version=no_version),
    # VTE can do sixel, but most distros build it without; chafa is the safe bet
    Terminal("GNOME Terminal", has("GNOME_TERMINAL_SCREEN"), version=no_version),
    Terminal("VTE", has("VTE_VERSION"), version=no_version),
)


def unknown(env: Env) -> Terminal:
    """Name an unknown terminal after whatever it tells us about itself."""
    name = env.get("TERM_PROGRAM")
    if not name or name == "tmux":
        name = env.get("TERM").split("-")[0]
    return Terminal(name or "unknown", lambda _env: True)


def detect(env: Env) -> Terminal:
    return next((t for t in TERMINALS if t.matches(env)), None) or unknown(env)


def describe(env: Env) -> str:
    """The Terminal row: name, version, and the multiplexer in between."""
    t = detect(env)
    out = " ".join(p for p in (t.name, t.version(env)) if p)
    if env.in_tmux:
        version = env.get("TERM_PROGRAM_VERSION") if env.get("TERM_PROGRAM") == "tmux" else ""
        version = version or run("tmux", "-V").replace("tmux", "").strip()
        out += f" {GREY}+{RESET} tmux {version}".rstrip()
    elif env.get("STY"):
        out += f" {GREY}+{RESET} screen"
    return out
