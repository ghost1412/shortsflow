import json

import pytest

from engine import case_options as co


def test_defaults_cover_every_option():
    values = co.parse()
    assert set(values) == {o.key for o in co.OPTIONS}
    assert values["theme"] == "dark" and values["manim"] is True and values["draft"] is False and values["formats"] == "16:9,9:16"


def test_pairs_switches_and_later_values_win():
    v = co.parse(["theme=neon", "draft", "manim=off", "theme=terminal", "formats=9:16, 16:9"])
    assert v["theme"] == "terminal" and v["draft"] is True and v["manim"] is False and v["formats"] == "9:16,16:9"
    assert co.parse(["draft=no"])["draft"] is False and co.parse(["draft=on"])["draft"] is True


def test_bad_keys_and_values_say_what_is_allowed():
    with pytest.raises(co.OptionError) as e:
        co.parse(["colour=red"])
    assert "Known:" in str(e.value) and "theme" in str(e.value)
    with pytest.raises(co.OptionError) as e:
        co.parse(["theme=rainbow"])
    assert "neon" in str(e.value)
    with pytest.raises(co.OptionError):
        co.parse(["formats=4:3"])
    with pytest.raises(co.OptionError):
        co.parse(["draft=maybe"])
    with pytest.raises(co.OptionError):
        co.parse(["background=C:/no/such/file.jpg"])


def test_help_lists_every_option():
    with pytest.raises(co.OptionError) as e:
        co.parse(["help"])
    text = str(e.value)
    assert all(o.key in text for o in co.OPTIONS) and "CASE options" in text


def test_a_settings_file_is_read_first_and_pairs_override_it(tmp_path):
    f = tmp_path / "series.json"
    f.write_text(json.dumps({"theme": "editorial", "formats": "16:9", "manim": False}), encoding="utf-8")
    v = co.parse(["theme=midnight"], file=str(f))
    assert v["theme"] == "midnight" and v["formats"] == "16:9" and v["manim"] is False
    f.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(co.OptionError):
        co.parse(file=str(f))
    with pytest.raises(co.OptionError):
        co.parse(file=str(tmp_path / "missing.json"))


def test_a_background_may_be_an_existing_file(tmp_path):
    img = tmp_path / "bg.jpg"
    img.write_bytes(b"x")
    assert co.parse([f"background={img}"])["background"] == str(img)
    assert co.parse(["background=images"])["background"] == "images"


def test_to_pairs_round_trips_what_differs_from_the_defaults():
    values = co.parse(["theme=neon", "draft", "manim=off", "resume=sessions/case_1"])
    pairs = co.to_pairs(values)
    assert sorted(pairs) == ["draft", "manim=off", "resume=sessions/case_1", "theme=neon"]
    assert co.parse(pairs) == values
    assert co.to_pairs(co.parse()) == []


def test_the_command_line_has_two_case_flags_not_one_per_option():
    from pathlib import Path
    main = (Path(__file__).resolve().parents[1] / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    import re
    flags = re.findall(r'add_argument\("(--case\w*)"', main)
    assert sorted(flags) == ["--case", "--case_file"]
