"""The story look (engine/story_art.py, engine/case_story.py and its place in engine/case_render.py): drawings are valid and deterministic, the plan is checked, beats land on sentences."""
import json
import os
import xml.dom.minidom

from engine import case_render as cr, case_story as st, story_art as sa

SCRIPT = {"title": "The Wheel", "hook": "h", "verified": True, "sources": [], "sections": [
    {"id": "moment", "title": "The moment", "scene": "story", "on_screen": [],
     "narration": "Karna jumped down to free the wheel. Krishna spoke to Arjuna. He reminded them of Abhimanyu, who was 16 years old."},
    {"id": "end", "title": "How it ended", "scene": "story", "on_screen": [], "narration": "Arjuna raised his bow. The son of the Sun fell."},
]}
GOOD = {"characters": {"Karna": {"skin": "tan", "headgear": "crown", "ornaments": ["halo"], "weapon": "bow", "outfit": "armour", "mood": "proud"},
                       "Krishna": {"skin": "blue", "headgear": "crown", "ornaments": ["feather", "tilak"]}, "Arjuna": {"skin": "brown", "headgear": "helmet"}},
        "sections": [{"sky": "sunset", "ground": "battlefield", "beats": [
            {"sentence": 1, "character": "Karna", "name": "Karna", "role": "Son of the Sun"},
            {"sentence": 2, "character": "krishna", "name": "Krishna", "role": ""},
            {"sentence": 3, "character": None, "name": "Abhimanyu", "role": "sixteen years old", "big": "16", "label": "years old"}]},
            {"sky": "nonsense", "ground": "none", "beats": [{"sentence": 2, "character": "Ghost", "name": "Arjuna", "role": ""}]}]}


def test_every_part_and_colour_draws_valid_svg_and_the_same_spec_draws_the_same_picture():
    for headgear in sa.HEADGEAR:
        for outfit in sa.OUTFITS:
            for mood in sa.MOODS:
                xml.dom.minidom.parseString(sa.character_svg({"headgear": headgear, "outfit": outfit, "mood": mood, "facial_hair": "beard", "weapon": "bow",
                                                              "ornaments": list(sa.ORNAMENTS), "age": "old", "skin": "blue"}))
    for skin in list(sa.SKIN) + ["#336699"]:
        xml.dom.minidom.parseString(sa.character_svg({"skin": skin}))
    spec = {"skin": "tan", "headgear": "turban", "weapon": "spear"}
    assert sa.character_svg(spec) == sa.character_svg(dict(spec))


def test_a_spec_keeps_only_known_values():
    spec = sa.clean_spec({"skin": "purple-ish", "headgear": "top hat", "mood": "furious", "ornaments": ["halo", "wings", "HALO", "tilak"], "outfit_colour": "ultraviolet", "weapon": "laser"})
    assert spec["skin"] == "tan" and spec["headgear"] == "none" and spec["mood"] == "neutral" and spec["ornaments"] == ["halo", "tilak"]
    assert spec["outfit_colour"] == "maroon" and spec["weapon"] == "none"
    assert sa.clean_spec(None) == sa.DEFAULT_SPEC and sa.clean_spec({"skin": "#A0B1c2"})["skin"] == "#a0b1c2"


def test_every_sky_and_ground_draws_a_valid_backdrop_of_the_right_size():
    for sky in sa.SKIES:
        for ground in sa.GROUNDS:
            doc = xml.dom.minidom.parseString(sa.backdrop_svg(sky, ground, 540, 960)).documentElement
            assert doc.getAttribute("width") == "540" and doc.getAttribute("height") == "960"
    assert sa.backdrop_svg("nope", "nope", 100, 100) == sa.backdrop_svg("sunset", "none", 100, 100)


def test_the_plan_keeps_only_what_it_may_and_fills_what_is_missing():
    plan, problem = st.check_plan(GOOD, SCRIPT)
    assert plan and not problem and set(plan["characters"]) == {"Karna", "Krishna", "Arjuna"}
    first = plan["sections"][0]
    assert [b["character"] for b in first["beats"]] == ["Karna", "Krishna", None]          # "krishna" is matched to Krishna
    assert all(b["name"] == b["character"] for b in first["beats"] if b["character"])
    assert first["beats"][2]["big"] == "16" and first["beats"][2]["label"] == "years old"      # the narration says 16
    second = plan["sections"][1]
    assert second["sky"] == "sunset" and second["ground"] == "none"                          # an unknown sky is replaced
    assert second["beats"][0]["sentence"] == 1 and second["beats"][1]["character"] is None     # a beat at sentence 1 is added; the unknown "Ghost" is not a character


