import plistlib
import sys

import pytest

from nekofetch import timer
from nekofetch.system import Env


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple[str, ...]] = []
    monkeypatch.setattr(timer, "run", lambda *cmd, **_kw: seen.append(cmd) or "")
    return seen


def test_launchd_agent(tmp_path, calls):
    t = timer.Launchd(Env({"HOME": str(tmp_path)}))
    (path,) = t.install(30)
    plist = plistlib.loads(path.read_bytes())
    assert path.parent == tmp_path / "Library/LaunchAgents"
    assert plist["StartInterval"] == 1800
    assert plist["ProgramArguments"][0] == sys.executable
    assert plist["ProgramArguments"][-3:] == ["weather", "--refresh", "--quiet"]
    assert calls[-1][:2] == ("launchctl", "bootstrap")
    assert t.remove() == [path]
    assert not path.exists()
    assert calls[-1][:2] == ("launchctl", "bootout")


def test_systemd_units_follow_xdg(tmp_path, calls):
    env = Env({"HOME": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path / "cfg")})
    service, unit = timer.Systemd(env).install(30)
    assert service.parent == tmp_path / "cfg/systemd/user"
    assert "OnCalendar=*:0/30" in unit.read_text()
    assert "Persistent=true" in unit.read_text()
    assert ("systemctl", "--user", "enable", "--now", "nekofetch-weather.timer") in calls


def test_intervals_a_calendar_can_express():
    assert timer.calendar(30) == "*:0/30"
    assert timer.calendar(120) == "0/2:00"
    assert timer.calendar(45) is None
    assert timer.calendar(90) is None


@pytest.mark.usefixtures("calls")
def test_odd_intervals_count_from_the_last_run(tmp_path):
    _, unit = timer.Systemd(Env({"HOME": str(tmp_path)})).install(45)
    assert "OnUnitActiveSec=45min" in unit.read_text()
    assert "OnCalendar" not in unit.read_text()


def test_cron_rounds_down_to_what_cron_can_do():
    assert timer.cron_line(30).startswith("*/30 * * * * ")
    assert timer.cron_line(45).startswith("*/30 * * * * ")
    assert timer.cron_line(90).startswith("0 */1 * * * ")
    assert timer.cron_line(180).startswith("0 */3 * * * ")


def test_reinstall_reloads(tmp_path, calls):
    t = timer.Launchd(Env({"HOME": str(tmp_path)}))
    t.install(30)
    t.install(60)
    assert [c[1] for c in calls] == ["bootstrap", "bootout", "bootstrap"]
    assert plistlib.loads(t.files[0].read_bytes())["StartInterval"] == 3600


def test_nothing_to_remove(tmp_path, calls):
    assert timer.Launchd(Env({"HOME": str(tmp_path)})).remove() == []
    assert calls == []
