from nekofetch import config


def test_defaults():
    conf, warnings = config.parse({})
    assert conf.image.width == 30
    assert conf.says.uwu == "april"
    assert not warnings


def test_valid_values_apply():
    conf, warnings = config.parse(
        {"image": {"order": "sorted", "width": 40}, "weather": {"location": "Vienna"}, "says": {"uwu": True}}
    )
    assert (conf.image.order, conf.image.width, conf.weather.location, conf.says.uwu) == ("sorted", 40, "Vienna", True)
    assert not warnings


def test_bad_values_fall_back_with_a_warning():
    conf, warnings = config.parse(
        {
            "image": {"width": "abc", "folder": 5, "order": "upside-down", "height": -1},
            "weather": {"refresh": "x", "enabled": "yes"},
            "says": {"uwu": 1},
            "nope": {},
        }
    )
    assert conf == config.Config()
    assert len(warnings) == 8


def test_unreadable_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_bytes(b"\xff\xfe[image]\n")
    conf, warnings = config.load(path)
    assert conf == config.Config()
    assert warnings


def test_missing_file(tmp_path):
    assert config.load(tmp_path / "nope.toml") == (config.Config(), [])


def test_dunder_sections_are_just_unknown():
    conf, warnings = config.parse({"__doc__": {"x": 1}})
    assert conf == config.Config()
    assert warnings == ["unknown section [__doc__]"]


def test_protocol_must_be_a_renderer():
    assert config.parse({"image": {"protocol": "sixel"}})[0].image.protocol == "sixel"
    assert config.parse({"image": {"protocol": "smoke-signals"}})[1]
