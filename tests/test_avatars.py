import json
import os
import re

import pytest

from engine import avatars as av

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_ready_made_presenter_is_clean_and_there_are_people_cats_a_dog_and_a_robot():
    kinds = set()
    for name, spec in av.PRESETS.items():
        cleaned = av.clean(spec)
        assert cleaned["name"] and av.load(name) == cleaned
        kinds.add(cleaned["kind"])
    assert kinds == set(av.KINDS) - {"photo"}                                                    # photo ones are only made from your own picture
    people = [av.clean(s) for s in av.PRESETS.values() if s["kind"] == "human"]
    assert any(p["lashes"] for p in people) and any(p["beard"] != "none" for p in people)      # looks of more than one gender
    assert len({p["skin"] for p in people}) >= 4                                                # and a range of skin tones


def test_clean_keeps_known_parts_only():
    out = av.clean({"kind": "dragon", "hair": "mohawk", "skin": "red", "eyeColor": "#ABCDEF", "lashes": "yes", "name": "<b>Bob</b>!!" + "x" * 40,
                    "evil": "<script>"})
    assert out["kind"] == "human" and out["hair"] == "short" and out["skin"] == av.DEFAULT["skin"] and out["eyeColor"] == "#abcdef"
    assert out["lashes"] is True and "<" not in out["name"] and len(out["name"]) <= 20 and "evil" not in out
    with pytest.raises(ValueError):
        av.clean(["not", "a", "dict"])


def test_off_unknown_and_saved_presenters(tmp_path):
    home = str(tmp_path)
    assert av.load("off") is None and av.load("") is None and av.load(None) is None
    with pytest.raises(ValueError, match="No presenter called"):
        av.load("nobody", home)
    key, path = av.save(home, "My Host", {"kind": "cat", "skin": "#112233", "name": ""})
    assert key == "my_host" and os.path.isfile(path)
    assert av.load("my_host", home)["kind"] == "cat" and av.load("my_host", home)["name"] == "My Host"
    assert "my_host" in av.names(home) and ("My Host (cat, saved)", "my_host") in av.choices(home)
    assert av.choices(home)[0] == ("Off (no presenter)", "off")
    with pytest.raises(ValueError, match="ready-made"):
        av.save(home, "maya", {})
    with pytest.raises(ValueError):
        av.save(home, "!!!", {})
    (tmp_path / "presenters" / "broken.json").write_text(json.dumps({"kind": "robot", "eyeColor": "javascript:"}), encoding="utf-8")
    assert av.load("broken", home)["eyeColor"] == av.DEFAULT["eyeColor"]           # a hand-edited file still passes only clean parts


def test_a_photo_answer_maps_to_parts_and_a_bad_answer_is_a_clear_error(tmp_path):
    answer = 'Here you go: {"skin": "Medium Deep", "hair": "curly", "hair_color": "black", "eye_color": "brown", "beard": "full", "glasses": "square", "lashes": false}'
    spec = av.from_answer(answer, base=av.clean({"outfit": "#123456"}))
    assert spec["skin"] == av.SKIN_TONES["medium deep"] and spec["hair"] == "curly" and spec["beard"] == "full" and spec["glasses"] == "square"
    assert spec["outfit"] == "#123456" and spec["kind"] == "human"
    with pytest.raises(ValueError, match="did not describe"):
        av.from_answer("I cannot help with that.")
    photo = tmp_path / "face.jpg"
    from PIL import Image
    Image.new("RGB", (1600, 1200), "#c68e64").save(photo)
    seen = {}

    def ask(frames, prompt):
        seen.update(n=len(frames), size=len(frames[0]), prompt=prompt)
        return answer
    spec, msg = av.suggest_from_photo(str(photo), ask=ask)
    assert spec["hair"] == "curly" and seen["n"] == 1 and "JSON" in seen["prompt"] and "Check it" in msg
    with pytest.raises(ValueError, match="Choose a photo"):
        av.suggest_from_photo(str(tmp_path / "none.jpg"), ask=ask)


def test_the_parts_lists_match_the_drawing():
    tsx = open(os.path.join(ROOT, "remotion-video", "src", "Presenter.tsx"), encoding="utf-8").read()
    for key, values in av.CHOICES.items():
        found = re.search(key + r': z\.enum\(\[([^\]]*)\]\)', tsx)
        assert found, key
        assert tuple(re.findall(r'"([^"]+)"', found.group(1))) == values, key
    for key in av.COLOURS:
        assert f"{key}: hex.default" in tsx


def test_the_presenter_travels_from_the_option_to_the_props(monkeypatch, tmp_path):
    from engine import case_options, case_render
    from shortsflow import web_args
    monkeypatch.chdir(tmp_path)
    assert case_options.parse(["avatar=Maya"])["avatar"] == "maya"
    assert case_options.parse([])["avatar"] == "off"
    with pytest.raises(Exception, match="No presenter called"):
        case_options.parse(["avatar=nobody"])
    args = web_args.case_args("Topic", avatar="miso")
    assert "avatar=miso" in args and not any(a.startswith("avatar=") for a in web_args.case_args("Topic"))
    script = {"title": "T", "sections": [{"title": "A", "scene": "quote", "on_screen": ["x"], "narration": "x"}], "sources": []}
    props = case_render.build_props(script, [(1.8, 5.0)], [[]], avatar=av.load("bolt"))
    assert props["avatar"]["kind"] == "robot"
    assert "avatar" not in case_render.build_props(script, [(1.8, 5.0)], [[]])


def test_the_preview_command_and_its_failure(tmp_path):
    calls = {}

    class R:
        returncode = 0
        stderr = ""

    def run(cmd, **kw):
        calls.update(cmd=cmd, cwd=kw["cwd"])
        props = [c for c in (cmd.split() if isinstance(cmd, str) else cmd) if c.startswith("--props=")][0].split("=", 1)[1]
        calls["props"] = json.load(open(os.path.join(kw["cwd"], props), encoding="utf-8"))
        return R()
    out = av.render_preview(av.load("luna"), str(tmp_path / "p.mp4"), remotion_dir=str(tmp_path), run=run)
    assert out.endswith("p.mp4") and "PresenterCard" in str(calls["cmd"]) and calls["props"]["avatar"]["kind"] == "cat"
    assert calls["props"]["words"] and not [f for f in os.listdir(tmp_path) if f.startswith("temp_props")]      # the props file is removed
    R.returncode, R.stderr = 1, "boom"
    with pytest.raises(RuntimeError, match="boom"):
        av.render_preview(av.load("luna"), str(tmp_path / "p.mp4"), remotion_dir=str(tmp_path), run=run)


def test_pictures_of_presenters(tmp_path):
    for name in av.PRESETS:
        assert os.path.isfile(os.path.join(av.THUMBS, name + ".jpg")), name
        assert av.thumbnail(name).endswith(name + ".jpg")
    assert av.thumbnail("off") is None and av.thumbnail("nobody") is None
    home = str(tmp_path)
    key, _ = av.save_photo(home, "Me", _jpg(tmp_path))
    assert av.thumbnail(key, home).endswith("me.jpg")


def _jpg(tmp_path):
    from PIL import Image
    p = tmp_path / "face.jpg"
    Image.new("RGB", (400, 500), "#c68e64").save(p)
    return str(p)
