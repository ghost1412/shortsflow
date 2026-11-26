"""Things a story needs that the kit cannot draw (engine/story_objects.py): drawn by the model, checked blind, saved only when recognised; and their cards."""
import json
import os
import xml.dom.minidom

import pytest

from engine import case_story as st, story_objects as so


@pytest.fixture(autouse=True)
def no_real_image_model(monkeypatch):
    """The story tests stay offline: no image model (a Gemini key on this PC must not be used) and no renderer."""
    from engine import story_objects, visual_context
    monkeypatch.setattr(visual_context, "choose_backend", lambda: (None, None, "none"))
    monkeypatch.setattr(story_objects, "render_sheet", lambda documents, out, **k: None)
    monkeypatch.setattr(story_objects, "BUSY_WAIT", 0)

DRAWING = json.dumps({"svg": "<rect x='-60' y='-20' width='120' height='60' rx='8' fill='#b45309' stroke='#1f2937'/><circle cx='-40' cy='60' r='18' fill='#f59e0b'/>"
                             "<circle cx='40' cy='60' r='18' fill='#f59e0b'/><polygon points='20,-20 60,-80 80,-20' fill='#b45309'/><rect x='-80' y='-30' width='30' height='20' fill='#facc15'/>"})


def render(documents, out):
    with open(out, "wb") as f:
        f.write(b"jpg")
    return out


def eyes(line):
    """A stand-in image model: always answers `line` (or line(prompt)); what it was asked is kept."""
    seen = []

    def ask_image(frames, model, prompt=None):
        seen.append(prompt)
        return line(prompt) if callable(line) else line
    return ("m", ask_image, "test"), seen


def asker(prompt, same=True):
    """A stand-in text model: it draws, and it judges whether what was seen is what was wanted."""
    if "someone who was not told" in prompt:
        count = prompt.count("Wanted: ")
        return json.dumps({"verdicts": [{"id": i, "same": same} for i in range(1, count + 1)]})
    return DRAWING


def test_a_recognised_drawing_is_used_and_saved_and_the_next_video_draws_nothing(tmp_path):
    vision, seen = eyes("1=a wooden horse on wheels")
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return asker(prompt)
    got = so.make(["wooden horse"], ask, str(tmp_path / "run"), vision=vision, render=render, directory=str(tmp_path / "lib"))["wooden horse"]
    assert got["status"] == "checked" and os.path.isfile(got["path"]) and so.load("wooden horse", str(tmp_path / "lib"))
    xml.dom.minidom.parse(got["path"])
    assert "wooden horse" not in seen[0]                                  # the image model is never told what it should see
    assert "Wanted: wooden horse" in prompts[-1] and "a wooden horse on wheels" in prompts[-1]
    again = so.make(["wooden horse"], lambda p: (_ for _ in ()).throw(AssertionError("asked again")), str(tmp_path / "run2"), vision=vision, render=render, directory=str(tmp_path / "lib"))
    assert again["wooden horse"]["status"] == "saved before" and len(seen) == 1
    fresh = so.make(["wooden horse"], ask, str(tmp_path / "run3"), vision=vision, render=render, directory=str(tmp_path / "lib"), fresh=True, feedback="a toy", setting="ancient Troy")
    assert fresh["wooden horse"]["status"] == "checked" and any("ancient Troy" in p and "rejected because: a toy" in p for p in prompts)


def test_a_drawing_seen_as_something_else_is_tried_twice_and_then_left_out_and_never_saved(tmp_path):
    vision, seen = eyes("1=a kitchen table")
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return asker(prompt, same=False)
    got = so.make(["wooden horse"], ask, str(tmp_path / "run"), vision=vision, render=render, directory=str(tmp_path / "lib"))["wooden horse"]
    assert got == {"path": None, "status": "not recognised"} and len(seen) == so.ROUNDS and not so.load("wooden horse", str(tmp_path / "lib"))
    assert any("could not be recognised" in p for p in prompts)
    assert sorted(f for f in os.listdir(tmp_path / "run") if f.startswith("rejected")) == ["rejected_1_wooden_horse.svg", "rejected_2_wooden_horse.svg"]


