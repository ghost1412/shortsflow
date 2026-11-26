"""Things a story needs that the kit cannot draw (engine/story_objects.py): drawn by the model, checked blind, saved only when recognised; and their cards."""
import json
import os
import xml.dom.minidom

from engine import case_story as st, story_objects as so

DRAWING = json.dumps({"svg": "<rect x='-60' y='-20' width='120' height='60' rx='8' fill='#b45309' stroke='#1f2937'/><circle cx='-40' cy='60' r='18' fill='#f59e0b'/>"
                             "<circle cx='40' cy='60' r='18' fill='#f59e0b'/><polygon points='20,-20 60,-80 80,-20' fill='#b45309'/><rect x='-80' y='-30' width='30' height='20' fill='#facc15'/>"})


def asker(prompt):
    return json.dumps({"look_alikes": ["pony cart", "table", "dog", "wooden horse"]}) if "look_alikes" in prompt else DRAWING


def render(documents, out):
    with open(out, "wb") as f:
        f.write(b"jpg")
    return out


def eyes(answer_for):
    """A stand-in image model: answer_for(prompt) gives its one line."""
    seen = []

    def ask_image(frames, model, prompt=None):
        seen.append(prompt)
        return answer_for(prompt)
    return ("m", ask_image, "test"), seen


def listed(prompt):
    return prompt.split("what it is: ")[1].split(".\n")[0].split("; ")


def test_a_recognised_drawing_is_used_and_saved_and_the_next_video_draws_nothing(tmp_path):
    vision, seen = eyes(lambda p: "1=wooden horse")
    got = so.make(["wooden horse"], asker, str(tmp_path / "run"), vision=vision, render=render, directory=str(tmp_path / "lib"))["wooden horse"]
    assert got["status"] == "checked" and os.path.isfile(got["path"]) and so.load("wooden horse", str(tmp_path / "lib"))
    xml.dom.minidom.parse(got["path"])
    names = listed(seen[0])
    assert "wooden horse" in names and "pony cart" in names and names == sorted(names) and len(names) >= 6     # look-alikes and unlike decoys, in an order that tells nothing
    again = so.make(["wooden horse"], lambda p: (_ for _ in ()).throw(AssertionError("asked again")), str(tmp_path / "run2"), vision=vision, render=render, directory=str(tmp_path / "lib"))
    assert again["wooden horse"]["status"] == "saved before" and len(seen) == 1


def test_a_drawing_nobody_recognises_is_tried_twice_and_then_left_out_and_never_saved(tmp_path):
    vision, seen = eyes(lambda p: "1=table")
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return asker(prompt)
    got = so.make(["wooden horse"], ask, str(tmp_path / "run"), vision=vision, render=render, directory=str(tmp_path / "lib"))["wooden horse"]
    assert got == {"path": None, "status": "not recognised"} and len(seen) == so.ROUNDS and not so.load("wooden horse", str(tmp_path / "lib"))
    assert any("could not be recognised" in p for p in prompts)
    assert sorted(f for f in os.listdir(tmp_path / "run") if f.startswith("rejected")) == ["rejected_1_wooden_horse.svg", "rejected_2_wooden_horse.svg"]


def test_with_nothing_to_look_at_it_a_drawing_is_used_but_marked_unchecked_and_not_saved(tmp_path):
    for vision, how in ((("", None, "none"), render), (eyes(lambda p: "")[0], render), (eyes(lambda p: "1=wooden horse")[0], lambda d, o: None)):
        got = so.make(["wooden horse"], asker, str(tmp_path / "run"), vision=vision, render=how, directory=str(tmp_path / "lib"))["wooden horse"]
        assert got["status"] == "unchecked" and got["path"] and not so.load("wooden horse", str(tmp_path / "lib"))


def test_a_broken_drawing_or_a_silent_model_gives_nothing(tmp_path):
    vision, seen = eyes(lambda p: "1=x")
    assert so.make(["ship"], lambda p: "<script>x</script>", str(tmp_path), vision=vision, render=render, directory=str(tmp_path / "l"))["ship"]["status"] == "not drawn"

    def silent(prompt):
        raise RuntimeError("busy")
    assert so.make(["ship"], silent, str(tmp_path), vision=vision, render=render, directory=str(tmp_path / "l"))["ship"]["status"] == "not drawn" and not seen


def test_the_answer_line_is_read_whatever_its_punctuation():
    assert so.read_answer("1=Wolf; 2: none\n3 - The Lighthouse.", 3) == {1: "wolf", 2: "none", 3: "the lighthouse"}
    assert so.read_answer("I cannot tell", 2) is None and so.read_answer("7=wolf", 2) is None


def test_look_alikes_never_include_the_thing_itself():
    out = so.look_alikes(["wooden horse"], lambda p: json.dumps({"look_alikes": ["horse", "wooden horse", "camel", "Camel", "x" * 60, 5]}))
    assert out == ["camel"] and so.look_alikes(["a"], lambda p: "nonsense") == [] and so.look_alikes([], asker) == []


NARRATION = "The Greeks build a wooden horse. The Trojans pull the horse inside the city. Soldiers climb out at night."


def plan_with(props, beats=((1, "Odysseus"),)):
    return {"characters": {"Odysseus": {}}, "sections": [{"props": props, "beats": [{"sentence": n, "character": c, "name": c, "role": "", "mood": "", "emblem": "", "big": "", "label": ""} for n, c in beats]}]}


def test_only_things_the_sentence_mentions_are_kept_and_never_a_person():
    raw = [{"sentence": 2, "object": "The Wooden Horse"}, {"sentence": 2, "object": "dragon"}, {"sentence": 9, "object": "horse"}, {"sentence": 1, "object": "Odysseus"},
           {"sentence": 3, "object": "a very long list of things"}, {"sentence": 3, "object": "soldiers"}]
    assert st.check_props(raw, NARRATION, ["Odysseus"]) == [{"sentence": 2, "object": "wooden horse"}, {"sentence": 3, "object": "soldiers"}]
    assert st.check_props("nonsense", NARRATION, []) == []


def test_only_things_with_a_free_place_are_drawn_and_a_card_appears_only_for_a_drawing_that_exists():
    script = {"sections": [{"narration": NARRATION}]}
    plan = plan_with([{"sentence": 1, "object": "city gate"}, {"sentence": 2, "object": "wooden horse"}])
    assert st.wanted_drawings(plan, script) == ["wooden horse"]                   # sentence 1 never takes a card, so nothing is drawn for it
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
        if "look_alikes" in prompt or prompt.startswith("Draw ONE"):
            return asker(prompt)
        return json.dumps(reply)
    vision, _ = eyes(lambda p: "1=wooden horse; 2=none")
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
