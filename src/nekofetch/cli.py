"""Command line: `nekofetch [options] [-- fastfetch args]` and its subcommands."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch import __version__, images, shell
from nekofetch.app import App
from nekofetch.renderers import RENDERERS
from nekofetch.style import CAT, GREY, PINK, RESET, echo, strip_ansi

if TYPE_CHECKING:
    from nekofetch.weather import Weather

EPILOG = f"""\
examples:
  nekofetch                      the cat, the facts, the weather
  nekofetch -p ascii             no picture, just the braille cat
  nekofetch --uwu                you know what this does
  nekofetch -- --logo-position top
                                 anything after -- goes to fastfetch

{PINK}{CAT}{RESET} {GREY}because catgirls are cute ok?{RESET}"""


Handler = Callable[[App, argparse.Namespace], int]


class Parser(argparse.ArgumentParser):
    commands: frozenset[str] = frozenset()


def cmd_run(app: App, args: argparse.Namespace) -> int:
    if args.image and not args.image.is_file():
        echo(f"nekofetch: no such image: {args.image}", file=sys.stderr)
        return 2
    return app.run(args.image, args.protocol, args.uwu, args.fastfetch)


def cmd_add(app: App, args: argparse.Namespace) -> int:
    folder = images.image_folder(app.config.image, app.paths)
    failed = 0
    for src in args.sources:
        try:
            if src.startswith(("http://", "https://")):
                dest = images.add_url(src, folder)
            else:
                dest = images.add_file(Path(src).expanduser(), folder)
            echo(f"{PINK}+{RESET} {dest}")
        except (OSError, ValueError) as e:
            echo(f"nekofetch: {e}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def cmd_fetch(app: App, args: argparse.Namespace) -> int:
    folder = images.image_folder(app.config.image, app.paths)
    try:
        for dest, artist in images.fetch_nekos(args.count, folder):
            echo(f"{PINK}+{RESET} {dest} {GREY}by {artist}{RESET}")
    except (OSError, ValueError, KeyError) as e:
        echo(f"nekofetch: nekos.best: {e}", file=sys.stderr)
        return 1
    echo(f"{GREY}these belong to their artists (see CREDITS.txt), so keep them to your own terminal{RESET}")
    return 0


def cmd_list(app: App, _args: argparse.Namespace) -> int:
    every = app.collection
    for image in every:
        echo(f"{image.name:<24} {GREY}{', '.join(str(p) for p in image.files.values())}{RESET}")
    if not every:
        echo("no images, so the ASCII cat steps in. add some: nekofetch add FILE")
    return 0


def cmd_weather(app: App, args: argparse.Namespace) -> int:
    weather: Weather = app.weather
    if args.refresh:
        if not app.config.weather.enabled:
            # the timer keeps running after `enabled = false`; it shouldn't fetch
            if not args.quiet:
                echo("weather is off in config.toml ([weather] enabled = false)")
            return 0
        try:
            line = weather.refresh()
        except RuntimeError as e:
            if not args.quiet:
                echo(f"nekofetch: {e}", file=sys.stderr)
            return 1
        if not args.quiet:
            echo(line)
        return 0
    echo(weather.line())
    return 0


def cmd_says(app: App, args: argparse.Namespace) -> int:
    if args.check:
        says = app.says_file
        problems = says.problems()
        for p in problems:
            echo(p)
        n = len(says.all_lines())
        echo(f"{n} lines, {len(problems)} problems" if problems else f"{n} lines, all good")
        return 1 if problems else 0
    echo(app.says(args.uwu, record=False).strip())
    return 0


def cmd_setup(app: App, args: argparse.Namespace) -> int:
    from nekofetch import setup  # only this command needs shell and timer

    return setup.main(app, args)


def cmd_doctor(app: App, _args: argparse.Namespace) -> int:
    from nekofetch import doctor

    return doctor.main(app)


def cmd_config(app: App, _args: argparse.Namespace) -> int:
    p = app.paths
    rows = [
        ("config", p.config_file),
        ("layout", p.user_or_default("layout.jsonc")),
        ("says", p.user_or_default("says.toml")),
        ("ascii", p.user_or_default("neko.txt")),
        ("images", images.image_folder(app.config.image, p)),
        ("cache", p.cache),
        ("bundled", p.data),
    ]
    for name, path in rows:
        echo(f"{name:<8} {path}" + ("" if path.exists() else f" {GREY}(not there){RESET}"))
    return 0


def parser() -> Parser:
    p = Parser(
        prog="nekofetch",
        description="fastfetch, but with catgirls.",
        usage="nekofetch [options] [-- fastfetch options]\n       nekofetch COMMAND [--help]",
        epilog=EPILOG if sys.stdout.isatty() else strip_ansi(EPILOG),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-v", "--version", action="version", version=f"nekofetch {__version__}")
    p.add_argument("-i", "--image", type=Path, metavar="FILE", help="show this image instead of picking one")
    p.add_argument(
        "-p",
        "--protocol",
        choices=["auto", *RENDERERS],
        metavar="NAME",
        help=f"how to draw it: auto, {', '.join(RENDERERS)}",
    )
    uwu = p.add_mutually_exclusive_group()
    uwu.add_argument("--uwu", action="store_true", default=None, help="the cat speaks uwu")
    uwu.add_argument("--no-uwu", dest="uwu", action="store_false", help="even on April 1st")
    p.set_defaults(func=cmd_run, fastfetch=[])

    sub = p.add_subparsers(title="commands", metavar="COMMAND")

    def command(name: str, func: Handler, summary: str, description: str | None = None) -> Parser:
        c = sub.add_parser(name, help=summary, description=description or summary)
        c.set_defaults(func=func)
        return c

    c = command(
        "add",
        cmd_add,
        "add images to your collection",
        "Copy files or download URLs into your image folder. GIF, PNG, JPG and WebP.",
    )
    c.add_argument("sources", nargs="+", metavar="FILE|URL")

    c = command(
        "fetch",
        cmd_fetch,
        "download random nekos from nekos.best",
        "Download random nekos from nekos.best into your image folder. "
        "The artists are noted in CREDITS.txt next to the files.",
    )
    c.add_argument("count", nargs="?", type=int, default=1, help="how many, up to 20 (default: 1)")

    command("list", cmd_list, "show the images in the rotation")

    c = command(
        "weather",
        cmd_weather,
        "show the cached weather line",
        "Show the cached weather line. A stale one is refreshed in the background.",
    )
    c.add_argument("--refresh", action="store_true", help="fetch it now and wait for it")
    c.add_argument("--quiet", action="store_true", help=argparse.SUPPRESS)

    c = command("says", cmd_says, "what the cat says right now")
    c.add_argument("--check", action="store_true", help="lint says.toml: line length, placeholders, names")
    c.add_argument("--uwu", action="store_true", default=argparse.SUPPRESS, help="say it in uwu")

    c = command(
        "setup",
        cmd_setup,
        "create your config and greet you in every new shell",
        "Create ~/.config/nekofetch and offer to add one line to your shell config, "
        "so nekofetch greets you in every new shell.",
    )
    c.add_argument("--shell", choices=list(shell.SHELLS), help="default: from $SHELL")
    c.add_argument("-y", "--yes", action="store_true", help="don't ask")
    c.add_argument("--no-shell", action="store_true", help="leave your shell config alone")
    c.add_argument(
        "--weather-timer",
        action="store_true",
        help="also refresh the weather on a schedule (launchd/systemd), so it's fresh at shell start",
    )
    c.add_argument("--undo", action="store_true", help="remove the shell line and the weather timer again")

    command("doctor", cmd_doctor, "what nekofetch detected, and what's missing")
    command("config", cmd_config, "show every path nekofetch reads")
    p.commands = frozenset(sub.choices)
    return p


def split_passthrough(argv: list[str], commands: frozenset[str]) -> tuple[list[str], list[str]]:
    """`nekofetch [options] -- fastfetch args`: only the default command passes args on,
    so a `--` after a subcommand stays with it (`nekofetch add -- -odd-name.png`)."""
    if "--" not in argv:
        return argv, []
    i = argv.index("--")
    if any(a in commands for a in argv[:i]):
        return argv, []
    return argv[:i], argv[i + 1 :]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:  # every new shell lands here: skip building the whole parser (~6 ms)
        return guarded(lambda: App.load().run())
    p = parser()
    argv, fastfetch = split_passthrough(argv, p.commands)
    args = p.parse_args(argv)
    args.fastfetch = fastfetch
    if args.func is not cmd_run and (args.image or args.protocol):
        p.error("-i/--image and -p/--protocol only apply to plain `nekofetch`")
    return guarded(lambda: args.func(App.load(), args) or 0)


def guarded(command: Callable[[], int]) -> int:
    """Runs a command with one-line errors instead of tracebacks."""
    try:
        return command()
    except KeyboardInterrupt:
        return 130
    except OSError as e:  # unwritable config, full disk, ...: one line, not a traceback
        echo(f"nekofetch: {e}", file=sys.stderr)
        return 1