def test_with_nothing_to_look_at_it_or_judge_it_a_drawing_is_used_but_marked_unchecked_and_not_saved(tmp_path):
    mute_judge = lambda p: "no idea" if "someone who was not told" in p else DRAWING
    for vision, how, ask in ((("", None, "none"), render, asker), (eyes("")[0], render, asker), (eyes("1=x")[0], lambda d, o: None, asker), (eyes("1=x")[0], render, mute_judge)):
        got = so.make(["wooden horse"], ask, str(tmp_path / "run"), vision=vision, render=how, directory=str(tmp_path / "lib"))["wooden horse"]
        assert got["status"] == "unchecked" and got["path"] and not so.load("wooden horse", str(tmp_path / "lib"))


def test_a_broken_drawing_or_a_silent_model_gives_nothing(tmp_path):
    vision, seen = eyes("1=x")
    assert so.make(["ship"], lambda p: "<script>x</script>", str(tmp_path), vision=vision, render=render, directory=str(tmp_path / "l"))["ship"]["status"] == "not drawn"

    def silent(prompt):
        raise RuntimeError("busy")
    assert so.make(["ship"], silent, str(tmp_path), vision=vision, render=render, directory=str(tmp_path / "l"))["ship"]["status"] == "not drawn" and not seen


def test_what_the_image_model_says_is_read_whole_and_in_order():
    assert so.read_answer("1=a sword, with a gem; 2: a 2-masted ship\n3 = fire.", 3) == {1: "a sword, with a gem", 2: "a 2-masted ship", 3: "fire"}
    assert so.read_answer("A single golden crown.", 1) == {1: "A single golden crown."}
    assert so.read_answer("I cannot tell", 2) is None and so.read_answer("7=wolf", 2) is None and so.read_answer("", 1) is None


def test_many_drawings_are_looked_at_a_few_at_a_time(tmp_path):
    vision, seen = eyes(lambda p: "1=a; 2=b; 3=c")
    assert so.describe_all(["<svg/>"] * 5, str(tmp_path), vision, render) == ["a", "b", "c", "a", "b"] and len(seen) == 2


NARRATION = "The Greeks build a wooden horse. The Trojans pull the horse inside the city. Soldiers climb out at night."


def plan_with(props, beats=((1, "Odysseus"),)):
    return {"characters": {"Odysseus": {}}, "sections": [{"props": props, "beats": [{"sentence": n, "character": c, "name": c, "role": "", "mood": "", "emblem": "", "big": "", "label": ""} for n, c in beats]}]}


def test_only_things_the_sentence_mentions_are_kept_and_never_a_person():
    raw = [{"sentence": 2, "object": "The Wooden Horse"}, {"sentence": 2, "object": "dragon"}, {"sentence": 9, "object": "horse"}, {"sentence": 1, "object": "Odysseus"},
           {"sentence": 3, "object": "a very long list of things"}, {"sentence": 3, "object": "soldiers"}]
    assert st.check_props(raw, NARRATION, ["Odysseus"]) == [{"sentence": 2, "object": "wooden horse"}, {"sentence": 3, "object": "soldiers"}]
    assert st.check_props("nonsense", NARRATION, []) == []


