"""Puts it together: config, image, logo and rows, then hands over to fastfetch."""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from nekofetch import images, renderers, terminals
from nekofetch.config import load as load_config
from nekofetch.paths import Paths, read_text
from nekofetch.says import SaysFile, say
from nekofetch.says.conditions import Facts
from nekofetch.sources import machine, packages
from nekofetch.style import strip_ansi
from nekofetch.system import Env
from nekofetch.weather import Weather

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from nekofetch.config import Config


DEFAULT_COLUMNS = 80
ROWS = ("NEKO_PACKAGES", "NEKO_TOOLING", "NEKO_TERMINAL", "NEKO_LOCALE", "NEKO_WEATHER", "NEKO_SAYS")


def terminal_columns(env: Env) -> int:
    """Terminal width, without importing shutil (slow) for shutil.get_terminal_size."""
    try:
        return os.get_terminal_size(sys.stdout.fileno()).columns
    except (OSError, ValueError):
        cols = env.get("COLUMNS")
        return int(cols) if cols.isdigit() else DEFAULT_COLUMNS


@dataclass(frozen=True)
class App:
    paths: Paths
    config: Config
    env: Env

    @classmethod
    def load(cls, env: Env | None = None, warn: bool = True) -> App:
        env = env or Env()
        paths = Paths.from_env(env.vars)
        config, warnings = load_config(paths.config_file)
        if warn:
            for w in warnings:
                print(f"nekofetch: {w}", file=sys.stderr)
        return cls(paths, config, env)

    # --- parts (built once per run) -----------------------------------------
    @cached_property
    def weather(self) -> Weather:
        return Weather(self.config.weather, self.paths.cache)

    @cached_property
    def says_file(self) -> SaysFile:
        return SaysFile.load(self.paths.user_or_default("says.toml"))

    @cached_property
    def collection(self) -> list[images.Image]:
        return images.collection(self.config.image, self.paths)

    def render_context(self) -> renderers.Context:
        return renderers.Context(
            self.env,
            self.paths.cache,
            self.config.image.width,
            self.config.image.height,
            self.paths.user_or_default("neko.txt"),
            self.paths.data,
            terminal_columns(self.env),
        )

    def logo(self, image: images.Image | None = None, protocol: str | None = None) -> renderers.Logo:
        if image is None:
            image = images.pick(self.collection, self.config.image.order, self.paths.cache / "last-image")
        return renderers.choose(
            terminals.detect(self.env), image, self.render_context(), protocol or self.config.image.protocol
        )

    def says(self, uwu: bool | None = None, record: bool = True) -> str:
        facts = Facts(
            self.paths.cache, weather=self.weather.cached()[0], user=self.env.get("USER", "you"), record=record
        )
        return say(self.config.says, self.says_file, facts, uwu=uwu)

    def rows(self, uwu: bool | None = None, wanted: Collection[str] = ROWS) -> dict[str, str]:
        """The $NEKO_* variables layout.jsonc reads, only those in `wanted`. Empty hides a row."""
        builders: dict[str, Callable[[], str]] = {
            "NEKO_PACKAGES": lambda: packages.row("system", self.env),
            "NEKO_TOOLING": lambda: packages.row("tooling", self.env),
            "NEKO_TERMINAL": lambda: terminals.describe(self.env),
            "NEKO_LOCALE": lambda: machine.locale_row(self.env),
            "NEKO_WEATHER": self.weather.line,
        }
        # The cat's line mostly waits on subprocesses (pmset, git), so it runs in a
        # thread while the other rows are gathered: ~10 ms less on every shell start.
        says: list[str] = []
        thread = threading.Thread(target=lambda: says.append(self.says(uwu)))
        with_says = "NEKO_SAYS" in wanted
        if with_says:
            thread.start()
        rows = {name: build() for name, build in builders.items() if name in wanted}
        if with_says:
            thread.join()
            rows["NEKO_SAYS"] = says[0] if says else ""
        return rows

    # --- run -----------------------------------------------------------------
    def plain(self, fastfetch_args: list[str]) -> bool:
        """No colors for NO_COLOR, `--pipe`, dumb terminals and output that isn't a terminal."""
        if self.env.get("NO_COLOR") or self.env.get("TERM") == "dumb":
            return True
        if "--pipe" in fastfetch_args:
            i = fastfetch_args.index("--pipe")
            return fastfetch_args[i + 1 : i + 2] != ["false"]
        return not sys.stdout.isatty()

    def run(
        self,
        image: Path | None = None,
        protocol: str | None = None,
        uwu: bool | None = None,
        fastfetch_args: list[str] | None = None,
    ) -> int:
        fastfetch_args = fastfetch_args or []
        fastfetch = self.env.which("fastfetch")
        if not fastfetch:
            print(
                "nekofetch: fastfetch isn't installed: https://github.com/fastfetch-cli/fastfetch#installation",
                file=sys.stderr,
            )
            return 1
        logo = self.logo(images.Image.from_file(image) if image else None, protocol)
        layout = self.paths.user_or_default("layout.jsonc")
        text = read_text(layout)
        rows = self.rows(uwu, [name for name in ROWS if name in text])  # skip rows the layout doesn't show
        if self.plain(fastfetch_args):
            rows = {k: strip_ansi(v) for k, v in rows.items()}
        env = {**self.env.vars, **rows, **logo.env}
        argv = [fastfetch, "--config", str(layout), *logo.args, *fastfetch_args]
        os.execve(fastfetch, argv, env)  # noqa: S606  replaces this process; fixed argv, no shell
        return 0  # not reached
