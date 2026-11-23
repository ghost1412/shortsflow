"""The explaining pictures (engine/art_kit.py, engine/case_art.py): the icon kit, the scene spec check, badge positions, caching, fallbacks."""
import json
import xml.etree.ElementTree as ET

from engine import art_kit as kit, case_art as art

SPEC = {"setting": "night", "layout": "row", "items": [{"kind": "hacker", "color": "red"}, {"kind": "server", "color": "blue", "mark": "warning"},
                                                        {"kind": "database", "color": "teal", "mark": "cross", "many": True}], "links": [[1, 2], [2, 3]]}
SECTION = {"title": "What happened", "narration": "An attacker hit a server.", "on_screen": ["Attacker", "Server", "Stolen data"]}


def test_every_icon_is_valid_svg_in_every_colour_and_mood():
    for name, fn in kit.ICONS.items():
        for color in kit.COLORS.values():
            for mood in kit.MOODS:
                ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{fn(color, mood)}</svg>')
    assert set(kit.HELP) == set(kit.ICONS) and all(m in kit.ICONS for m in kit.MARKS)


def test_compose_gives_valid_svg_and_one_badge_inside_the_picture_per_item():
    for aspect in ("16:9", "1:1"):
        for n in (2, 3, 4):
            for layout in kit.LAYOUTS:
                spec = {"setting": "city", "layout": layout, "items": [{"kind": "cloud", "color": "blue"}] * n, "links": [{"from": 1, "to": 2}]}
                svg, points = kit.compose(spec, aspect)
                ET.fromstring(svg)
                assert len(points) == n and all(0 <= x <= 100 and 0 <= y <= 100 for x, y in points)
                assert len(set(points)) == n                         # no two badges on the same spot


def test_badges_never_overlap_each_other():
    for aspect in ("16:9", "1:1"):
        for n in (2, 3, 4):
            _, points = kit.compose({"items": [{"kind": "gear", "color": "blue"}] * n}, aspect)
            for i in range(n):
                for j in range(i + 1, n):
                    assert abs(points[i][0] - points[j][0]) > 10 or abs(points[i][1] - points[j][1]) > 10


def test_check_spec_accepts_a_good_reply_and_repairs_small_things():
    spec, problem = art.check_spec(json.dumps(SPEC), 3)
    assert spec and not problem and spec["items"][2]["many"] and spec["links"][0] == {"from": 1, "to": 2, "dashed": False}
    odd = {"setting": "moon", "layout": "triangle", "items": [{"kind": "Attacker", "color": "chartreuse", "mood": "furious"}, {"kind": "padlock"}], "links": [[1, 1], [1, 9], [2, 1]]}
    spec, _ = art.check_spec("Here you go:\n" + json.dumps(odd), 2)
    assert spec["items"][0]["kind"] == "hacker" and spec["items"][0]["color"] in kit.COLORS and "mood" not in spec["items"][0]
    assert spec["items"][1]["kind"] == "lock" and spec["setting"] == "office" and spec["layout"] == "row"      # triangle needs exactly 3 items
    assert spec["links"] == [{"from": 2, "to": 1, "dashed": False}]


def test_check_spec_names_the_problem():
    assert art.check_spec("no json", 3)[0] is None
    spec, problem = art.check_spec(json.dumps({"items": [{"kind": "server"}]}), 3)
    assert spec is None and "1 items" in problem
    spec, problem = art.check_spec(json.dumps({"items": [{"kind": "!!"}, {"kind": "server"}]}), 2)
    assert spec is None and "short plain name" in problem
    spec, problem = art.check_spec(json.dumps({"items": [{"kind": "Stone Pyramid"}, {"kind": "server"}]}), 2)          # not in the kit: it will be drawn
    assert spec["items"][0]["kind"] == "stone_pyramid" and spec["items"][0]["custom"] and not spec["items"][1].get("custom")


def test_check_spec_reads_a_wrapped_reply():
    assert art.check_spec(json.dumps({"picture": SPEC}), 3)[0]["items"][0]["kind"] == "hacker"


def test_make_retries_once_with_the_problem_and_caches(tmp_path):
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return "nonsense" if len(calls) == 1 else json.dumps(SPEC)
    got = art.make(SECTION, "Topic", "16:9", ask, str(tmp_path))
    assert got and len(calls) == 2 and "could not be used" in calls[1]
    assert list(got["points"]) == SECTION["on_screen"] and all(len(v) == 2 for v in got["points"].values())
    assert art.make(SECTION, "Topic", "16:9", lambda p: 1 / 0, str(tmp_path))["points"] == got["points"]       # cached: the model is not asked again
    assert art.make(SECTION, "Topic", "9:16", lambda p: json.dumps(SPEC), str(tmp_path))["path"] != got["path"]  # another shape, another picture


