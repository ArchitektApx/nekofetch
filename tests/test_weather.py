from nekofetch.config import WeatherConfig
from nekofetch.weather import Weather, format_line


def test_format():
    line = format_line(["☁️", "Overcast", "+7°C", "→12km/h", "🌗", "07:01:00", "16:40:00"], now="12:00:00")
    assert "󰖐 Overcast" in line
    assert "W→12km/h" in line
    assert "+7°C" in line


def test_sun_at_night_is_a_moon_but_only_here():
    parts = ["☀️", "Clear", "+2°C", "↓3km/h", "🌕", "07:00:00", "17:00:00"]
    assert format_line(parts, now="23:00:00").startswith("󰖔 Clear")
    assert format_line(parts, local=False, now="23:00:00").startswith("󰖙 Clear")


def test_url(tmp_path):
    w = Weather(WeatherConfig(location="New York", units="imperial"), cache_dir=tmp_path)
    assert w.url.startswith("https://wttr.in/New+York?u&")


def test_cache_belongs_to_a_location(tmp_path):
    here = Weather(WeatherConfig(), tmp_path)
    (tmp_path / "weather.txt").write_text(f"sunny\n{here.key}\n")
    assert here.cached()[0] == "sunny"
    assert Weather(WeatherConfig(location="Vienna"), tmp_path).cached() == ("", None)


def test_stale_cache_refreshes_in_the_background_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **_k: calls.append(a))
    w = Weather(WeatherConfig(), tmp_path)
    assert "asking the sky" in w.line()
    w.line()
    assert len(calls) == 1  # the lock holds off the second


def test_disabled(tmp_path):
    assert Weather(WeatherConfig(enabled=False), tmp_path).line() == ""


def test_offline_with_nothing_cached_hides_the_row(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: None)
    (tmp_path / "weather.lock").write_text("failed")
    assert Weather(WeatherConfig(), tmp_path).line() == ""


def test_old_weather_says_how_old(tmp_path, monkeypatch):
    import os
    import time

    monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: None)
    w = Weather(WeatherConfig(), tmp_path)
    w.cache.write_text(f"sunny\n{w.key}\n")
    assert w.line() == "sunny"
    three_hours_ago = time.time() - 3 * 3600
    os.utime(w.cache, (three_hours_ago, three_hours_ago))
    assert w.line().endswith("3h ago\x1b[0m")


def test_ago():
    from nekofetch.weather import ago

    assert ago(3 * 3600) == "3h ago"
    assert ago(50 * 3600) == "2d ago"