def test_every_thing_asked_for_is_drawn_and_a_card_appears_only_for_a_drawing_that_exists():
    script = {"sections": [{"narration": NARRATION}]}
    plan = plan_with([{"sentence": 1, "object": "city gate"}, {"sentence": 2, "object": "wooden horse"}])
    assert st.wanted_drawings(plan, script) == ["city gate", "wooden horse"]      # both are drawn: what fits no card can stand beside the speaker
    without = st.add_object_cards(plan_with([{"sentence": 2, "object": "wooden horse"}]), script)
    assert all(b["character"] for b in without["sections"][0]["beats"])            # not drawn: the face stays
    beats = st.add_object_cards(plan_with([{"sentence": 2, "object": "wooden horse"}]), script, drawn={"wooden horse": "x.svg"})["sections"][0]["beats"]
    assert [(b["sentence"], b["emblem"], b["name"]) for b in beats] == [(1, "", "Odysseus"), (2, "custom:wooden horse", "Wooden Horse"), (3, "", "Odysseus")]
    kit = st.add_object_cards(plan_with([{"sentence": 2, "object": "the wheel"}]), {"sections": [{"narration": "A. The wheel turns. C."}]})
    assert [b["emblem"] for b in kit["sections"][0]["beats"]] == ["", "wheel", ""] and st.kit_emblem("wooden horse") is None


def test_a_whole_run_shows_the_drawn_thing_and_reports_what_it_left_out(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "chars"))
    monkeypatch.setenv("SHORTSFLOW_STORY_OBJECTS", str(tmp_path / "objects"))
    script = {"title": "Troy", "sections": [{"scene": "story", "title": "a", "narration": NARRATION}]}
    reply = {"characters": {"Odysseus": {}}, "sections": [{"props": [{"sentence": 2, "object": "wooden horse"}, {"sentence": 3, "object": "soldiers"}],
                                                          "beats": [{"sentence": 1, "character": "Odysseus"}]}]}

    def ask(prompt):
        if "someone who was not told" in prompt:
            return json.dumps({"verdicts": [{"id": i, "same": "Wanted: wooden horse" in line} for i, line in
                                            enumerate([x for x in prompt.splitlines() if "Wanted: " in x], 1)]})
        if prompt.startswith("Draw ONE"):
            return asker(prompt)
        if "numbered section.sentence" in prompt or "decide whether to keep it" in prompt:
            return "no answer"                                    # the review has its own tests: here it gets nothing to work with
        return json.dumps(reply)
    vision, _ = eyes("1=a horse made of wood; 2=a blob")
    out = st.attach(script, str(tmp_path / "run"), "9:16", ask, [[]], [(0.0, 12.0)], vision=vision, render=render)[0]
    card = [b for b in out["beats"] if not b["character"]]
    assert len(card) == 1 and card[0]["emblem"].endswith("wooden_horse.svg") and os.path.isfile(card[0]["emblem"]) and out["cards"] == ["Wooden Horse"]
    report = {o["name"]: (o["status"], o["shown"]) for o in out["objects"]}
    assert report == {"wooden horse": ("checked", True), "soldiers": ("not recognised", False)}

    from engine import case_report
    text = case_report.build({"title": "Troy", "sections": script["sections"]}, art={"9:16": [out]})
    assert "cards: Wooden Horse" in text and "soldiers: not recognised (not shown)" in text


SAVED = {"Athena": {"skin": "fair", "figure": "woman"}, "Kratos": {"skin": "ashen"}, "King Minos": {"skin": "fair"}, "Karna": {"skin": "tan"}}


def test_only_saved_people_this_story_names_are_mentioned_and_they_need_no_new_description():
    script = {"title": "Troy", "sections": [{"narration": "Athena guides the Greeks. Sinon waits. The karnatic song plays."}]}
    assert set(st.named_here(SAVED, script)) == {"Athena"}                    # not the others, and not "Karna" inside "karnatic"
    prompt = st.request(script, SAVED)
    assert "already drawn" in prompt and "Athena" in prompt and "Kratos" not in prompt and "King Minos" not in prompt
    assert "already drawn" not in st.request({"sections": [{"narration": "Sinon waits."}]}, SAVED)
    reply = {"characters": {"Sinon": {}}, "sections": [{"beats": [{"sentence": 1, "character": "Athena"}, {"sentence": 2, "character": "Sinon"}]}]}
    plan = st.check_plan(reply, script, {k: st.story_art.clean_spec(v) for k, v in SAVED.items()})[0]
    assert set(plan["characters"]) == {"Athena", "Sinon"} and [b["character"] for b in plan["sections"][0]["beats"]] == ["Athena", "Sinon"]


