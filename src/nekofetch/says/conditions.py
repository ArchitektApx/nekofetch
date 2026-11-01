"""The moments the cat has an opinion about. says.toml refers to these by name.

Facts are gathered lazily, so a says.toml without battery or git lines never
asks for the battery or runs git.
"""

from __future__ import annotations

import re
import time
from functools import cached_property
from typing import TYPE_CHECKING

from nekofetch.paths import read_text, write_text
from nekofetch.sources import machine

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

BATTERY_CRITICAL = 10  # percent
BATTERY_LOW = 25
DISK_FULL = 90  # percent
LONG_UPTIME_DAYS = 7
HOT = 28  # °C
SUNNY_FROM, SUNNY_UNTIL = 8, 19  # hours of the day
FRIDAY, SATURDAY = 4, 5  # tm_wday
# the day's parts, as the hour each one starts at
NIGHT_ENDS = 5
MORNING = 9
NOON = 12
AFTERNOON = 14
EVENING = 18
LATE = 22


class Facts:
    def __init__(
        self,
        cache: Path,
        weather: str = "",
        now: time.struct_time | None = None,
        user: str = "you",
        record: bool = True,
    ) -> None:
        self.cache = cache
        self.now = now or time.localtime()
        self.weather = weather.lower()
        self.user = user
        self.record = record  # False: look, but don't use up today's first_shell

    @property
    def hour(self) -> int:
        return self.now.tm_hour

    @property
    def weekday(self) -> int:
        return self.now.tm_wday

    @property
    def month(self) -> int:
        return self.now.tm_mon

    @cached_property
    def temp(self) -> int | None:
        """In °C, whatever units the weather line uses."""
        m = re.search(r"([+-]?\d+)°([CF])", self.weather.upper())
        if not m:
            return None
        t = int(m.group(1))
        return round((t - 32) * 5 / 9) if m.group(2) == "F" else t

    @cached_property
    def temp_shown(self) -> str | None:
        """The temperature as the weather row shows it, unit included: +4°C or +39°F."""
        m = re.search(r"[+-]?\d+°[CF]", self.weather.upper())
        return m.group(0) if m else None

    @cached_property
    def battery(self) -> machine.Battery | None:
        return machine.battery()

    @cached_property
    def uptime(self) -> int:
        return machine.uptime_days()

    @cached_property
    def disk(self) -> int:
        return machine.disk_percent()

    @cached_property
    def changes(self) -> int:
        return machine.git_changes()

    @cached_property
    def first_today(self) -> bool:
        """True for the first nekofetch of the day."""
        path = self.cache / "last-day"
        today = time.strftime("%Y-%m-%d", self.now)
        if read_text(path).strip() == today:
            return False
        if self.record:
            write_text(path, today)
        return True

    def weather_has(self, pattern: str) -> bool:
        return re.search(pattern, self.weather) is not None

    def discharging_below(self, low: int, high: int) -> bool:
        b = self.battery
        return bool(b and b.discharging and low < b.percent <= high)


CONDITIONS: dict[str, Callable[[Facts], bool]] = {}


def condition(fn: Callable[[Facts], bool]) -> Callable[[Facts], bool]:
    CONDITIONS[fn.__name__] = fn
    return fn


# machine
@condition
def battery_critical(f: Facts) -> bool:
    return f.discharging_below(-1, BATTERY_CRITICAL)


@condition
def battery_low(f: Facts) -> bool:
    return f.discharging_below(BATTERY_CRITICAL, BATTERY_LOW)


@condition
def disk_full(f: Facts) -> bool:
    return f.disk >= DISK_FULL


@condition
def long_uptime(f: Facts) -> bool:
    return f.uptime >= LONG_UPTIME_DAYS


@condition
def git_dirty(f: Facts) -> bool:
    return f.changes > 0


@condition
def first_shell(f: Facts) -> bool:
    return f.first_today


# weather
@condition
def rain(f: Facts) -> bool:
    return f.weather_has(r"rain|drizzle|shower")


@condition
def snow(f: Facts) -> bool:
    return f.weather_has(r"snow|sleet|blizzard")


@condition
def thunder(f: Facts) -> bool:
    return f.weather_has(r"thunder")


@condition
def sunny(f: Facts) -> bool:
    return f.weather_has(r"sunny|clear") and SUNNY_FROM <= f.hour < SUNNY_UNTIL


@condition
def fog(f: Facts) -> bool:
    return f.weather_has(r"fog|mist")


@condition
def freezing(f: Facts) -> bool:
    return f.temp is not None and f.temp <= 0


@condition
def hot(f: Facts) -> bool:
    return f.temp is not None and f.temp >= HOT


# time of day
@condition
def night(f: Facts) -> bool:
    return f.hour < NIGHT_ENDS


@condition
def early(f: Facts) -> bool:
    return NIGHT_ENDS <= f.hour < MORNING


@condition
def morning(f: Facts) -> bool:
    return MORNING <= f.hour < NOON


@condition
def lunch(f: Facts) -> bool:
    return NOON <= f.hour < AFTERNOON


@condition
def afternoon(f: Facts) -> bool:
    return AFTERNOON <= f.hour < EVENING


@condition
def evening(f: Facts) -> bool:
    return EVENING <= f.hour < LATE


@condition
def late(f: Facts) -> bool:
    return f.hour >= LATE


# calendar
@condition
def monday_morning(f: Facts) -> bool:
    return f.weekday == 0 and f.hour < NOON


@condition
def friday_afternoon(f: Facts) -> bool:
    return f.weekday == FRIDAY and f.hour >= AFTERNOON


@condition
def weekend(f: Facts) -> bool:
    return f.weekday >= SATURDAY


@condition
def winter(f: Facts) -> bool:
    return f.month in (12, 1, 2)


@condition
def spring(f: Facts) -> bool:
    return f.month in (3, 4, 5)


@condition
def summer(f: Facts) -> bool:
    return f.month in (6, 7, 8)


@condition
def autumn(f: Facts) -> bool:
    return f.month in (9, 10, 11)


@condition
def always(_f: Facts) -> bool:
    return True
