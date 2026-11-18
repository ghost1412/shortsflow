import json

import pytest

from engine.mode_options import Option, OptionError, OptionSet


def demo():
    def even(raw):
        if not raw.isdigit() or int(raw) % 2:
            raise OptionError("'size' must be an even number")
        return int(raw)
    return OptionSet("demo", [Option("look", "choice", "plain", "the look", ("plain", "fancy")), Option("fast", "switch", False, "go fast"),
                              Option("size", "text", 4, "an even size", check=even), Option("folder", "path", "", "a folder")])


def test_a_new_mode_gets_parsing_help_defaults_and_validation_from_its_schema():
    s = demo()
    assert s.parse() == {"look": "plain", "fast": False, "size": 4, "folder": ""}
    v = s.parse(["look=fancy", "fast", 'folder="C:/x y"', "size=10"])
    assert v == {"look": "fancy", "fast": True, "size": 10, "folder": "C:/x y"}
    with pytest.raises(OptionError) as e:
        s.parse(["size=3"])
    assert "even" in str(e.value)
    with pytest.raises(OptionError) as e:
        s.parse(["help"])
    assert str(e.value).startswith("DEMO options (use --demo KEY=VALUE") and "fancy" in str(e.value)
    with pytest.raises(OptionError) as e:
        s.parse(["nope=1"])
    assert "Unknown DEMO option" in str(e.value) and "look" in str(e.value)


def test_from_args_reads_the_flag_named_after_the_mode_and_its_file(tmp_path):
    class Args:
        demo = ["fast"]
        demo_file = str(tmp_path / "s.json")
    (tmp_path / "s.json").write_text(json.dumps({"look": "fancy", "fast": False}), encoding="utf-8")
    v = demo().from_args(Args())
    assert v["look"] == "fancy" and v["fast"] is True                  # the pairs win over the file


def test_round_trip_and_duplicate_keys():
    s = demo()
    values = s.parse(["look=fancy", "fast"])
    assert sorted(s.to_pairs(values)) == ["fast", "look=fancy"] and s.parse(s.to_pairs(values)) == values
    with pytest.raises(ValueError):
        OptionSet("dup", [Option("a", "text", "", ""), Option("a", "text", "", "")])
