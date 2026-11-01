"""Startup time of nekofetch next to plain fastfetch.

Runs against a throwaway HOME and XDG dirs with a cached weather line, so it
never touches your config, uses up today's first-shell line or hits the network.

usage: python3 tools/bench.py [runs]     whole runs, from a checkout after `uv sync`
       uv run tools/bench.py --rows      time spent per part, inside one process
"""

import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv/bin"
LAYOUT = ROOT / "src/nekofetch/data/layout.jsonc"

CASES = {
    "python startup": [str(VENV / "python"), "-c", "pass"],
    "fastfetch alone": ["fastfetch", "--pipe", "--logo-type", "none", "-c", str(LAYOUT)],
    "nekofetch": [str(VENV / "nekofetch")],
    "nekofetch (ascii)": [str(VENV / "nekofetch"), "-p", "ascii", "--", "--pipe"],
    "nekofetch (chafa)": [str(VENV / "nekofetch"), "-p", "chafa", "--", "--pipe"],
}


def rows() -> None:
    """Where nekofetch's own time goes, measured inside one process."""
    start = time.perf_counter()
    from nekofetch import terminals
    from nekofetch.app import App
    from nekofetch.sources import machine, packages

    print(f"{'import':<20} {(time.perf_counter() - start) * 1000:5.1f} ms")
    app = App.load()
    steps = {
        "logo": app.logo,
        "packages": lambda: packages.row("system", app.env),
        "tooling": lambda: packages.row("tooling", app.env),
        "terminal": lambda: terminals.describe(app.env),
        "locale": lambda: machine.locale_row(app.env),
        "weather": app.weather.line,
        "says": lambda: app.says(record=False),
    }
    for name, step in steps.items():
        start = time.perf_counter()
        step()
        print(f"{name:<20} {(time.perf_counter() - start) * 1000:5.1f} ms")


def sandbox() -> None:
    """Point HOME and XDG at a temp dir, with weather already cached."""
    home = Path(tempfile.mkdtemp(prefix="nekofetch-bench-"))
    cache = home / ".cache/nekofetch"
    cache.mkdir(parents=True)
    (cache / "weather.txt").write_text("󰖐 Overcast · 󰔏 +7°C\n|metric\n", encoding="utf-8")
    os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_CACHE_HOME=str(home / ".cache"))


def main() -> None:
    sandbox()
    if sys.argv[1:] == ["--rows"]:
        rows()
        return
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    for name, cmd in CASES.items():
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            times.append((time.perf_counter() - start) * 1000)
        print(f"{name:<20} {statistics.median(times):5.0f} ms median   {min(times):4.0f} ms min")


if __name__ == "__main__":
    main()
