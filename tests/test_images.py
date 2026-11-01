from pathlib import Path

from nekofetch import images
from nekofetch.config import ImageConfig
from nekofetch.paths import Paths


def touch(folder: Path, *names):
    folder.mkdir(parents=True, exist_ok=True)
    for n in names:
        (folder / n).write_bytes(b"x")


def test_files_with_one_name_are_one_image(tmp_path):
    touch(tmp_path, "a.gif", "a.png", "b.jpg", "notes.txt", ".hidden.png")
    found = images.scan(tmp_path)
    assert [(i.name, sorted(i.files)) for i in found] == [("a", ["gif", "png"]), ("b", ["jpg"])]


def test_best_format(tmp_path):
    touch(tmp_path, "a.gif", "a.png")
    a = images.scan(tmp_path)[0]
    png, gif = a.best(("png",)), a.best(("webp", "gif"))
    assert png is not None
    assert png.suffix == ".png"
    assert gif is not None
    assert gif.suffix == ".gif"
    assert a.best(("webp",)) is None
    assert a.best(None) is not None


def test_bundled_images_have_a_png_for_every_gif():
    for image in images.scan(Paths.from_env().data / "images"):
        assert set(image.files) == {"gif", "png"}, image.name


def test_defaults_step_aside(tmp_path):
    paths = Paths(config=tmp_path, cache=tmp_path / "cache")
    bundled = len(images.collection(ImageConfig(), paths))
    assert bundled >= 6
    touch(tmp_path / "images", "mine.png")
    assert [i.name for i in images.collection(ImageConfig(), paths)] == ["mine"]
    assert len(images.collection(ImageConfig(defaults="always"), paths)) == bundled + 1


def test_sorted_order_cycles(tmp_path):
    touch(tmp_path, "a.png", "b.png", "c.png")
    found = images.scan(tmp_path)
    state = tmp_path / "state"
    picks = [images.pick(found, "sorted", state) for _ in range(4)]
    names = [i.name for i in picks if i is not None]
    assert names == ["a", "b", "c", "a"]


def test_add_file_never_overwrites(tmp_path):
    touch(tmp_path / "src", "cat.png")
    dest = tmp_path / "images"
    first = images.add_file(tmp_path / "src/cat.png", dest)
    second = images.add_file(tmp_path / "src/cat.png", dest)
    assert first.name == "cat.png"
    assert second.name == "cat-1.png"
