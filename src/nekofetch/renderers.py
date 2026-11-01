"""Ways to draw the logo, and the fallback chain that picks one.

Every renderer answers three questions:
  installed(ctx)  are the tools it needs there?
  fits(ctx)       does it work here (tmux, SSH)? Skipped when the user forces it.
  render(...)     the fastfetch arguments, or None if this image didn't work out
and lists the image `formats` it can show, best first (None: anything).

choose() walks the terminal's preferred renderers, then the fallbacks: block
art of the bundled cats, chafa for other images, and the braille cat, which
always works. The first one that can show the image wins.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeVar

from nekofetch.paths import DATA, read_text, write_text

if TYPE_CHECKING:
    from nekofetch.images import Image
    from nekofetch.system import Env
    from nekofetch.terminals import Terminal


@dataclass(frozen=True)
class Logo:
    renderer: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class Context:
    env: Env
    cache: Path
    width: int
    height: int
    ascii_art: Path
    bundled: Path = DATA  # the bundled images and their pre-rendered block art
    columns: int = 80  # terminal width

    @property
    def size(self) -> list[str]:
        return ["--logo-width", str(self.width), "--logo-height", str(self.height)]


class Renderer(ABC):
    name: ClassVar[str]
    formats: ClassVar[tuple[str, ...] | None] = None
    needs_image: ClassVar[bool] = True

    def installed(self, ctx: Context) -> bool:
        del ctx  # part of the interface; most renderers need nothing
        return True

    def fits(self, ctx: Context) -> bool:
        del ctx
        return True

    @abstractmethod
    def render(self, image: Path | None, ctx: Context) -> Logo | None: ...


R = TypeVar("R", bound=Renderer)

RENDERERS: dict[str, Renderer] = {}


def renderer(cls: type[R]) -> type[R]:
    """Registers a renderer under its name; that name is also a valid `protocol`."""
    RENDERERS[cls.name] = cls()
    return cls


@renderer
class KittyIcat(Renderer):
    """kitty and Ghostty through `kitten icat`: animated GIFs, works in tmux and over SSH."""

    name = "kitty"
    formats = ("gif", "png", "webp", "jpg", "jpeg")

    def installed(self, ctx: Context) -> bool:
        return ctx.env.kitten() is not None

    def fits(self, ctx: Context) -> bool:
        return not ctx.env.in_tmux or ctx.env.tmux_passthrough()

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        kitten = ctx.env.kitten()
        if kitten is None:
            return None
        path = str(Path(kitten).parent)
        if not ctx.env.remote:
            # icat streams images through the pty by default, which takes seconds
            # for a big GIF in tmux. Reading the file directly is ~30x faster, so
            # a shim named `kitten` adds --transfer-mode=file for fastfetch.
            shim = ctx.cache / "shim" / "kitten"
            k = shlex.quote(kitten)
            body = (
                f'#!/bin/sh\nif [ "$1" = icat ]; then shift; exec {k} icat '
                f'--transfer-mode=file "$@"; fi\nexec {k} "$@"\n'
            )
            try:
                if read_text(shim) != body and write_text(shim, body):
                    shim.chmod(0o755)
                if os.access(shim, os.X_OK):
                    path = str(shim.parent)
            except OSError:
                pass
        env_path = path + os.pathsep + ctx.env.get("PATH")
        return Logo(self.name, ["--logo-type", "kitty-icat", "--logo", str(image), *ctx.size], {"PATH": env_path})


@renderer
class KittyDirect(Renderer):
    """The kitty protocol without `kitten`: the terminal reads a PNG file itself."""

    name = "kitty-direct"
    formats = ("png",)

    def fits(self, ctx: Context) -> bool:
        return not (ctx.env.in_tmux or ctx.env.remote)

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        return Logo(self.name, ["--logo-type", "kitty-direct", "--logo", str(image), *ctx.size])


@renderer
class ITerm(Renderer):
    """iTerm2's inline images, also spoken by WezTerm. Animates GIFs."""

    name = "iterm"

    def fits(self, ctx: Context) -> bool:
        return not ctx.env.in_tmux

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        return Logo(self.name, ["--logo-type", "iterm", "--logo", str(image), *ctx.size])