def test_a_figure_the_narration_does_not_say_is_dropped_and_an_empty_plan_is_refused():
    bad = json.loads(json.dumps(GOOD))
    bad["sections"][0]["beats"][2]["big"] = "99"
    plan, _ = st.check_plan(bad, SCRIPT)
    assert plan["sections"][0]["beats"][2]["big"] == "" and plan["sections"][0]["beats"][2]["label"] == ""
    assert st.check_plan("not json at all", SCRIPT)[0] is None
    assert st.check_plan({"characters": {}, "sections": []}, {"sections": [{"narration": "", "title": ""}]})[0] is None


def test_beats_start_when_their_sentence_starts():
    narration = "One two three. Four five six. Seven eight nine."
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(narration.replace(".", "").split())]
    beats = [{"sentence": 1}, {"sentence": 2}, {"sentence": 3}]
    times = st.beat_times(narration, words, 5.0, beats)
    assert times[0][0] == 0.0 and abs(times[1][0] - 1.4) < 0.2 and abs(times[2][0] - 2.9) < 0.2
    assert times[0][1] == times[1][0] and times[2][1] == 5.0


def test_a_run_plans_once_and_a_saved_plan_is_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "lib"))
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return json.dumps(GOOD)
    timing = [(0.0, 9.0), (9.0, 15.0)]
    words = [[{"word": "w", "start": i * 0.3, "end": i * 0.3 + 0.2} for i in range(24)], [{"word": "w", "start": i * 0.3, "end": i * 0.3 + 0.2} for i in range(10)]]
    out = st.attach(SCRIPT, str(tmp_path), "9:16", ask, words, timing)
    assert len(calls) == 1 and all(o and o["kind"] == "story" for o in out)
    assert os.path.isfile(out[0]["backdrop"]) and os.path.isfile(out[0]["beats"][0]["character"]) and out[0]["beats"][2]["character"] is None
    assert "Karna" in st.load_library(str(tmp_path / "lib")) and os.path.isfile(str(tmp_path / "story_plan.json"))
    st.attach(SCRIPT, str(tmp_path), "9:16", ask, words, timing)
    assert len(calls) == 1                                                         # the plan saved with the run is used
    assert st.attach({"sections": [{"scene": "quote", "narration": "x", "title": "t"}]}, str(tmp_path), "9:16", ask, [[]], [(0, 1)]) == [None]


def test_known_people_are_told_to_the_model_and_keep_their_saved_look(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "lib"))
    st.save_character("Krishna", sa.clean_spec({"skin": "blue", "headgear": "crown"}), str(tmp_path / "lib"))
    seen = []

    def ask(prompt):
        seen.append(prompt)
        again = json.loads(json.dumps(GOOD))
        again["characters"]["Krishna"] = {"skin": "green", "headgear": "turban"}         # the model redescribes him differently
        return json.dumps(again)
    plan = st.plan(SCRIPT, ask, str(tmp_path / "run"))
    assert "Krishna" in seen[0] and plan["characters"]["Krishna"]["skin"] == "blue" and plan["characters"]["Krishna"]["headgear"] == "crown"


def test_props_carry_the_story_and_a_section_without_a_picture_shows_a_quote():
    words = [[{"word": "w", "start": 0.1 * i, "end": 0.1 * i + 0.08} for i in range(20)]] * 2
    story = {"kind": "story", "backdrop": "bd.svg", "beats": [{"from": 0.0, "to": 2.0, "character": "k.svg", "name": "Karna", "role": "", "big": "", "label": ""}]}
    props = cr.build_props(SCRIPT, [(2.0, 9.0), (9.0, 15.0)], words, art=[story, None])
    first, second = props["sections"]
    assert first["scene"] == "story" and first["story"]["backdrop"] == "bd.svg" and first["labels"] == [] and first["cues"] == []
    assert second["scene"] == "quote" and second["labels"] and "story" not in second


