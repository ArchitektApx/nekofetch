"""The image collection. Files that share a name are one image in several formats
(neko-typing.gif + neko-typing.png), so each renderer can take the one it shows best."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch import __version__
from nekofetch.paths import read_text, write_text

if TYPE_CHECKING:
    from collections.abc import Iterator

    from nekofetch.config import ImageConfig
    from nekofetch.paths import Paths

FORMATS = ("gif", "png", "jpg", "jpeg", "webp")


@dataclass(frozen=True)
class Image:
    name: str
    files: dict[str, Path]  # format -> file

    @classmethod
    def from_file(cls, path: Path) -> Image:
        return cls(path.stem, {path.suffix[1:].lower(): path})

    def best(self, formats: tuple[str, ...] | None) -> Path | None:
        """The file in the first of `formats` we have; any file when formats is None."""
        if formats is None:
            formats = FORMATS
        return next((self.files[f] for f in formats if f in self.files), None)

    @property
    def key(self) -> str:
        return str(next(iter(self.files.values())).with_suffix(""))


def scan(folder: Path) -> list[Image]:
    groups: dict[Path, dict[str, Path]] = {}
    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return []
    for p in entries:
        ext = p.suffix[1:].lower()
        if ext in FORMATS and not p.name.startswith(".") and p.is_file():
            groups.setdefault(p.with_suffix(""), {})[ext] = p
    return [Image(stem.name, files) for stem, files in groups.items()]


def image_folder(conf: ImageConfig, paths: Paths) -> Path:
    """`folder` from the config; relative paths are relative to ~/.config/nekofetch."""
    return paths.config / Path(conf.folder).expanduser() if conf.folder else paths.config / "images"


def collection(conf: ImageConfig, paths: Paths) -> list[Image]:
    mine = scan(image_folder(conf, paths))
    bundled = scan(paths.data / "images")
    if conf.defaults == "never":
        return mine
    if conf.defaults == "always":
        return mine + bundled
    return mine or bundled


def pick(images: list[Image], order: str, state: Path) -> Image | None:
    if not images:
        return None
    if order != "sorted":
        return random.choice(images)
    keys = [i.key for i in images]
    last = read_text(state).strip()
    nxt = images[(keys.index(last) + 1) % len(images)] if last in keys else images[0]
    write_text(state, nxt.key)
    return nxt


# --- growing the collection -----------------------------------------------------

CONTENT_TYPES = {"image/gif": "gif", "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def unique(path: Path) -> Path:
    n, candidate = 1, path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return candidate


def add_file(src: Path, folder: Path) -> Path:
    if not src.is_file() or src.suffix[1:].lower() not in FORMATS:
        raise ValueError(f"{src}: not an image nekofetch knows (gif, png, jpg, webp)")
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique(folder / src.name)
    import shutil  # only `nekofetch add` needs it

    shutil.copy2(src, dest)
    return dest


def download(url: str, timeout: float = 30) -> tuple[bytes, str]:
    import urllib.request  # slow to import, and only needed here
    from urllib.parse import urlparse

    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"{url}: only http(s) URLs are supported")
    req = urllib.request.Request(url, headers={"User-Agent": f"nekofetch/{__version__}"})  # noqa: S310  scheme checked above
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310  scheme checked above
        return r.read(), r.headers.get("Content-Type", "").split(";")[0].strip()


def add_url(url: str, folder: Path) -> Path:
    from urllib.parse import unquote, urlparse

    data, ctype = download(url)
    name = Path(unquote(urlparse(url).path)).name or "neko"
    if Path(name).suffix[1:].lower() not in FORMATS:
        ext = CONTENT_TYPES.get(ctype)
        if not ext:
            raise ValueError(f"{url}: not an image ({ctype or 'unknown type'})")
        name = f"{name}.{ext}"
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique(folder / name)
    dest.write_bytes(data)
    return dest


def fetch_nekos(count: int, folder: Path) -> Iterator[tuple[Path, str]]:
    """Random nekos from nekos.best, yielded as (file, artist) as each one lands, so a
    failure halfway still reports the ones already saved. Credits go to CREDITS.txt."""
    import json  # only `nekofetch fetch` needs it

    data, _ = download(f"https://nekos.best/api/v2/neko?amount={max(1, min(count, 20))}", timeout=20)
    for item in json.loads(data)["results"]:
        dest = add_url(item["url"], folder)
        dest = dest.rename(unique(dest.with_name(f"nekos-best-{dest.name}")))
        artist = item.get("artist_name") or "unknown artist"
        with (folder / "CREDITS.txt").open("a", encoding="utf-8") as f:
            f.write(f"{dest.name}  by {artist}  {item.get('source_url', '')}\n")
        yield dest, artist
