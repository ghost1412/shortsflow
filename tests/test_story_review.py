"""ShortsFlow's review of its own story (engine/story_review.py): wrong pictures are replaced or removed, what is missing is added, the rest is reported."""
import json
import os

import pytest

from engine import case_story as st, story_review as sr


@pytest.fixture(autouse=True)
def no_real_image_model(monkeypatch):
    """The story tests stay offline: no image model (a Gemini key on this PC must not be used) and no renderer."""
    from engine import story_objects, visual_context
    monkeypatch.setattr(visual_context, "choose_backend", lambda: (None, None, "none"))
    monkeypatch.setattr(story_objects, "render_sheet", lambda documents, out, **k: None)

DRAWING = json.dumps({"svg": "<rect x='-60' y='-20' width='120' height='60' rx='8' fill='#b45309' stroke='#1f2937'/><circle cx='-40' cy='60' r='18' fill='#f59e0b'/>"
                             "<circle cx='40' cy='60' r='18' fill='#f59e0b'/><polygon points='20,-20 60,-80 80,-20' fill='#b45309'/><rect x='-80' y='-30' width='30' height='20' fill='#facc15'/>"})
SCRIPT = {"title": "Warrior", "sections": [{"scene": "story", "narration": "The Prince is hunted by the Dahaka. He releases the Sands. His ship sails to an island."},
                                           {"scene": "story", "narration": "Shahdee attacks him. He raises the sword."}]}


def render(documents, out):
    with open(out, "wb") as f:
        f.write(b"jpg")
    return out


def beat(k, who=None, emblem="", asides=None, name=None):
    row = {"sentence": k, "character": who, "name": name or who or "Card", "role": "", "mood": "", "emblem": emblem, "big": "", "label": ""}
    if asides:
        row["asides"] = [{"sentence": s, "emblem": e} for s, e in asides]
    return row


def a_plan():
    return {"setting": "an ancient Persian fantasy", "characters": {"The Prince": {}},
            "sections": [{"sky": "storm", "ground": "none", "beats": [beat(1, "The Prince"), beat(2, emblem="box", name="The Sands"), beat(3, "The Prince")]},
                         {"sky": "fire", "ground": "none", "beats": [beat(1, "The Prince", asides=[(2, "sword")])]}]}


NEEDED = {"needed": [{"name": "The Prince", "kind": "person", "at": "1.1"}, {"name": "Dahaka", "kind": "creature", "at": "1.1", "looks": "black horned smoke demon"},
                     {"name": "Shahdee", "kind": "person", "at": "2.1"}, {"name": "dragon", "kind": "creature", "at": "1.1"}, {"name": "ship", "kind": "thing", "at": "2.2"}]}


def model(verdicts, needed=NEEDED, same=True, calls=None):
    """A stand-in text model. verdicts: a function of the sentence line -> (keep, why, should)."""
    def ask(prompt):
        if calls is not None:
            calls.append(prompt)
        if "numbered section.sentence" in prompt:
            return json.dumps(needed)
        if "decide whether to keep it" in prompt:
            rows = []
            for line in prompt.split("\n"):
                if line[:1].isdigit() and "The narrator says" in line:
                    keep, why, should = verdicts(line)
                    rows.append({"id": int(line.split(".")[0]), "keep": keep, "why": why, "should": should})
            return json.dumps({"verdicts": rows})
        if "someone who was not told" in prompt:
            return json.dumps({"verdicts": [{"id": i, "same": same} for i in range(1, prompt.count("Wanted: ") + 1)]})
        if "Describe each of these people" in prompt:
            return json.dumps({"people": [{"name": "Shahdee", "figure": "woman", "weapon": "twin_blades"}]})
        return DRAWING
    return ask


VISION = ("m", lambda frames, m, prompt=None: "1=something; 2=something; 3=something", "test")


def keep_all(line):
    return True, "", ""


