"""Locale, battery, uptime, disk and git: one function each, per platform where needed."""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

from nekofetch.paths import read_text
from nekofetch.style import DOT, GREY, RESET
from nekofetch.system import Env, run


class Battery(NamedTuple):
    percent: int
    discharging: bool


def _battery_macos() -> Battery | None:
    out = run("pmset", "-g", "batt")
    m = re.search(r"(\d+)%", out)
    return Battery(int(m.group(1)), "discharging" in out) if m else None


def _battery_linux() -> Battery | None:
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            pct = int(read_text(bat / "capacity"))
        except ValueError:
            continue
        return Battery(pct, read_text(bat / "status").strip() == "Discharging")
    return None


def battery() -> Battery | None:
    """None on machines without a battery."""
    return _battery_macos() if sys.platform == "darwin" else _battery_linux()


def _macos_region(env: Env) -> str:
    import plistlib

    try:
        with (env.home / "Library/Preferences/.GlobalPreferences.plist").open("rb") as f:
            return plistlib.load(f).get("AppleLocale", "")
    except (OSError, ValueError, plistlib.InvalidFileException):
        return ""


def locale_row(env: Env) -> str:
    """$LANG, plus the macOS region when it differs (en_US.UTF-8 · region en_AT)."""
    lang = env.get("LC_ALL") or env.get("LANG") or "unset"
    region = _macos_region(env) if sys.platform == "darwin" else ""
    if region and not lang.startswith(region):
        return f"{lang}{DOT}{GREY}region {region}{RESET}"
    return lang


def uptime_days() -> int:
    clock = getattr(time, "CLOCK_BOOTTIME", time.CLOCK_MONOTONIC)  # macOS counts sleep anyway
    return int(time.clock_gettime(clock) // 86400)


def disk_percent() -> int:
    data_volume = Path("/System/Volumes/Data")
    path = data_volume if data_volume.is_dir() else Path("/")
    try:
        st = os.statvfs(path)
    except OSError:
        return 0
    total = st.f_blocks * st.f_frsize
    return round(100 * (total - st.f_bavail * st.f_frsize) / total) if total else 0


def git_changes() -> int:
    """Uncommitted changes to tracked files in the current repo; git only runs inside one."""
    try:
        d = Path.cwd()
    except OSError:
        return 0
    if not any((p / ".git").exists() for p in (d, *d.parents)):
        return 0
    return len(
        run(
            "git", "--no-optional-locks", "status", "--porcelain", "-uno", "--ignore-submodules", timeout=1
        ).splitlines()
    )
