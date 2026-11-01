"""Where nekofetch reads and writes. Everything follows the XDG base directories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

DATA = Path(__file__).parent / "data"

XDG_DEFAULTS = {
    "XDG_CONFIG_HOME": ".config",
    "XDG_CACHE_HOME": ".cache",
    "XDG_DATA_HOME": ".local/share",
}


def xdg(env: Mapping[str, str], var: str) -> Path:
    """An XDG base directory. Per the spec, unset, empty and relative values fall back
    to the default under $HOME."""
    value = env.get(var, "")
    if value and Path(value).is_absolute():
        return Path(value)
    return Path(env.get("HOME") or Path.home()) / XDG_DEFAULTS[var]


@dataclass(frozen=True)
class Paths:
    config: Path  # ~/.config/nekofetch: the user's config, images and overrides
    cache: Path  # ~/.cache/nekofetch: weather, renders, small state files
    data: Path = DATA  # bundled defaults

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Paths:
        return cls(config=xdg(env, "XDG_CONFIG_HOME") / "nekofetch", cache=xdg(env, "XDG_CACHE_HOME") / "nekofetch")

    def user_or_default(self, name: str) -> Path:
        """The user's copy of a data file if there is one, else the bundled one."""
        mine = self.config / name
        return mine if mine.exists() else self.data / name

    @property
    def config_file(self) -> Path:
        return self.config / "config.toml"


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return default


def write_text(path: Path, text: str) -> bool:
    """Atomic write that never raises; False when the disk said no."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except (OSError, ValueError):
        return False
    return True
