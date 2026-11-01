"""Package counts per package manager, for the Packages and Tooling rows.

Each source counts its packages by reading files, never by running the package
manager, so the rows cost milliseconds. A source that isn't installed counts 0
and drops out of the row, so there is no "which OS is this" logic anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch.paths import read_text, xdg
from nekofetch.style import DOT, GREY, RESET

if TYPE_CHECKING:
    from collections.abc import Callable

    from nekofetch.system import Env


@dataclass(frozen=True)
class Source:
    name: str
    group: str  # "system" (Packages row) or "tooling" (Tooling row)
    count: Callable[[Env], int]


SOURCES: list[Source] = []


def source(name: str, group: str = "system") -> Callable[[Callable[[Env], int]], Callable[[Env], int]]:
    def register(fn: Callable[[Env], int]) -> Callable[[Env], int]:
        SOURCES.append(Source(name, group, fn))
        return fn

    return register


# --- helpers -------------------------------------------------------------------


def data_home(env: Env) -> Path:
    return xdg(env.vars, "XDG_DATA_HOME")


def entries(*dirs: str | Path, skip: tuple[str, ...] = ()) -> int:
    """Visible entries in the first directory that exists."""
    for d in dirs:
        try:
            return sum(1 for e in Path(d).iterdir() if not e.name.startswith(".") and e.name not in skip)
        except OSError:
            continue
    return 0


def node_modules(*dirs: str | Path) -> int:
    """Global node packages: @scope/pkg counts per package; npm itself is skipped."""
    for d in dirs:
        try:
            names = [e.name for e in Path(d).iterdir()]
        except OSError:
            continue
        return sum(
            entries(Path(d) / n) if n.startswith("@") else 1
            for n in names
            if not n.startswith(".") and n not in ("npm", "corepack")
        )
    return 0


def json_len(path: Path, *keys: str) -> int:
    try:
        import json  # only for nix and cargo, and only when their files exist

        data = json.loads(read_text(path) or "null")
        for k in keys:
            data = data[k]
        return len(data)
    except (ValueError, KeyError, TypeError):
        return 0


def brew_prefix(env: Env) -> str:
    return env.get("HOMEBREW_PREFIX") or next(
        (p for p in ("/opt/homebrew", "/usr/local", "/home/linuxbrew/.linuxbrew") if (Path(p) / "Cellar").is_dir()),
        "",
    )


# --- system package managers -----------------------------------------------------


@source("dpkg")
def dpkg(_env: Env) -> int:
    return len(list(Path("/var/lib/dpkg/info").glob("*.list")))


@source("pacman")
def pacman(_env: Env) -> int:
    return entries("/var/lib/pacman/local", skip=("ALPM_DB_VERSION",))


@source("rpm")
def rpm(_env: Env) -> int:
    db = next(
        (p for p in ("/var/lib/rpm/rpmdb.sqlite", "/usr/lib/sysimage/rpm/rpmdb.sqlite") if Path(p).exists()), None
    )
    if not db:
        return 0
    try:
        import sqlite3

        with sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True) as con:
            return con.execute("SELECT COUNT(*) FROM Packages").fetchone()[0]
    except Exception:  # noqa: BLE001  no sqlite3 module, or a database layout we don't know
        return 0


@source("apk")
def apk(_env: Env) -> int:
    return sum(1 for line in read_text(Path("/lib/apk/db/installed")).splitlines() if line.startswith("P:"))


@source("xbps")
def xbps(_env: Env) -> int:
    return sum(read_text(p).count("<key>pkgver</key>") for p in Path("/var/db/xbps").glob("pkgdb-*.plist"))


@source("nix")
def nix(env: Env) -> int:
    return json_len(env.home / ".nix-profile/manifest.json", "elements")


@source("brew")
def brew(env: Env) -> int:
    prefix = brew_prefix(env)
    return entries(f"{prefix}/Cellar") if prefix else 0


@source("cask")
def cask(env: Env) -> int:
    prefix = brew_prefix(env)
    return entries(f"{prefix}/Caskroom") if prefix else 0


@source("flatpak")
def flatpak(env: Env) -> int:
    return entries("/var/lib/flatpak/app") + entries(data_home(env) / "flatpak/app")


@source("snap")
def snap(_env: Env) -> int:
    return entries("/snap", skip=("bin", "README", "snapd", "core", "core18", "core20", "core22", "core24"))


@source("app store")
def app_store(_env: Env) -> int:
    return len(list(Path("/Applications").glob("*.app/Contents/_MASReceipt")))


# --- developer tooling -------------------------------------------------------------


@source("npm", "tooling")
def npm(env: Env) -> int:
    return node_modules(f"{brew_prefix(env)}/lib/node_modules", "/usr/local/lib/node_modules", "/usr/lib/node_modules")


@source("pnpm", "tooling")
def pnpm(env: Env) -> int:
    return node_modules(env.home / "Library/pnpm/global/5/node_modules", data_home(env) / "pnpm/global/5/node_modules")


@source("bun", "tooling")
def bun(env: Env) -> int:
    return node_modules(env.home / ".bun/install/global/node_modules")


@source("pipx", "tooling")
def pipx(env: Env) -> int:
    return entries(data_home(env) / "pipx/venvs", env.home / ".local/pipx/venvs")


@source("uv", "tooling")
def uv(env: Env) -> int:
    return entries(data_home(env) / "uv/tools")


@source("cargo", "tooling")
def cargo(env: Env) -> int:
    return json_len(env.home / ".cargo/.crates2.json", "installs")


@source("go", "tooling")
def go(env: Env) -> int:
    return entries(Path(env.get("GOPATH") or env.home / "go") / "bin")


def row(group: str, env: Env) -> str:
    """ "424 brew · 129 cask", with zero counts left out."""
    counts = ((s.name, s.count(env)) for s in SOURCES if s.group == group)
    return DOT.join(f"{n} {GREY}{name}{RESET}" for name, n in counts if n)
