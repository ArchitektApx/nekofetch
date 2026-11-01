import pytest

from nekofetch import shell
from nekofetch.system import Env


def current(env: Env) -> shell.Shell:
    sh = shell.current(env)
    assert sh is not None
    return sh


def test_add_is_idempotent_and_remove_leaves_the_rest(tmp_path):
    env = Env({"HOME": str(tmp_path), "SHELL": "/bin/zsh"})
    rc = tmp_path / ".zshrc"
    rc.write_text('alias nf="nekofetch -p ascii" # nekofetch\n')
    sh = current(env)
    shell.add_hook(sh, env)
    shell.add_hook(sh, env)
    assert rc.read_text().count(shell.MARK) == 1
    assert shell.remove_hooks(env) == [rc]
    assert rc.read_text() == 'alias nf="nekofetch -p ascii" # nekofetch\n'


def test_zdotdir_and_symlinks_survive(tmp_path):
    zd = tmp_path / "zd"
    zd.mkdir()
    real = tmp_path / "dotfiles-zshrc"
    real.write_text("export A=1\n")
    (zd / ".zshrc").symlink_to(real)
    env = Env({"HOME": str(tmp_path), "ZDOTDIR": str(zd), "SHELL": "/usr/bin/zsh"})
    shell.add_hook(current(env), env)
    assert shell.MARK in real.read_text()
    shell.remove_hooks(env)
    assert (zd / ".zshrc").is_symlink()
    assert real.read_text() == "export A=1\n"


def test_fish(tmp_path):
    env = Env({"HOME": str(tmp_path), "SHELL": "/usr/bin/fish"})
    path = shell.add_hook(current(env), env)
    assert path == tmp_path / ".config/fish/config.fish"
    assert "status is-interactive" in path.read_text()


def test_never_clobbers_what_it_cannot_read(tmp_path):
    env = Env({"HOME": str(tmp_path), "SHELL": "/bin/zsh"})
    rc = tmp_path / ".zshrc"
    rc.write_bytes(b"export CAFE=caf\xe9\n")
    rc.chmod(0o600)
    shell.add_hook(current(env), env)
    assert rc.read_bytes().startswith(b"export CAFE=caf\xe9\n")
    assert rc.stat().st_mode & 0o777 == 0o600  # permissions survive
    shell.remove_hooks(env)
    assert rc.read_bytes() == b"export CAFE=caf\xe9\n"


def test_unreadable_rc_is_left_alone(tmp_path):
    env = Env({"HOME": str(tmp_path), "SHELL": "/bin/zsh"})
    rc = tmp_path / ".zshrc"
    rc.write_text("secret\n")
    rc.chmod(0o200)
    try:
        with pytest.raises(OSError, match="Permission denied"):
            shell.add_hook(current(env), env)
    finally:
        rc.chmod(0o600)
    assert rc.read_text() == "secret\n"


def test_new_bash_profile_keeps_loading_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(shell.sys, "platform", "darwin")
    env = Env({"HOME": str(tmp_path), "SHELL": "/bin/bash"})
    (tmp_path / ".profile").write_text("export PATH=x\n")
    path = shell.add_hook(current(env), env)
    assert path.name == ".bash_profile"
    assert path.read_text().startswith("[ -f ~/.profile ] && . ~/.profile")
    shell.remove_hooks(env)
    assert not path.exists()  # created by us, gone again


def test_fish_follows_xdg_config_home(tmp_path):
    env = Env({"HOME": str(tmp_path), "SHELL": "/usr/bin/fish", "XDG_CONFIG_HOME": str(tmp_path / "xdg")})
    assert current(env).rc(env) == tmp_path / "xdg/fish/config.fish"
