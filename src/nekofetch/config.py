"""config.toml as typed settings. Bad values are reported and replaced by defaults."""

from __future__ import annotations

import tomllib
from dataclasses import Field, dataclass, field, fields, replace
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

T = TypeVar("T")


def choice(default: T, *allowed: T) -> T:
    """A field restricted to `allowed` values (the default is always allowed)."""
    return field(default=default, metadata={"choices": (default, *allowed)})


@dataclass(frozen=True)
class ImageConfig:
    order: str = choice("random", "sorted")
    # any renderer name; looked up on use, as renderers -> images -> config would be a cycle
    protocol: str = field(default="auto", metadata={"choices": lambda: ("auto", *_renderer_names())})
    width: int = 30
    height: int = 16
    folder: str = ""
    defaults: str = choice("fallback", "always", "never")


@dataclass(frozen=True)
class WeatherConfig:
    enabled: bool = True
    location: str = ""
    units: str = choice("metric", "imperial")
    refresh: int = 30


@dataclass(frozen=True)
class SaysConfig:
    enabled: bool = True
    # True, False, or "april": only on April 1st
    uwu: bool | str = choice("april", True, False)  # noqa: FBT003  values of the setting, not flags


@dataclass(frozen=True)
class Config:
    image: ImageConfig = ImageConfig()
    weather: WeatherConfig = WeatherConfig()
    says: SaysConfig = SaysConfig()


def _renderer_names() -> tuple[str, ...]:
    from nekofetch.renderers import RENDERERS

    return tuple(RENDERERS)


Section = TypeVar("Section", ImageConfig, WeatherConfig, SaysConfig)


def _valid(f: Field[Any], value: object) -> bool:
    if "choices" in f.metadata:
        raw: tuple[object, ...] | Callable[[], tuple[object, ...]] = f.metadata["choices"]
        choices = raw() if callable(raw) else raw
        # `True == 1` in Python, so compare types too
        return any(value == c and type(value) is type(c) for c in choices)
    if isinstance(f.default, bool):
        return isinstance(value, bool)
    if isinstance(f.default, int):
        return isinstance(value, int) and not isinstance(value, bool) and value > 0
    return isinstance(value, type(f.default))


def _section(defaults: Section, values: dict[str, object], name: str, warnings: list[str]) -> Section:
    known = {f.name: f for f in fields(defaults)}
    changes: dict[str, object] = {}
    for key, value in values.items():
        f = known.get(key)
        if f is None:
            warnings.append(f"unknown setting [{name}] {key}")
        elif _valid(f, value):
            changes[key] = value
        else:
            warnings.append(f"ignoring [{name}] {key} = {value!r}")
    return replace(defaults, **changes)


def parse(data: dict[str, Any]) -> tuple[Config, list[str]]:
    conf, warnings = Config(), list[str]()
    known = {f.name for f in fields(Config)}
    sections: dict[str, Any] = {}
    for name, values in data.items():
        current = getattr(conf, name) if name in known else None
        if current is None or not isinstance(values, dict):
            warnings.append(f"unknown section [{name}]")
            continue
        sections[name] = _section(current, cast("dict[str, object]", values), name, warnings)
    return replace(conf, **sections), warnings


def load(path: Path) -> tuple[Config, list[str]]:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return Config(), []
    except (OSError, ValueError) as e:  # TOMLDecodeError and UnicodeDecodeError are ValueErrors
        return Config(), [f"ignoring {path}: {e}"]
    conf, warnings = parse(data)
    return conf, [f"{path}: {w}" for w in warnings]
