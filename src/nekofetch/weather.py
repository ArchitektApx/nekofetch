"""One line of weather from wttr.in, cached.

nekofetch never waits for the network: it shows the cached line (even an old
one) and, when that is stale, starts `nekofetch weather --refresh` in the
background for next time. The cache remembers which location and units it was
fetched for, so changing them in config.toml takes effect on the next refresh.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nekofetch import __version__
from nekofetch.paths import read_text, write_text
from nekofetch.style import DOT, GREY, RESET

if TYPE_CHECKING:
    from pathlib import Path

    from nekofetch.config import WeatherConfig

# wttr.in emoji -> Nerd Font weather icons, which are one cell wide
ICONS = {
    "☀": "󰖙",
    "🌛": "󰖔",
    "⛅": "󰖕",
    "☁": "󰖐",
    "🌫": "󰖑",
    "🌦": "󰖗",
    "🌧": "󰖖",
    "❄": "󰼶",
    "🌨": "󰖘",
    "🌩": "󰖓",
    "⛈": "󰙾",
    "✨": "󰖐",
}
# wttr.in arrows point where the wind blows to; we name where it comes from
WIND = {"↓": "N", "↙": "NE", "←": "E", "↖": "SE", "↑": "S", "↗": "SW", "→": "W", "↘": "NW"}
RETRY_AFTER = 300  # seconds between background attempts
MIN_CACHE_LINES = 2  # the line, then the location and units it was fetched for
SHOW_AGE_AFTER = 3600  # seconds; older weather says how old it is
HOURS_PER_DAY = 24
MIN_FIELDS = 5  # wttr.in's answer has 7; fewer than this is an error page


def format_line(parts: list[str], local: bool = True, now: str | None = None) -> str:
    """wttr.in's `icon|condition|temp|wind|moon|sunrise|sunset` as a styled row."""
    icon, cond, temp, wind, moon, sunrise, sunset = (parts + [""] * 7)[:7]
    icon = icon.replace("️", "").strip()
    now = now or time.strftime("%H:%M:%S")
    # sunrise and sunset are in the location's time zone; only trust them for "here"
    if local and icon == "☀" and sunrise and sunset and not sunrise <= now <= sunset:
        icon = "🌛"
    icon = ICONS.get(icon, icon)
    for arrow, name in WIND.items():
        if arrow in wind:
            wind = wind.replace(arrow, f"{name}{arrow}")
            break
    pieces = (f"{icon} {cond}".strip(), f"󰔏 {temp}" if temp else "", f"󰖝 {wind}" if wind else "", moon)
    return DOT.join(p for p in pieces if p.strip())


def ago(seconds: float) -> str:
    """3h ago, 2d ago: rough on purpose."""
    hours = int(seconds // 3600)
    return f"{hours}h ago" if hours < HOURS_PER_DAY else f"{hours // HOURS_PER_DAY}d ago"


@dataclass(frozen=True)
class Weather:
    conf: WeatherConfig
    cache_dir: Path

    @property
    def cache(self) -> Path:
        return self.cache_dir / "weather.txt"

    @property
    def lock(self) -> Path:
        return self.cache_dir / "weather.lock"

    @property
    def key(self) -> str:
        """What the cached line was fetched for; changing either means fetching again."""
        return f"{self.conf.location.strip()}|{self.conf.units}"

    @property
    def url(self) -> str:
        from urllib.parse import quote  # only needed to fetch, not to read the cache

        loc = quote(self.conf.location.strip().replace(" ", "+"), safe="+~@,-")
        units = "u" if self.conf.units == "imperial" else "m"
        return f"https://wttr.in/{loc}?{units}&format=%c|%C|%t|%w|%m|%S|%s"

    def cached(self) -> tuple[str, float | None]:
        """(line, age in seconds) for this location; ("", None) when there is none."""
        text = read_text(self.cache).splitlines()
        if len(text) < MIN_CACHE_LINES or text[1] != self.key:
            return "", None
        try:
            return text[0], time.time() - self.cache.stat().st_mtime
        except OSError:
            return "", None

    def fetch(self, tries: int = 3) -> str:
        import urllib.request  # slow to import; only the background refresh needs it

        req = urllib.request.Request(  # noqa: S310  the URL is always https://wttr.in/...
            self.url, headers={"User-Agent": f"curl/8 nekofetch/{__version__}"}
        )
        error: Exception | None = None
        for attempt in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310  https only, see above
                    raw = r.read().decode("utf-8").strip()
                return self._parse(raw)
            except (OSError, ValueError) as e:
                error = e
                if attempt + 1 < tries:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"wttr.in: {error}")

    def _parse(self, raw: str) -> str:
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < MIN_FIELDS or raw.startswith("<") or "unknown location" in raw.lower():
            raise ValueError(raw[:80] or "empty answer")
        return format_line(parts, local=not self.conf.location.strip())

    def refresh(self) -> str:
        """Fetch now and cache it. Raises RuntimeError; a failure also backs off retries."""
        try:
            line = self.fetch()
        except RuntimeError:
            write_text(self.lock, "failed")
            raise
        write_text(self.cache, f"{line}\n{self.key}\n")
        return line

    def line(self) -> str:
        """What the Weather row shows. Kicks off a background refresh when stale."""
        if not self.conf.enabled:
            return ""
        line, age = self.cached()
        if age is None or age > self.conf.refresh * 60:
            self._refresh_in_background()
        if line and age is not None and age > SHOW_AGE_AFTER:
            return f"{line}{DOT}{GREY}{ago(age)}{RESET}"
        if line:
            return line
        # nothing cached yet: say so, unless the last try failed (offline): then hide the row
        return "" if read_text(self.lock) == "failed" else f"{GREY}asking the sky...{RESET}"

    def _refresh_in_background(self) -> None:
        try:
            if time.time() - self.lock.stat().st_mtime < RETRY_AFTER:
                return  # one is running, or the last one failed recently
        except OSError:
            pass
        if not write_text(self.lock, "busy"):
            return  # no writable cache, no point fetching
        with contextlib.suppress(OSError):
            subprocess.Popen(
                [sys.executable, "-m", "nekofetch", "weather", "--refresh", "--quiet"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
