import pytest

from nekofetch import cli


def test_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "fastfetch, but with catgirls." in out
    assert "doctor" in out


def test_subcommand_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["add", "--help"])
    assert "FILE|URL" in capsys.readouterr().out


def test_says_check(capsys):
    assert cli.main(["says", "--check"]) == 0
    assert "all good" in capsys.readouterr().out


def test_setup_and_undo(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/bash")
    assert cli.main(["setup", "--yes"]) == 0
    assert (tmp_path / "config/nekofetch/config.toml").exists()
    rc = next((tmp_path / "home").glob(".bash*"))
    assert "nekofetch setup" in rc.read_text()
    assert cli.main(["setup", "--undo"]) == 0
    assert not rc.exists()  # it held nothing but our line


def test_passthrough_reaches_fastfetch(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "nekofetch.app.App.run",
        lambda _self, _image, _protocol, _uwu, fastfetch_args: seen.update(args=fastfetch_args) or 0,
    )
    assert cli.main(["-p", "ascii", "--", "--logo-position", "top"]) == 0
    assert seen["args"] == ["--logo-position", "top"]


def test_uwu_before_a_subcommand_sticks(monkeypatch):
    seen = {}
    monkeypatch.setattr("nekofetch.app.App.says", lambda _self, uwu=None, **_kw: seen.update(uwu=uwu) or "")
    cli.main(["--uwu", "says"])
    assert seen["uwu"] is True


def test_double_dash_after_a_subcommand_stays_with_it(tmp_path):
    odd = tmp_path / "-odd.png"
    odd.write_bytes(b"x")
    assert cli.main(["add", "--", str(odd)]) == 0


def test_run_options_with_a_subcommand_are_an_error():
    with pytest.raises(SystemExit) as e:
        cli.main(["-p", "ascii", "list"])
    assert e.value.code == 2


def test_unwritable_config_is_one_line(tmp_path, capsys):
    (tmp_path / "config").mkdir()
    (tmp_path / "config").chmod(0o500)
    try:
        assert cli.main(["setup", "--no-shell"]) == 1
    finally:
        (tmp_path / "config").chmod(0o700)
    assert "Traceback" not in capsys.readouterr().err


def test_weather_timer_is_opt_in(tmp_path, monkeypatch):
    from nekofetch import timer

    monkeypatch.setattr(timer, "run", lambda *_a, **_k: "")
    monkeypatch.setattr(timer.sys, "platform", "darwin")
    agent = tmp_path / "home/Library/LaunchAgents"
    assert cli.main(["setup", "--no-shell"]) == 0
    assert not agent.exists()
    assert cli.main(["setup", "--no-shell", "--weather-timer"]) == 0
    assert len(list(agent.iterdir())) == 1
    assert cli.main(["setup", "--undo"]) == 0
    assert not list(agent.iterdir())


def test_bare_nekofetch_skips_the_parser(monkeypatch):
    seen = {}
    monkeypatch.setattr("nekofetch.app.App.run", lambda _self: seen.setdefault("ran", True) and 0)
    monkeypatch.setattr(cli, "parser", lambda: pytest.fail("parser built for a bare run"))
    assert cli.main([]) == 0
    assert seen["ran"]


def test_rows_the_layout_does_not_show_are_skipped(monkeypatch):
    from nekofetch.app import App

    called = []
    monkeypatch.setattr("nekofetch.sources.packages.row", lambda *a: called.append(a) or "")
    rows = App.load().rows(wanted=["NEKO_LOCALE"])
    assert list(rows) == ["NEKO_LOCALE"]
    assert not called
