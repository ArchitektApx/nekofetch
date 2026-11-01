from pathlib import Path

import pytest

from nekofetch import renderers, terminals
from nekofetch.images import Image
from nekofetch.system import Env


@pytest.fixture
def image(tmp_path):
    files = {}
    for ext in ("gif", "png"):
        files[ext] = tmp_path / f"neko.{ext}"
        files[ext].write_bytes(b"x")
    return Image("neko", files)


def ctx(tmp_path, tools=(), **env_vars):
    which = {t: f"/bin/{t}" for t in tools}.get
    env = Env({"TERM": "xterm-256color", "PATH": "/bin", **env_vars}, which=which)
    return renderers.Context(env, tmp_path / "cache", 30, 16, Path("/ascii.txt"))


def choose(c, image, protocol=None):
    return renderers.choose(terminals.detect(c.env), image, c, protocol)


def test_ghostty_with_kitten_animates(tmp_path, image, monkeypatch):
    c = ctx(tmp_path, TERM_PROGRAM="ghostty")
    monkeypatch.setattr(Env, "kitten", lambda _self: "/opt/kitten")
    logo = choose(c, image)
    assert logo.renderer == "kitty"
    assert logo.args[logo.args.index("--logo") + 1].endswith(".gif")
    assert logo.env["PATH"].startswith(str(tmp_path / "cache/shim"))
    assert "--transfer-mode=file" in (tmp_path / "cache/shim/kitten").read_text()


def test_ssh_skips_the_file_transfer_shim(tmp_path, image, monkeypatch):
    c = ctx(tmp_path, TERM_PROGRAM="ghostty", SSH_CONNECTION="1 2 3 4")
    monkeypatch.setattr(Env, "kitten", lambda _self: "/opt/kitten")
    assert choose(c, image).env["PATH"].startswith("/opt")


def test_ghostty_without_kitten_takes_the_png(tmp_path, image, monkeypatch):
    monkeypatch.setattr(Env, "kitten", lambda _self: None)
    logo = choose(ctx(tmp_path, TERM_PROGRAM="ghostty"), image)
    assert logo.renderer == "kitty-direct"
    assert logo.args[3].endswith(".png")


def test_gif_only_image_moves_down_the_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(Env, "kitten", lambda _self: None)
    gif = tmp_path / "only.gif"
    gif.write_bytes(b"x")
    logo = choose(ctx(tmp_path, TERM_PROGRAM="ghostty"), Image.from_file(gif))
    assert logo.renderer == "ascii"  # no PNG, no chafa


def test_iterm_but_not_in_tmux(tmp_path, image):
    assert choose(ctx(tmp_path, TERM_PROGRAM="iTerm.app"), image).renderer == "iterm"
    assert choose(ctx(tmp_path, TERM_PROGRAM="iTerm.app", TMUX="/t"), image).renderer == "ascii"


def test_chafa_everywhere_else(tmp_path, image, monkeypatch):
    monkeypatch.setattr(renderers.Chafa, "rendered", lambda _self, _image, _ctx: tmp_path / "out.txt")
    assert choose(ctx(tmp_path, ("chafa",), TERM="alacritty"), image).renderer == "chafa"
    assert choose(ctx(tmp_path, ("chafa",), TERM="foot"), image).renderer == "sixel"


def test_forcing_ignores_the_environment_but_not_missing_tools(tmp_path, image):
    assert choose(ctx(tmp_path, TERM_PROGRAM="iTerm.app", TMUX="/t"), image, "iterm").renderer == "iterm"
    assert choose(ctx(tmp_path), image, "sixel").renderer == "ascii"  # no chafa
    assert choose(ctx(tmp_path), image, "none").renderer == "none"


def test_no_image_is_the_ascii_cat(tmp_path):
    assert choose(ctx(tmp_path, TERM_PROGRAM="iTerm.app"), None).renderer == "ascii"


def test_unknown_protocol(tmp_path, image):
    with pytest.raises(ValueError, match="carrier-pigeon"):
        choose(ctx(tmp_path), image, "carrier-pigeon")


def test_every_name_in_the_terminal_table_is_a_renderer():
    for t in terminals.TERMINALS:
        assert set(t.renderers) <= set(renderers.RENDERERS), t.name


def test_icat_in_tmux_needs_passthrough(tmp_path, image, monkeypatch):
    monkeypatch.setattr(Env, "kitten", lambda _self: "/opt/kitten")
    monkeypatch.setattr(Env, "tmux_passthrough", lambda _self: False)
    assert choose(ctx(tmp_path, TERM_PROGRAM="ghostty", TMUX="/t"), image).renderer == "ascii"
    monkeypatch.setattr(Env, "tmux_passthrough", lambda _self: True)
    assert choose(ctx(tmp_path, TERM_PROGRAM="ghostty", TMUX="/t"), image).renderer == "kitty"


def logo_file(logo):
    return logo.args[logo.args.index("--logo") + 1]


def test_bundled_cats_fall_back_to_block_art(tmp_path):
    data = Path(renderers.DATA)
    typing = Image.from_file(data / "images/neko-typing.png")
    small = renderers.Context(Env({"TERM": "xterm"}, which=lambda _n: None), tmp_path, 30, 16, Path("/a"), data, 100)
    logo = choose(small, typing)
    assert logo.renderer == "blocks"
    assert logo_file(logo).endswith("neko-typing-small.ans")
    wide = renderers.Context(small.env, tmp_path, 30, 16, Path("/a"), data, 200)
    assert logo_file(choose(wide, typing)).endswith("neko-typing-large.ans")


def test_your_own_images_get_no_block_art(tmp_path, image):
    assert choose(ctx(tmp_path), image).renderer == "ascii"


def test_every_bundled_cat_has_block_art():
    data = Path(renderers.DATA)
    for png in (data / "images").glob("*.png"):
        for size in ("small", "large"):
            assert (data / "blocks" / f"{png.stem}-{size}.ans").exists()