def test_make_gives_up_after_two_bad_answers_and_with_too_few_labels(tmp_path):
    assert art.make(SECTION, "T", "16:9", lambda p: "nope", str(tmp_path)) is None
    assert art.make(dict(SECTION, on_screen=["Only one"]), "T", "16:9", lambda p: json.dumps(SPEC), str(tmp_path)) is None


def test_attach_only_draws_illustration_sections_and_only_when_drawn_is_allowed(tmp_path):
    script = {"title": "T", "sections": [dict(SECTION, scene="illustration"), dict(SECTION, scene="checklist")]}
    ask = lambda p: json.dumps(SPEC)
    out = art.attach(script, str(tmp_path), "16:9", "auto", ask, cache_dir=str(tmp_path))
    assert out[0] and out[1] is None
    assert art.attach(script, str(tmp_path), "16:9", "cloud", ask, cache_dir=str(tmp_path)) == [None, None]
    assert art.attach(script, str(tmp_path), "16:9", "off", ask, cache_dir=str(tmp_path)) == [None, None]


def test_build_props_puts_art_on_the_section_and_falls_back_to_a_checklist():
    from engine import case_render as cr
    script = {"title": "T", "sections": [dict(SECTION, id="a", scene="illustration"), dict(SECTION, id="b", scene="illustration")], "sources": []}
    pic = {"path": "x.svg", "points": {"Attacker": (10.0, 20.0), "Server": (40.0, 20.0), "Stolen data": (70.0, 20.0)}}
    props = cr.build_props(script, [(0, 5), (5, 10)], [[], []], art=[pic, None])
    first, second = props["sections"]
    assert first["scene"] == "illustration" and first["art"]["src"] == "x.svg" and len(first["art"]["points"]) == len(first["labels"]) == 3
    assert second["scene"] == "checklist" and "art" not in second
    by_label = dict(zip(first["labels"], first["art"]["points"]))
    assert by_label["Server"] == {"x": 40.0, "y": 20.0}                       # a badge stays with its label even when the labels are reordered


def test_layers_are_separate_transparent_pictures_that_add_up_to_the_scene():
    checked, _ = art.check_spec(json.dumps(SPEC), 3)
    layered = kit.compose_layers(checked, "16:9")
    for svg in [layered["background"], *layered["items"], *(l["svg"] for l in layered["links"])]:
        ET.fromstring(svg)
    assert len(layered["items"]) == 3 and len(layered["links"]) == 2 and len(layered["centres"]) == 3
    assert "<rect" not in layered["items"][0].split("<g", 1)[0]           # an item layer has no background of its own
    whole, badges = kit.compose(checked, "16:9")
    assert badges == layered["badges"] and whole.count("<g transform") >= 3


def test_make_writes_layer_files_and_build_props_keeps_them_with_their_labels(tmp_path):
    from engine import case_render as cr
    got = art.make(SECTION, "T", "16:9", lambda p: json.dumps(SPEC), str(tmp_path))
    assert list(got["items"]) == SECTION["on_screen"] and [(l["from"], l["to"]) for l in got["links"]] == [("Attacker", "Server"), ("Server", "Stolen data")]
    assert all(__import__("os").path.isfile(p) for p in [got["path"], *got["items"].values(), *(l["path"] for l in got["links"])])
    script = {"title": "T", "sections": [dict(SECTION, id="a", scene="illustration")], "sources": []}
    props = cr.build_props(script, [(0, 5)], [[]], art=[got])
    pic = props["sections"][0]["art"]
    labels = props["sections"][0]["labels"]
    assert len(pic["items"]) == 3 and len(pic["links"]) == 2
    assert [labels[l["from"]] for l in pic["links"]] == ["Attacker", "Server"] and [labels[l["to"]] for l in pic["links"]] == ["Server", "Stolen data"]
    assert pic["items"][labels.index("Server")]["src"] == got["items"]["Server"]


def test_a_thing_the_kit_lacks_is_drawn_saved_and_used_and_a_failure_falls_back(tmp_path):
    from engine import art_icons
    drawing = json.dumps({"svg": "<g><rect x='-60' y='0' width='120' height='70' fill='#f59e0b' stroke='#1f2937' stroke-width='6'/>" + "<circle cx='0' cy='-20' r='30' fill='#fff'/>" * 3 + "</g>"})
    spec, _ = art.check_spec(json.dumps({"items": [{"kind": "vaccine"}, {"kind": "server"}]}), 2)
    asked = []
    out = art.resolve_custom(spec, lambda p: asked.append(p) or drawing, str(tmp_path))
    assert out["items"][0]["kind"] == "vaccine" and "custom" not in out["items"][0] and len(asked) == 1
    svg, _ = kit.compose(out, "16:9")
    ET.fromstring(svg)
    assert (tmp_path / "vaccine.v2.svg").is_file()
    spec, _ = art.check_spec(json.dumps({"items": [{"kind": "vaccine"}, {"kind": "server"}]}), 2)
    art.resolve_custom(spec, lambda p: 1 / 0, str(tmp_path))                     # saved already: the model is not asked again
    assert spec["items"][0]["kind"] == "vaccine"
    spec, _ = art.check_spec(json.dumps({"items": [{"kind": "pyramid"}, {"kind": "server"}]}), 2)
    art.resolve_custom(spec, lambda p: "no drawing", str(tmp_path))
    assert spec["items"][0]["kind"] == art.FALLBACK