def test_only_what_the_narration_names_is_asked_for_and_a_wrong_sentence_number_is_corrected():
    out = sr.needed(SCRIPT, model(keep_all))
    assert [(o["name"], o["section"], o["sentence"]) for o in out] == [("The Prince", 0, 1), ("Dahaka", 0, 1), ("Shahdee", 1, 1), ("ship", 0, 3)]      # no dragon is said; the ship is said in 1.3
    assert sr.needed(SCRIPT, lambda p: "nonsense") is None


def test_a_missing_person_creature_and_thing_are_added_and_a_creature_drawn_as_a_person_is_missing(tmp_path):
    plan = a_plan()
    plan["sections"][0]["beats"][1] = beat(2, "The Prince")
    drawn = {}
    report = sr.run(plan, SCRIPT, model(keep_all), str(tmp_path), drawn, vision=VISION, render=render)
    assert {(a["name"], a["kind"]) for a in report["added"]} == {("Dahaka", "creature"), ("Shahdee", "person"), ("ship", "thing")} and not report["left"]
    assert os.path.isfile(plan["characters"]["Dahaka"]["creature"]) and plan["characters"]["Shahdee"]["figure"] == "woman"
    assert [b["character"] for b in plan["sections"][1]["beats"]][0] == "Shahdee" and plan["sections"][0]["beats"][0]["character"] == "Dahaka"
    assert plan["sections"][0]["beats"][1]["character"] == "The Prince"                                 # the face comes back after the sentence
    as_person = a_plan()
    as_person["characters"]["Dahaka"] = {"skin": "dark"}
    as_person["sections"][0]["beats"][0] = beat(1, "Dahaka")
    assert sr.shown_as(as_person, {"name": "Dahaka", "kind": "creature"}) is None


def test_a_wrong_card_is_replaced_by_what_the_sentence_needs(tmp_path):
    plan, drawn = a_plan(), {}
    wrong = lambda line: (False, "a chest is not sand", "sand") if "releases the Sands" in line and "chest" not in line.split("shows:")[0] else (True, "", "")
    calls = []

    def verdicts(line):
        if "releases the Sands" in line:
            first = not any("sand" == k for k in drawn)
            seen_before = sum("releases the Sands" in c for c in calls if "decide whether to keep it" in c)
            return (False, "a chest is not sand", "sand") if seen_before == 1 else (True, "", "")
        return True, "", ""
    report = sr.run(plan, SCRIPT, model(verdicts, needed={"needed": []}, calls=calls), str(tmp_path), drawn, vision=VISION, render=render)
    card = plan["sections"][0]["beats"][1]
    assert card["emblem"] == "custom:sand" and card["name"] == "Sand" and os.path.isfile(drawn["sand"])
    assert report["replaced"][0]["was"] == "box" and report["checked"] == 2 and not report["removed"]


def test_a_picture_with_nothing_better_is_removed_and_a_card_gives_the_screen_back_to_the_face(tmp_path):
    plan = a_plan()
    report = sr.run(plan, SCRIPT, model(lambda line: (False, "loose symbol", ""), needed={"needed": []}), str(tmp_path), {}, vision=VISION, render=render)
    assert [r["was"] for r in report["removed"]] == ["box", "sword"] and not report["replaced"]
    assert plan["sections"][0]["beats"][1]["character"] == "The Prince" and not plan["sections"][0]["beats"][1].get("emblem")
    assert "asides" not in plan["sections"][1]["beats"][0]


def test_what_cannot_be_fixed_is_reported_as_still_missing(tmp_path):
    plan = a_plan()
    report = sr.run(plan, SCRIPT, model(keep_all, same=False), str(tmp_path), {}, vision=VISION, render=render)           # no drawing is ever recognised
    left = {x["name"]: x["why"] for x in report["left"]}
    assert left["Dahaka"] == "not recognised" and left["ship"] == "not recognised" and [a["name"] for a in report["added"]] == ["Shahdee"]
    text = "\n".join(sr.summary(report))
    assert "STILL MISSING: Dahaka (creature): not recognised" in text and "nothing it listed" not in text


