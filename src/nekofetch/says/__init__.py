"""What the cat says: lines from says.toml, picked by which conditions are true."""

from __future__ import annotations

import random
import threading
import time
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from nekofetch.says.conditions import CONDITIONS
from nekofetch.says.uwu import uwuify
from nekofetch.style import CAT, GREY, PINK, RESET

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from nekofetch.config import SaysConfig
    from nekofetch.says.conditions import Facts

MAX_WIDTH = 34
SAMPLE: dict[str, object] = {
    "time": "00:00",
    "user": "someone",
    "battery": 100,
    "temp": "-10°C",
    "uptime": 99,
    "disk": 100,
    "changes": 99,
}


class Blank(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "?"


def fill(line: str, values: dict[str, object]) -> str:
    try:
        return line.format_map(Blank(values))
    except (ValueError, AttributeError, IndexError, KeyError, TypeError):
        return line


@dataclass(frozen=True)
class Table:
    lines: list[str]
    priority: bool = False


@dataclass(frozen=True)
class SaysFile:
    dates: dict[str, list[str]] = field(default_factory=dict[str, list[str]])  # "MM-DD" -> lines
    when: dict[str, Table] = field(default_factory=dict[str, Table])  # condition -> lines
    errors: list[str] = field(default_factory=list[str])

    @classmethod
    def load(cls, path: Path) -> SaysFile:
        try:
            with path.open("rb") as f:
                raw = tomllib.load(f)
        except (OSError, ValueError) as e:
            return cls(errors=[f"{path}: {e}"])

        def strings(v: object) -> list[str]:
            return [x for x in cast("list[object]", v) if isinstance(x, str)] if isinstance(v, list) else []

        def table(v: object) -> dict[str, object] | None:
            return cast("dict[str, object]", v) if isinstance(v, dict) else None

        dates = table(raw.get("dates")) or {}
        when = table(raw.get("when")) or {}
        return cls(
            dates={k: strings(v) for k, v in dates.items()},
            when={
                k: Table(strings(t.get("lines")), t.get("priority") is True)
                for k, v in when.items()
                if (t := table(v)) is not None
            },
        )

    def all_lines(self) -> list[str]:
        return [line for v in self.dates.values() for line in v] + [
            line for t in self.when.values() for line in t.lines
        ]

    def problems(self) -> list[str]:
        out = list(self.errors)
        for line in self.all_lines():
            try:
                n = len(line.format_map(Blank(SAMPLE)))
            except (ValueError, AttributeError, IndexError, KeyError, TypeError) as e:
                out.append(f"broken placeholder ({e}): {line}")
                continue
            if n > MAX_WIDTH:
                out.append(f"too long ({n} > {MAX_WIDTH}): {line}")
        out += [f"unknown condition: {name}" for name in self.when if name not in CONDITIONS]
        return out

    def pick(self, facts: Facts, rng: random.Random) -> str:
        special = list(self.dates.get(time.strftime("%m-%d", facts.now), []))
        pool: list[str] = []
        for name, table in self.when.items():
            cond = CONDITIONS.get(name)
            try:
                active = cond is not None and cond(facts)
            except TypeError:  # e.g. no battery on this machine
                active = False
            if active:
                (special if table.priority else pool).extend(table.lines)
        return rng.choice(special or pool or ["meow"])


def uwu_today(conf: SaysConfig, now: time.struct_time) -> bool:
    if conf.uwu == "april":
        return (now.tm_mon, now.tm_mday) == (4, 1)
    return conf.uwu is True


def say(
    conf: SaysConfig, says: SaysFile, facts: Facts, uwu: bool | None = None, rng: random.Random | None = None
) -> str:
    """The whole row, cat included. Empty when the cat is muted."""
    if not conf.enabled:
        return ""
    rng = rng or random.Random()
    if "git_dirty" in says.when or any("{changes}" in line for line in says.all_lines()):
        # git and the battery are both subprocesses: run git alongside instead of after
        git = threading.Thread(target=lambda: facts.changes)
        git.start()
        _ = facts.battery
        git.join()
    msg = says.pick(facts, rng)
    lazy: dict[str, Callable[[], object]] = {
        "time": lambda: time.strftime("%H:%M", facts.now),
        "user": lambda: facts.user,
        "battery": lambda: facts.battery.percent if facts.battery else None,
        "temp": lambda: facts.temp_shown,
        "uptime": lambda: facts.uptime,
        "disk": lambda: facts.disk,
        "changes": lambda: facts.changes,
    }
    # only gather what the line mentions
    text = fill(msg, {k: get() for k, get in lazy.items() if "{" + k in msg})
    if uwu if uwu is not None else uwu_today(conf, facts.now):
        text = uwuify(text, seed=rng.randrange(1 << 30))
    return f"  {PINK}{CAT}{RESET} {GREY}«{RESET} {text}"