def test_icon_check_keeps_flat_shapes_only_and_near_the_box():
    from engine import art_icons
    good = "<g>" + "<circle cx='0' cy='0' r='40' fill='#fff' stroke='#1f2937'/>" * 5 + "</g>"
    assert art_icons.clean(json.dumps({"svg": good}))
    assert art_icons.clean("<svg xmlns='http://www.w3.org/2000/svg' viewBox='-100 -100 200 200'>" + good + "</svg>")
    assert "onclick" not in art_icons.clean(good.replace("<circle ", "<circle onclick='x()' ", 1))
    assert art_icons.clean(good.replace("</g>", "<script>alert(1)</script></g>")) is None
    assert art_icons.clean(good.replace("</g>", "<text>hi</text></g>")) is None
    assert art_icons.clean(good.replace("</g>", "<image href='x'/></g>")) is None
    assert art_icons.clean("<circle r='9'/><circle r='9'/>") is None                        # too few shapes
    assert art_icons.clean(good.replace("r='40'", "r='400'")) is None                       # far outside the 200 x 200 box
    assert art_icons.clean("<g><rect></g>") is None and art_icons.clean("") is None


def test_icon_check_keeps_rectangle_sizes_and_rejects_scratches_and_sizeless_rectangles():
    from engine import art_icons
    body = "<rect x='-60' y='-60' width='120' height='120' rx='8' fill='#3b82f6' stroke='#1f2937'/>" + "<circle cx='0' cy='0' r='30' fill='#fff'/>" * 3
    out = art_icons.clean("<g>" + body + "</g>")
    assert out and 'width="120"' in out and 'height="120"' in out                    # these were stripped once: every rectangle vanished
    assert art_icons.clean("<g>" + body.replace(" width='120' height='120'", "") + "</g>") is None      # a rectangle with no size draws nothing
    assert art_icons.clean("<g>" + "<path d='M-80 -80 L80 80' fill='none' stroke='#000'/>" * 6 + "</g>") is None   # outlines only: scratches
    assert art_icons.clean("<g>" + "<circle cx='0' cy='0' r='10' fill='#fff'/>" * 5 + "</g>") is None            # a speck


def test_a_rough_stand_in_is_replaced_by_the_thing_to_draw():
    spec, _ = art.check_spec(json.dumps({"items": [{"kind": "flask", "draw": "Syringe"}, {"kind": "bug", "draw": "bug"}, {"kind": "shield"}]}), 3)
    assert spec["items"][0]["kind"] == "syringe" and spec["items"][0]["custom"]          # drawn instead of the flask
    assert spec["items"][1]["kind"] == "bug" and not spec["items"][1].get("custom")      # the thing IS a kit icon: no drawing needed
    assert spec["items"][2]["kind"] == "shield"
    spec, _ = art.check_spec(json.dumps({"items": [{"kind": "flask", "draw": "!!"}, {"kind": "bug"}]}), 2)
    assert spec["items"][0]["kind"] == "flask"                                           # an unusable name is ignored


def test_the_picture_is_planned_in_the_order_the_narrator_reaches_the_labels(tmp_path):
    from engine import case_render as cr
    seen = []

    def ask(prompt):
        seen.append(prompt)
        return json.dumps(SPEC)
    labels = ["Server", "Attacker", "Stolen data"]                                   # the script order
    spoken = ["An", "attacker", "hit", "a", "server", "and", "took", "stolen", "data"]
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(spoken)]
    script = {"title": "T", "sections": [dict(SECTION, id="a", scene="illustration", on_screen=labels)]}
    cr.attach_art(script, str(tmp_path), "16:9", "auto", ask, words=[words], timing=[(0, 10)], cache_dir=str(tmp_path))
    asked = seen[0]
    assert asked.index("1. Attacker") < asked.index("2. Server") < asked.index("3. Stolen data")
    assert script["sections"][0]["on_screen"] == labels                              # the script itself is not changed