def test_story_sections_get_no_stock_footage_or_cartoon_behind_them(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(cr, "attach_footage", lambda script, *a, **k: seen.update(footage=[s["footage"] for s in script["sections"]]) or None)
    script = {"sections": [{"scene": "story", "footage": ["sunset"]}, {"scene": "quote", "footage": ["city"]}]}
    cr.backgrounds_for(script, str(tmp_path), "9:16", "footage", has_pexels=True)
    assert seen["footage"] == [[], ["city"]]


def test_a_run_with_no_text_model_stops_with_a_clear_message_not_a_traceback(monkeypatch, capsys):
    import argparse

    import pytest

    from engine import case_study
    from engine.modes import case as case_mode
    monkeypatch.setattr(case_study, "gather_sources", lambda items, **kw: ([], []))

    def nobody(*a, **k):
        raise RuntimeError("The local model did not answer (connection refused)")
    monkeypatch.setattr(case_study, "write_script", nobody)
    args = argparse.Namespace(prompt="A topic", sources=[], category=None)
    with pytest.raises(SystemExit) as stop:
        case_mode._make_script(args, "unused", {"template": "story", "layouts": "auto", "length": "short", "llm": "auto"})
    out = capsys.readouterr().out
    assert stop.value.code == 1 and "No text model answered" in out and "Ollama" in out


def test_a_title_about_someone_else_is_a_card_and_a_face_always_carries_its_own_name():
    data = json.loads(json.dumps(GOOD))
    data["sections"][0]["beats"] = [{"sentence": 1, "character": "Krishna", "name": "Abhimanyu", "role": "broken rules", "emblem": "bow"},
                                    {"sentence": 2, "character": "Krishna", "name": "Krishna's Counsel", "role": "urging", "emblem": "wheel"},
                                    {"sentence": 3, "character": None, "name": "The Wheel", "emblem": "WHEEL"}]
    card, face, wheel = st.check_plan(data, SCRIPT)[0]["sections"][0]["beats"]
    assert card["character"] is None and card["name"] == "Abhimanyu" and card["emblem"] == "bow"
    assert face["character"] == "Krishna" and face["name"] == "Krishna" and face["emblem"] == ""
    assert wheel["emblem"] == "wheel"


def test_every_emblem_draws_valid_svg_and_an_unknown_one_draws_nothing():
    for kind in sa.EMBLEMS:
        xml.dom.minidom.parseString(sa.emblem_svg(kind))
    assert sa.emblem_svg("dragon") == ""


def test_a_card_with_an_emblem_gets_its_drawing_and_a_beat_without_one_carries_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "lib"))
    data = json.loads(json.dumps(GOOD))
    data["sections"][0]["beats"].append({"sentence": 2, "character": None, "name": "x"})
    data["sections"][0]["beats"][1] = {"sentence": 2, "character": None, "name": "The Wheel", "emblem": "wheel"}
    words = [[{"word": "w", "start": i * 0.3, "end": i * 0.3 + 0.2} for i in range(24)]] * 2
    out = st.attach(SCRIPT, str(tmp_path), "9:16", lambda p: json.dumps(data), words, [(0.0, 9.0), (9.0, 15.0)])
    assert os.path.isfile(out[0]["beats"][1]["emblem"])
    beats = cr.build_props(SCRIPT, [(0.0, 9.0), (9.0, 15.0)], words, art=out)["sections"][0]["story"]["beats"]
    assert "emblem" in beats[1] and "character" not in beats[1] and "emblem" not in beats[0]


def test_two_pages_of_one_site_are_listed_once_on_the_closing_card():
    script = dict(SCRIPT, sources=[{"id": "S1", "ref": "https://en.wikipedia.org/wiki/A"}, {"id": "S2", "ref": "https://en.wikipedia.org/wiki/B"}])
    props = cr.build_props(script, [(0.0, 5.0), (5.0, 9.0)], [[], []])
    assert props["sources"] == ["en.wikipedia.org"]


def test_the_browser_app_offers_every_template_the_pipeline_has():
    from pathlib import Path

    from engine import case_options
    from shortsflow import web_args
    assert [value for _, value in web_args.CASE_TEMPLATE_CHOICES] == list(case_options.TEMPLATES)       # the list was once typed by hand and missed three
    assert "c_template = gr.Dropdown(web_args.CASE_TEMPLATE_CHOICES" in (Path(__file__).resolve().parent.parent / "webui.py").read_text(encoding="utf-8")
    assert "template=story" in web_args.case_args("A tale", template="story", formats=("9:16",))