def test_without_an_image_model_nothing_is_changed_on_a_guess_and_it_says_so(tmp_path):
    plan = a_plan()
    report = sr.run(plan, SCRIPT, model(lambda line: (False, "x", ""), needed={"needed": []}), str(tmp_path), {}, vision=("", None, "none"), render=render)
    assert plan == a_plan() and "could not be checked" in report["notes"][0] and report["checked"] == 0


def test_a_run_reviews_once_keeps_the_result_and_a_failing_review_keeps_the_video(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "chars"))
    runs = []
    real = sr.run

    def counted(*a, **k):
        runs.append(1)
        return real(*a, **k)
    monkeypatch.setattr(sr, "run", counted)
    reply = {"setting": "ancient Persia", "characters": {"The Prince": {}}, "sections": [{"beats": [{"sentence": 1, "character": "The Prince"}]}] * 2}
    inner = model(keep_all)

    def ask(prompt):
        return json.dumps(reply) if "art director of a short animated story" in prompt else inner(prompt)
    timing = [(0.0, 9.0), (9.0, 15.0)]
    first = st.attach(SCRIPT, str(tmp_path / "run"), "9:16", ask, [[], []], timing, vision=VISION, render=render)
    second = st.attach(SCRIPT, str(tmp_path / "run"), "16:9", ask, [[], []], timing, vision=VISION, render=render)
    assert len(runs) == 1 and first[0]["review"]["added"] and [b["name"] for b in first[0]["beats"]] == [b["name"] for b in second[0]["beats"]]
    assert any(b.get("character", "") and b["character"].endswith("black_horned_smoke_demon.svg") for b in first[0]["beats"])          # the creature's own drawing is what is on screen

    def broken(*a, **k):
        raise KeyError("boom")
    monkeypatch.setattr(sr, "run", broken)
    again = st.attach(SCRIPT, str(tmp_path / "other"), "9:16", ask, [[], []], timing, vision=VISION, render=render)
    assert again[0]["kind"] == "story" and again[0]["review"]["notes"] == ["the review stopped with an error"]

    from engine import case_report
    text = case_report.build({"title": "W", "sections": SCRIPT["sections"]}, art={"9:16": first})
    assert "ShortsFlow's own review of the story" in text and "added, it was missing: Dahaka (creature)" in text


def test_a_made_up_name_is_drawn_and_checked_as_what_it_looks_like(tmp_path):
    calls = []
    plan = a_plan()
    sr.run(plan, SCRIPT, model(keep_all, needed={"needed": [{"name": "Dahaka", "kind": "creature", "at": "1.1", "looks": "A black horned smoke demon!"}]}, calls=calls),
           str(tmp_path), {}, vision=VISION, render=render)
    drawing = [c for c in calls if c.startswith("Draw ONE")]
    assert drawing and "black horned smoke demon" in drawing[0].split("\n")[0] and "dahaka" not in drawing[0].split("\n")[0].lower()
    assert any("Wanted: black horned smoke demon" in c for c in calls)
    assert plan["characters"]["Dahaka"]["creature"].endswith(".svg") and plan["sections"][0]["beats"][0]["name"] == "Dahaka"


def test_a_person_with_two_names_is_one_person_and_gets_no_second_face(tmp_path):
    rows = {"needed": [{"name": "Kaileena", "also": ["Empress of Time"], "kind": "person", "at": "1.1"}, {"name": "Empress of Time", "kind": "person", "at": "1.1"}]}
    script = {"sections": [{"narration": "Kaileena, the Empress of Time, waits."}]}
    assert [o["name"] for o in sr.needed(script, lambda p: json.dumps(rows))] == ["Kaileena"]
    plan = {"characters": {"Empress of Time": {}}, "sections": [{"beats": [beat(1, "Empress of Time")]}]}
    assert sr.shown_as(plan, {"name": "Kaileena", "also": ["Empress of Time"], "kind": "person"}) == "Empress of Time"