def test_labels_match_the_spoken_word_even_when_one_is_plural():
    from engine import case_render as cr
    spoken = ["Attackers", "use", "QR", "codes", "and", "automated", "calls", "and", "texts"]
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(spoken)]
    assert cr._first_spoken("QR code", words) == 3 and cr._first_spoken("Phone call", words) == 6
    labels, cues = cr.spoken_order(["Phone call", "QR code"], words, duration=10)
    assert labels == ["QR code", "Phone call"] and cues[0] < cues[1]                  # in the order the narrator says them, not appended at the end
    assert cr._first_spoken("This one", words) is None and not cr._word_matches("this", "thi")


def test_check_spec_reads_a_plan_wrapped_in_a_list():
    spec, problem = art.check_spec(json.dumps([SPEC]), 3)
    assert spec and not problem and spec["items"][0]["kind"] == "hacker"
    assert art.check_spec(json.dumps([{"picture": SPEC}]), 3)[0]["items"][1]["kind"] == "server"
    assert art.check_spec(json.dumps([1, 2]), 3)[0] is None and art.check_spec("[]", 3)[0] is None


def test_the_planner_is_told_the_ready_made_icons_and_a_rejected_plan_says_why(tmp_path, monkeypatch, capsys):
    from engine import art_icons
    monkeypatch.setenv("SHORTSFLOW_ICONS", str(tmp_path))
    assert "Also ready-made" not in art.request(SECTION, "T", ["A", "B"])                 # an empty library adds nothing
    for name in ("credit_card", "qr_code"):
        (tmp_path / f"{name}.v2.svg").write_text("<g/>", encoding="utf-8")
    (tmp_path / "old.svg").write_text("<g/>", encoding="utf-8")                           # a file from before the rectangle fix is not offered
    assert art_icons.library_names() == ["credit_card", "qr_code"]
    assert "Also ready-made, usable as a kind: credit_card, qr_code." in art.request(SECTION, "T", ["A", "B"])
    assert art.make(SECTION, "T", "16:9", lambda p: json.dumps({"items": [{"kind": "server"}]}), str(tmp_path / "cache")) is None
    assert "was not usable: it had 1 items and 3 were needed" in capsys.readouterr().out   # the reason is printed, not just "No picture"


def test_narration_timing_warnings_name_the_section_and_the_problem():
    from engine import case_render as cr
    ok = [{"word": "a", "start": 0.0, "end": 0.4}, {"word": "b", "start": 9.0, "end": 9.8}]
    late = [{"word": "a", "start": 12.0, "end": 12.4}, {"word": "b", "start": 20.0, "end": 21.0}]
    early = [{"word": "a", "start": 0.0, "end": 0.4}, {"word": "b", "start": 3.0, "end": 3.5}]
    assert cr.timing_warnings([ok], [10.0]) == []
    assert "first word is timed 12.0 s in" in cr.timing_warnings([late], [21.5], ["What it is"])[0] and cr.timing_warnings([late], [21.5], ["What it is"])[0].startswith("What it is:")
    assert "ends 6.5 s before the audio does" in cr.timing_warnings([early], [10.0])[0]
    assert "no word timings" in cr.timing_warnings([[]], [5.0])[0]


def test_tests_run_with_a_private_home_folder():
    import os
    home = os.path.expanduser("~")
    assert "home" in home and os.path.isdir(home) and not os.listdir(home)                    # empty, and not the real home


def test_the_picture_plan_remembers_which_icon_each_label_got(tmp_path):
    got = art.make(SECTION, "T", "16:9", lambda p: json.dumps(SPEC), str(tmp_path))
    assert got["kinds"] == {"Attacker": "hacker", "Server": "server", "Stolen data": "database"}
    again = art.make(SECTION, "T", "16:9", lambda p: 1 / 0, str(tmp_path))                  # from the cache
    assert again["kinds"] == got["kinds"]


def test_an_icon_drawn_by_the_local_fallback_is_used_but_not_kept_in_the_library(tmp_path):
    from engine import art_icons
    drawing = json.dumps({"svg": "<g><rect x='-60' y='-60' width='120' height='120' fill='#3b82f6' stroke='#1f2937'/>" + "<circle cx='0' cy='0' r='30' fill='#fff'/>" * 3 + "</g>"})

    def ask_from(source):
        def ask(prompt):
            ask.last_source = source
            return drawing
        return ask
    assert art_icons.get("heat pump", ask_from("local"), str(tmp_path)) and not (tmp_path / "heat_pump.v2.svg").exists()      # drawn, used, not saved
    assert art_icons.get("heat pump", ask_from("cloud"), str(tmp_path)) and (tmp_path / "heat_pump.v2.svg").is_file()       # the cloud model's drawing is kept
    assert art_icons.get("water drop", lambda p: drawing, str(tmp_path)) and (tmp_path / "water_drop.v2.svg").is_file()       # an ask with no record of its source is kept as before
