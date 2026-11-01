"""`nekofetch setup`: the config folder, the shell line and the optional weather timer,
and `setup --undo` to take the last two out again."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from nekofetch import images, shell, timer
from nekofetch.style import GREY, PINK, RESET, echo

if TYPE_CHECKING:
    import argparse

    from nekofetch.app import App


def main(app: App, args: argparse.Namespace) -> int:
    if args.undo:
        _undo(app)
        return 0
    _setup_files(app)
    if not args.no_shell:
        _setup_shell(app, args)
    if args.weather_timer:
        _setup_timer(app)
    return 0


def _setup_files(app: App) -> None:
    conf = app.paths.config_file
    if not conf.exists():
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text((app.paths.data / "config.toml").read_text(encoding="utf-8"), encoding="utf-8")
        echo(f"{PINK}+{RESET} {conf}")
    folder = images.image_folder(app.config.image, app.paths)
    folder.mkdir(parents=True, exist_ok=True)
    echo(f"{PINK}+{RESET} {folder}  {GREY}(your cats go here){RESET}")


def _setup_shell(app: App, args: argparse.Namespace) -> None:
    sh = shell.SHELLS.get(args.shell) if args.shell else shell.current(app.env)
    if not sh:
        echo(f"{GREY}unknown shell; to greet you on start, add `nekofetch` to your shell config{RESET}")
        return
    rc = sh.rc(app.env)
    if shell.has_hook(rc):
        echo(f"{GREY}already greets you in {rc}{RESET}")
    elif args.yes or _ask(f"show nekofetch in every new {sh.name} (adds one line to {rc})?"):
        echo(f"{PINK}+{RESET} {shell.add_hook(sh, app.env)}")
    elif not sys.stdin.isatty():
        echo(f"{GREY}not asking without a terminal; `nekofetch setup --yes` adds the shell line{RESET}")


def _setup_timer(app: App) -> None:
    minutes = app.config.weather.refresh
    scheduler = timer.for_platform(app.env)
    if scheduler is None:
        echo(f"no launchd or systemd here; add this to `crontab -e` instead:\n  {timer.cron_line(minutes)}")
        return
    for path in scheduler.install(minutes):
        echo(f"{PINK}+{RESET} {path}  {GREY}(weather every {minutes} min){RESET}")


def _undo(app: App) -> None:
    for path in shell.remove_hooks(app.env):
        echo(f"{PINK}-{RESET} removed the nekofetch line from {path}")
    scheduler = timer.for_platform(app.env)
    for path in scheduler.remove() if scheduler else []:
        echo(f"{PINK}-{RESET} {path}")
    echo(
        f"{GREY}your config stays in {app.paths.config}. to remove nekofetch itself:\n"
        f"  uv tool uninstall nekofetch   or   pipx uninstall nekofetch{RESET}"
    )


def _ask(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        return input(f"{PINK}?{RESET} {question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False
