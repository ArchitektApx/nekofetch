"""The optional weather timer: `nekofetch setup --weather-timer`.

Without it, weather refreshes in the background when a shell finds it stale, so
the fresh line shows up one shell later. The timer refreshes on a schedule
instead: a launchd agent on macOS, a systemd user timer on Linux. Both run after
sleep to catch up, and both are a file or two that only nekofetch touches.
"""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from nekofetch.paths import xdg
from nekofetch.system import run

if TYPE_CHECKING:
    from nekofetch.system import Env

NAME = "nekofetch-weather"
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
CRON_MINUTES = tuple(m for m in range(1, MINUTES_PER_HOUR) if MINUTES_PER_HOUR % m == 0)
CRON_HOURS = tuple(h for h in range(1, HOURS_PER_DAY + 1) if HOURS_PER_DAY % h == 0)


def refresh_command() -> list[str]:
    """The same Python and package that run nekofetch, so it survives PATH changes."""
    return [sys.executable, "-m", "nekofetch", "weather", "--refresh", "--quiet"]


class Timer(ABC):
    def __init__(self, env: Env) -> None:
        self.env = env

    @property
    @abstractmethod
    def files(self) -> list[Path]: ...

    @abstractmethod
    def contents(self, minutes: int) -> list[str]:
        """The text of each file in `files`, in the same order."""

    @abstractmethod
    def activate(self) -> None: ...

    @abstractmethod
    def deactivate(self) -> None: ...

    def installed(self) -> bool:
        return all(f.exists() for f in self.files)

    def install(self, minutes: int) -> list[Path]:
        if self.installed():
            self.deactivate()  # reload with the current interval
        for path, text in zip(self.files, self.contents(minutes), strict=True):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.activate()
        return self.files

    def remove(self) -> list[Path]:
        present = [f for f in self.files if f.exists()]
        if present:
            self.deactivate()
            for f in present:
                f.unlink()
        return present


class Launchd(Timer):
    LABEL = "io.github.architektapx.nekofetch.weather"

    @property
    def files(self) -> list[Path]:
        return [self.env.home / "Library/LaunchAgents" / f"{self.LABEL}.plist"]

    def contents(self, minutes: int) -> list[str]:
        import plistlib

        plist = {
            "Label": self.LABEL,
            "ProgramArguments": refresh_command(),
            "StartInterval": minutes * 60,
            "RunAtLoad": True,
            "ProcessType": "Background",
            "LowPriorityIO": True,
            "StandardOutPath": os.devnull,
            "StandardErrorPath": os.devnull,
        }
        return [plistlib.dumps(plist).decode()]

    @property
    def domain(self) -> str:
        return f"gui/{os.getuid()}"

    def activate(self) -> None:
        run("launchctl", "bootstrap", self.domain, str(self.files[0]))

    def deactivate(self) -> None:
        run("launchctl", "bootout", f"{self.domain}/{self.LABEL}")


class Systemd(Timer):
    @property
    def files(self) -> list[Path]:
        folder = xdg(self.env.vars, "XDG_CONFIG_HOME") / "systemd/user"
        return [folder / f"{NAME}.service", folder / f"{NAME}.timer"]

    def contents(self, minutes: int) -> list[str]:
        command = " ".join(f'"{a}"' if " " in a else a for a in refresh_command())
        service = f"[Unit]\nDescription=nekofetch weather refresh\n\n[Service]\nType=oneshot\nExecStart={command}\n"
        if spec := calendar(minutes):
            # wall-clock schedule; Persistent catches up on runs missed while asleep
            schedule = f"OnCalendar={spec}\nPersistent=true\n"
        else:  # intervals a calendar can't express exactly (45, 90 ...): count from the last run
            schedule = f"OnStartupSec=1min\nOnUnitActiveSec={minutes}min\n"
        timer = (
            f"[Unit]\nDescription=nekofetch weather refresh\n\n[Timer]\n{schedule}\n[Install]\nWantedBy=timers.target\n"
        )
        return [service, timer]

    def activate(self) -> None:
        run("systemctl", "--user", "daemon-reload")
        run("systemctl", "--user", "enable", "--now", f"{NAME}.timer")

    def deactivate(self) -> None:
        run("systemctl", "--user", "disable", "--now", f"{NAME}.timer")


def for_platform(env: Env) -> Timer | None:
    """The timer for this system, or None when there is no scheduler we manage."""
    if sys.platform == "darwin":
        return Launchd(env)
    if env.which("systemctl") and Path("/run/systemd/system").is_dir():
        return Systemd(env)
    return None


def calendar(minutes: int) -> str | None:
    """`minutes` as a systemd calendar spec, if it fits one exactly: calendars count
    within the hour (or day), so only divisors of 60 minutes or of 24 hours do."""
    if minutes < MINUTES_PER_HOUR and MINUTES_PER_HOUR % minutes == 0:
        return f"*:0/{minutes}"
    hours, rest = divmod(minutes, MINUTES_PER_HOUR)
    if not rest and HOURS_PER_DAY % hours == 0:
        return f"0/{hours}:00"
    return None


def cron_line(minutes: int) -> str:
    """For systems without launchd or systemd: a line the user can add themselves.
    cron has the same limits as calendars, so this is the closest interval at or under `minutes`."""
    every = max(m for m in (*CRON_MINUTES, *(h * MINUTES_PER_HOUR for h in CRON_HOURS)) if m <= max(minutes, 1))
    schedule = f"*/{every} * * * *" if every < MINUTES_PER_HOUR else f"0 */{every // MINUTES_PER_HOUR} * * *"
    return f"{schedule} {' '.join(refresh_command())}"
