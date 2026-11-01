"""`nekofetch doctor`: what nekofetch found, and what would make it better."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nekofetch import __version__, images, shell, terminals, timer
from nekofetch.style import CAT, GREEN, GREY, PINK, RED, RESET, YELLOW, echo
from nekofetch.system import run

if TYPE_CHECKING:
    from nekofetch.app import App

OK, MEH, BAD = f"{GREEN}✓{RESET}", f"{YELLOW}!{RESET}", f"{RED}✗{RESET}"


@dataclass
class Check:
    mark: str
    label: str
    text: str


def checks(app: App) -> list[Check]:
    env = app.env
    out: list[Check] = []
    out.append(Check(OK, "python", sys.version.split()[0]))

    ff = env.which("fastfetch")
    out.append(
        Check(OK, "fastfetch", run(ff, "--version").strip())
        if ff
        else Check(BAD, "fastfetch", "missing: https://github.com/fastfetch-cli/fastfetch#installation")
    )

    term = terminals.detect(env)
    out.append(Check(OK, "terminal", terminals.describe(env)))
    if env.in_tmux:
        out.append(
            Check(OK, "tmux", "allow-passthrough on")
            if env.tmux_passthrough(fresh=True)
            else Check(MEH, "tmux", "allow-passthrough off: no images (set -g allow-passthrough on)")
        )
    if "kitty" in term.renderers:
        kitten = env.kitten()
        out.append(
            Check(OK, "kitten", kitten)
            if kitten
            else Check(MEH, "kitten", "missing: no animation, PNGs only (it comes with kitty)")
        )
    chafa = env.which("chafa")
    out.append(
        Check(OK, "chafa", chafa)
        if chafa
        else Check(MEH, "chafa", "missing: no pictures in terminals without image support")
    )

    folder = images.image_folder(app.config.image, app.paths)
    every = app.collection
    mine = images.scan(folder)
    out.append(Check(OK, "images", f"{len(every)} in rotation, {len(mine)} yours ({folder})"))
    logo = app.logo(every[0] if every else None)
    out.append(Check(OK if logo.renderer != "ascii" or not every else MEH, "protocol", logo.renderer))

    if app.config.weather.enabled:
        line, age = app.weather.cached()
        out.append(
            Check(OK, "weather", f"{line}  {GREY}{int((age or 0) // 60)} min old{RESET}")
            if line
            else Check(MEH, "weather", "nothing cached yet (nekofetch weather --refresh)")
        )
    else:
        out.append(Check(OK, "weather", "off"))

    scheduler = timer.for_platform(env)
    if scheduler and scheduler.installed():
        out.append(Check(OK, "timer", f"weather refreshes on a schedule ({scheduler.files[0]})"))

    sh = shell.current(env)
    if sh:
        hooked = shell.has_hook(sh.rc(env))
        out.append(
            Check(
                OK if hooked else MEH,
                "shell",
                f"{sh.name}, " + ("greets you on start" if hooked else "not on startup (nekofetch setup)"),
            )
        )
    return out


def main(app: App) -> int:
    echo(f"{PINK}{CAT}{RESET} nekofetch {__version__} {GREY}({app.paths.data.parent}){RESET}\n")
    for c in checks(app):
        echo(f" {c.mark} {c.label:<10} {c.text}")
    echo(f"\n{GREY}boxes instead of icons? you need a Nerd Font: https://www.nerdfonts.com{RESET}")
    return 0