def test_a_plan_without_a_single_face_is_sent_back_once(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "chars"))
    script = {"title": "Troy", "sections": [{"scene": "story", "narration": "Sinon waits. Night falls."}]}
    cards = {"characters": {}, "sections": [{"beats": [{"sentence": 1, "name": "The Wait"}]}]}
    faces = {"characters": {"Sinon": {}}, "sections": [{"beats": [{"sentence": 1, "character": "Sinon"}]}]}
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return json.dumps(cards if len(asked) == 1 else faces)
    plan = st.plan(script, ask, str(tmp_path / "a"))
    assert len(asked) == 2 and "no beat shows a person" in asked[1] and plan["sections"][0]["beats"][0]["character"] == "Sinon"
    stubborn = st.plan(script, lambda p: json.dumps(cards), str(tmp_path / "b"))         # a story with nobody to show is still accepted the second time
    assert stubborn and stubborn["sections"][0]["beats"][0]["character"] is None


def asides(plan):
    return [(b["sentence"], b["character"], a["sentence"], a["emblem"]) for s in plan["sections"] for b in s["beats"] for a in b.get("asides", [])]


def test_a_thing_stands_beside_the_speaker_even_in_the_first_sentence_and_the_face_stays():
    plan = st.add_asides(plan_with([{"sentence": 1, "object": "city gate"}]), {"sections": [{"narration": NARRATION}]}, drawn={"city gate": "g.svg"})
    assert asides(plan) == [(1, "Odysseus", 1, "custom:city gate")] and all(b["character"] for b in plan["sections"][0]["beats"])
    assert asides(st.add_asides(plan_with([{"sentence": 1, "object": "city gate"}]), {"sections": [{"narration": NARRATION}]})) == []      # no drawing, nothing shown


def test_a_thing_is_shown_once_two_a_section_and_never_over_a_card_that_shows_one():
    props = [{"sentence": 1, "object": "ship"}, {"sentence": 2, "object": "wooden horse"}, {"sentence": 3, "object": "torch"}]
    drawn = {"ship": 1, "wooden horse": 1, "torch": 1}
    plan = st.add_asides(plan_with(props), {"sections": [{"narration": NARRATION}]}, drawn=drawn)
    assert [a[3] for a in asides(plan)] == ["custom:ship", "custom:wooden horse"]
    busy = plan_with(props)
    busy["sections"][0]["beats"][0]["emblem"] = "wheel"
    assert asides(st.add_asides(busy, {"sections": [{"narration": NARRATION}]}, drawn=drawn)) == []
    two = {"characters": {}, "sections": [plan_with(props[:1])["sections"][0], plan_with(props[:1])["sections"][0]]}
    assert len(asides(st.add_asides(two, {"sections": [{"narration": NARRATION}] * 2}, drawn=drawn))) == 1


def test_a_thing_appears_with_its_sentence_stays_a_moment_and_leaves_for_the_next_one():
    sentence_times = [(0.0, 4.0), (4.0, 5.0), (5.0, 12.0)]
    got = st.aside_times([{"sentence": 3, "emblem": "b"}, {"sentence": 2, "emblem": "a"}], sentence_times, 0.0, 12.0)
    assert got == [("a", 4.0, 5.0), ("b", 5.0, 12.0)]
    assert st.aside_times([{"sentence": 2, "emblem": "a"}], sentence_times, 2.0, 12.0) == [("a", 2.0, 4.5)]            # at least 2.5 s
    assert st.aside_times([{"sentence": 2, "emblem": "a"}], sentence_times, 0.0, 5.5) == [("a", 4.0, 5.5)]             # never past its beat