@renderer
class Chafa(Renderer):
    """Colored unicode blocks drawn by chafa. Works in any terminal."""

    name = "chafa"
    chafa_format = "symbols"

    def installed(self, ctx: Context) -> bool:
        return ctx.env.which("chafa") is not None

    KEEP = 50  # cached renders

    def rendered(self, image: Path, ctx: Context) -> Path | None:
        """chafa's output for this image and size, cached since chafa takes a moment."""
        colors = "full" if ctx.env.get("COLORTERM") in ("truecolor", "24bit") else "256"
        size = f"{ctx.width}x{ctx.height}"
        try:
            st = image.stat()
            key = f"{image.name}-{int(st.st_mtime)}-{st.st_size}-{self.chafa_format}-{colors}-{size}"
            out = ctx.cache / "render" / (re.sub(r"[^\w.-]", "_", key) + ".txt")
            if out.exists():
                return out
            res = subprocess.run(
                [
                    "chafa",
                    "--format",
                    self.chafa_format,
                    "--size",
                    size,
                    "--animate",
                    "off",
                    "--colors",
                    colors,
                    "--polite",
                    "on",
                    str(image),
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if res.returncode or not res.stdout:
                return None
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(f"{out.name}.{os.getpid()}.tmp")
            tmp.write_bytes(res.stdout)
            tmp.replace(out)  # a shell starting right now never sees half a cat
            self._prune(out.parent)
        except (OSError, subprocess.SubprocessError):
            return None
        return out

    def _prune(self, folder: Path) -> None:
        renders = sorted(folder.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in renders[self.KEEP :]:
            old.unlink(missing_ok=True)

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        if image is None:
            return None
        out = self.rendered(image, ctx)
        return Logo(self.name, ["--logo-type", "file-raw", "--logo", str(out)]) if out else None


@renderer
class Sixel(Chafa):
    """Sixel graphics, encoded by chafa, for foot, Konsole, Windows Terminal and friends."""

    name = "sixel"
    chafa_format = "sixels"

    def fits(self, ctx: Context) -> bool:
        return not ctx.env.in_tmux

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        if image is None:
            return None
        out = self.rendered(image, ctx)
        return Logo(self.name, ["--logo-type", "raw", "--logo", str(out), *ctx.size]) if out else None


@renderer
class Blocks(Renderer):
    """The bundled cats as pre-rendered half-block art (tools/draw.py makes them).
    Pixel exact in any truecolor terminal, over SSH too; the large one when there's room."""

    name = "blocks"
    LARGE_FROM = 150  # columns: 64 for the cat, the rest for the info

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        if image is None or image.parent != ctx.bundled / "images":
            return None  # only the bundled cats come pre-rendered
        size = "large" if ctx.columns >= self.LARGE_FROM else "small"
        art = ctx.bundled / "blocks" / f"{image.stem}-{size}.ans"
        if not art.exists():
            return None
        # the large cat is taller than the info; print all of her
        return Logo(self.name, ["--logo-type", "file-raw", "--logo", str(art), "--logo-print-remaining", "true"])


@renderer
class Ascii(Renderer):
    """The braille cat (neko.txt, drawn by tools/draw.py). Text only, so the chain always ends here."""

    name = "ascii"
    needs_image = False
    COLORS = ("38;2;225;215;255",)  # $1 in neko.txt

    def render(self, image: Path | None, ctx: Context) -> Logo:
        del image
        args = ["--logo-type", "file", "--logo", str(ctx.ascii_art), "--logo-print-remaining", "true"]
        for i, color in enumerate(self.COLORS, 1):
            args += [f"--logo-color-{i}", color]
        return Logo(self.name, args)


@renderer
class NoLogo(Renderer):
    name = "none"
    needs_image = False

    def render(self, image: Path | None, ctx: Context) -> Logo | None:
        del image, ctx
        return Logo(self.name, ["--logo-type", "none"])


FALLBACK = ("blocks", "chafa", "ascii")


def chain(terminal: Terminal, forced: str | None) -> list[tuple[Renderer, bool]]:
    """(renderer, forced) pairs in the order they get a try."""
    if forced and forced != "auto":
        if forced not in RENDERERS:
            raise ValueError(f"unknown protocol {forced!r}; try one of: {', '.join(RENDERERS)}")
        first = [(RENDERERS[forced], True)]
        return [*first, *((RENDERERS[n], False) for n in FALLBACK if n != forced)]
    names = list(dict.fromkeys(terminal.renderers + FALLBACK))
    return [(RENDERERS[n], False) for n in names]


def choose(terminal: Terminal, image: Image | None, ctx: Context, forced: str | None = None) -> Logo:
    for renderer, is_forced in chain(terminal, forced):
        if not renderer.installed(ctx) or not (is_forced or renderer.fits(ctx)):
            continue
        path: Path | None = None
        if renderer.needs_image:
            path = image.best(renderer.formats) if image else None
            if path is None:
                continue
        logo = renderer.render(path, ctx)
        if logo:
            return logo
    return Ascii().render(None, ctx)
