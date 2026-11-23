"""The cartoon backgrounds of the case explainer (engine/case_cartoon.py): prompts, the SVG check, the order of the ways, caching, fallbacks."""
import os

from engine import case_cartoon as cc, case_options

GOOD_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><rect width='10' height='10' fill='#9cf'/>"
            + "".join(f"<circle cx='{i}' cy='5' r='1' fill='#fc0' stroke='#222'/>" for i in range(6)) + "</svg>")


def test_prompt_is_phrase_plus_fixed_style_and_drops_odd_characters():
    p = cc.prompt_for("  server <rack>  ")
    assert p.startswith("server rack, ") and "no text" in p
    assert cc.prompt_for("") == "" and cc.prompt_for(None) == ""


def test_order_of_ways():
    assert cc.order("auto", True, True) == ["local", "cloud", "drawn"]
    assert cc.order("auto", False, False) == ["drawn"]
    assert cc.order("cloud", False, True) == ["cloud"]


def test_make_image_falls_through_and_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "local_ready", lambda: False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    calls = []
    makers = {"local": lambda p: calls.append("local"), "cloud": lambda p: calls.append("cloud"),
              "drawn": lambda p: calls.append("drawn") or GOOD_SVG}
    path = cc.make_image("red fox", str(tmp_path), "16:9", "auto", makers=makers)
    assert calls == ["cloud", "drawn"] and path.endswith(".svg") and os.path.isfile(path)
    assert cc.make_image("red fox", str(tmp_path), "16:9", "auto", makers=makers) == path and calls == ["cloud", "drawn"]   # cached: no new calls


def test_named_way_does_not_fall_back(tmp_path, monkeypatch):
    makers = {"local": lambda p: None, "cloud": lambda p: None, "drawn": lambda p: GOOD_SVG}
    assert cc.make_image("red fox", str(tmp_path), "16:9", "cloud", makers=makers) is None


def test_attach_gives_one_picture_per_phrase_and_skips_failures(tmp_path):
    script = {"sections": [{"footage": ["red fox", "blue sea"]}, {"footage": []}, {"footage": "red fox"}]}
    makers = {"local": lambda p: None, "cloud": lambda p: b"png" if "fox" in p else None, "drawn": lambda p: None}
    out = cc.attach(script, str(tmp_path), "16:9", "cloud", cache_dir=str(tmp_path), makers=makers)
    assert [len(x) if x else 0 for x in out] == [1, 0, 1] and out[0][0]["kind"] == "cartoon"


def test_make_cloud_tries_gemini_then_hugging_face(monkeypatch):
    import base64

    class R:
        def __init__(self, ok, body=None, content=b"", ctype=""):
            self.ok, self._b, self.content, self.headers = ok, body, content, {"content-type": ctype}

        def raise_for_status(self):
            if not self.ok:
                raise RuntimeError("429")

        def json(self):
            return self._b

    def post(url, **kw):
        if "generativelanguage" in url:
            return R(False)
        return R(True, content=b"IMG", ctype="image/png")

    monkeypatch.setattr(cc, "_hugging_face", lambda prompt, aspect, key, post: b"IMG")
    assert cc.make_cloud("p", "16:9", post=post, env={"GEMINI_API_KEY": "a", "HF_API_KEY": "b"}) == b"IMG"
    assert cc.make_cloud("p", "16:9", post=post, env={}) is None

    def gem(url, **kw):
        return R(True, {"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(b"G").decode()}}]}}]})
    assert cc.make_cloud("p", "9:16", post=gem, env={"GEMINI_API_KEY": "a"}) == b"G"


def test_option_is_in_the_schema():
    opts = case_options.parse(["background=cartoon", "cartoon=drawn"])
    assert opts["background"] == "cartoon" and opts["cartoon"] == "drawn"
    assert case_options.parse([])["cartoon"] == "auto"


def test_ways_can_be_left_out_or_turned_off(tmp_path, monkeypatch):
    assert cc.order("local,drawn", True, True) == ["local", "drawn"]
    assert cc.order("drawn,cloud", True, False) == ["drawn", "cloud"]
    assert cc.order("off", True, True) == []
    opts = case_options.parse(["cartoon=local,drawn"])
    assert opts["cartoon"] == "local,drawn"
    assert case_options.parse(["cartoon=OFF"])["cartoon"] == "off"
    import pytest
    from engine.mode_options import OptionError
    with pytest.raises(OptionError):
        case_options.parse(["cartoon=cloud,pigeon"])
    calls = []
    makers = {"local": lambda p: None, "cloud": lambda p: calls.append("cloud") or b"x", "drawn": lambda p: None}
    assert cc.make_image("red fox", str(tmp_path), "16:9", "local,drawn", makers=makers) is None and calls == []     # cloud left out: never called
    script = {"sections": [{"footage": ["red fox"]}]}
    assert cc.attach(script, str(tmp_path), "16:9", "off", cache_dir=str(tmp_path), makers=makers) == [None]


def test_drawn_way_picks_a_kit_icon_and_draws_it_on_the_canvas_of_the_video_shape():
    import json
    import xml.etree.ElementTree as ET
    reply = json.dumps({"setting": "space", "items": [{"kind": "black hole", "color": "orange"}]})
    for aspect, size in (("16:9", "1024"), ("9:16", "576")):
        svg = cc.make_drawn("glowing ring", aspect, lambda p: reply)
        root = ET.fromstring(svg)
        assert root.get("width") == size and "<ellipse" in svg and svg.count("<svg") == 1


def test_drawn_way_draws_an_icon_the_kit_lacks_and_gives_up_when_the_model_fails(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("SHORTSFLOW_ICONS", str(tmp_path))
    drawing = "<g>" + "<circle cx='0' cy='0' r='40' fill='#fff' stroke='#1f2937'/>" * 5 + "</g>"
    replies = iter([json.dumps({"items": [{"kind": "unicorn"}]}), json.dumps({"svg": drawing})])
    svg = cc.make_drawn("odd", "16:9", lambda p: next(replies))
    assert svg and (tmp_path / "unicorn.v2.svg").is_file()
    assert cc.make_drawn("odd", "16:9", lambda p: 1 / 0) is None
