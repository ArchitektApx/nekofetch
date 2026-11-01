from pathlib import Path

from nekofetch.paths import Paths, xdg


def test_xdg_variables_are_respected():
    env = {"HOME": "/home/neko", "XDG_CONFIG_HOME": "/cfg", "XDG_CACHE_HOME": "/tmp/c"}
    paths = Paths.from_env(env)
    assert paths.config == Path("/cfg/nekofetch")
    assert paths.cache == Path("/tmp/c/nekofetch")


def test_unset_empty_and_relative_values_fall_back():
    for value in (None, "", "relative/dir"):
        env = {"HOME": "/home/neko"}
        if value is not None:
            env["XDG_CONFIG_HOME"] = env["XDG_DATA_HOME"] = value
        assert xdg(env, "XDG_CONFIG_HOME") == Path("/home/neko/.config")
        assert xdg(env, "XDG_DATA_HOME") == Path("/home/neko/.local/share")


def test_user_files_override_bundled(tmp_path):
    paths = Paths(config=tmp_path, cache=tmp_path / "cache")
    assert paths.user_or_default("says.toml").parent == paths.data
    (tmp_path / "says.toml").write_text("")
    assert paths.user_or_default("says.toml") == tmp_path / "says.toml"
