import pytest

from nekofetch import terminals
from nekofetch.system import Env


def env(**env_vars):
    return Env({"TERM": "xterm-256color", **env_vars}, which=lambda _name: None)


@pytest.mark.parametrize(
    ("env_vars", "name", "renderers"),
    [
        ({"TERM_PROGRAM": "ghostty", "TERM_PROGRAM_VERSION": "1.4.0"}, "Ghostty", ("kitty", "kitty-direct")),
        ({"KITTY_WINDOW_ID": "1", "TERM": "xterm-kitty"}, "kitty", ("kitty", "kitty-direct")),
        ({"TERM_PROGRAM": "WezTerm"}, "WezTerm", ("iterm",)),
        ({"TERM_PROGRAM": "iTerm.app"}, "iTerm2", ("iterm",)),
        ({"KONSOLE_VERSION": "240802"}, "Konsole", ("sixel",)),
        ({"TERM": "foot"}, "foot", ("sixel",)),
        ({"ALACRITTY_WINDOW_ID": "1"}, "Alacritty", ()),
        ({"VTE_VERSION": "7800"}, "VTE", ()),
    ],
)
def test_detect(env_vars, name, renderers):
    t = terminals.detect(env(**env_vars))
    assert (t.name, t.renderers) == (name, renderers)


def test_looks_through_tmux():
    e = env(
        TMUX="/tmp/t", TERM_PROGRAM="tmux", TERM_PROGRAM_VERSION="3.5", LC_TERMINAL="iTerm2", LC_TERMINAL_VERSION="3.6"
    )
    t = terminals.detect(e)
    assert t.name == "iTerm2"
    assert t.version(e) == "3.6"
    assert terminals.describe(e).endswith("tmux 3.5")


def test_version_is_not_tmuxs():
    e = env(TMUX="/tmp/t", TERM_PROGRAM="tmux", TERM_PROGRAM_VERSION="3.5", GHOSTTY_RESOURCES_DIR="/x")
    assert terminals.detect(e).version(e) == ""


def test_konsole_version():
    assert terminals.konsole_version(env(KONSOLE_VERSION="240802")) == "24.08.2"


def test_unknown_terminal_uses_term():
    assert terminals.detect(env(TERM="xterm-256color")).name == "xterm"


def test_versions_are_remembered_until_the_binary_changes(tmp_path, monkeypatch):
    binary = tmp_path / "ghostty"
    binary.write_text("")
    calls = []

    def fake_run(*cmd, **_kw):
        calls.append(cmd)
        return "Ghostty 1.4.0\n\nVersion\n  - channel: stable\n"

    monkeypatch.setattr(terminals, "run", fake_run)
    e = env(GHOSTTY_BIN_DIR=str(tmp_path), TMUX="/t", XDG_CACHE_HOME=str(tmp_path / "cache"))
    assert terminals.ghostty_version(e) == "1.4.0"
    assert terminals.ghostty_version(e) == "1.4.0"
    assert len(calls) == 1
    import os

    os.utime(binary, ns=(1, 1))  # a new ghostty
    assert terminals.ghostty_version(e) == "1.4.0"
    assert len(calls) == 2
