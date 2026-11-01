import random
import time

from nekofetch.config import SaysConfig
from nekofetch.paths import DATA
from nekofetch.says import SaysFile, Table, say, uwu_today
from nekofetch.says.conditions import CONDITIONS, Facts
from nekofetch.says.uwu import builtin


def facts(tmp_path, when="2026-06-10 10:00", weather=""):
    now = time.strptime(when, "%Y-%m-%d %H:%M")
    f = Facts(tmp_path, weather=weather, now=now)
    f.__dict__.update(first_today=False, battery=None, changes=0, disk=10, uptime=1)
    return f


def test_bundled_says_toml_is_clean():
    assert SaysFile.load(DATA / "says.toml").problems() == []


def test_picks_from_true_conditions(tmp_path):
    says = SaysFile(when={"rain": Table(["wet"]), "snow": Table(["cold"])})
    assert says.pick(facts(tmp_path, weather="Light rain"), random.Random(1)) == "wet"


def test_dates_win(tmp_path):
    says = SaysFile.load(DATA / "says.toml")
    assert "halloween" in says.pick(facts(tmp_path, "2026-10-31 12:00"), random.Random(1))


def test_broken_file_does_not_crash(tmp_path):
    path = tmp_path / "says.toml"
    path.write_text('[when]\nalways = "meow"\n[when.morning]\nlines = ["{}", "{user.x}", 3]\n')
    says = SaysFile.load(path)
    line = say(SaysConfig(), says, facts(tmp_path), rng=random.Random(1))
    assert "«" in line
    assert any("broken placeholder" in p for p in says.problems())


def test_temperature_in_fahrenheit_counts_as_freezing(tmp_path):
    assert CONDITIONS["freezing"](facts(tmp_path, weather="󰖘 Snow · 󰔏 +28°F"))


def test_uwu():
    out = builtin("hello, the router is really slow", random.Random(3))
    assert "hewwo" in out
    assert "woutew" in out


def test_uwu_on_april_first_only():
    april = time.strptime("2026-04-01", "%Y-%m-%d")
    may = time.strptime("2026-05-01", "%Y-%m-%d")
    assert uwu_today(SaysConfig(), april)
    assert not uwu_today(SaysConfig(), may)
    assert not uwu_today(SaysConfig(uwu=False), april)
    assert uwu_today(SaysConfig(uwu=True), may)


def test_muted(tmp_path):
    assert say(SaysConfig(enabled=False), SaysFile(), facts(tmp_path)) == ""
