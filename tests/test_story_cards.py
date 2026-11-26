"""A title card must show something: one ordinary word on an empty screen is not a picture."""
import json

from engine import case_story, story_review

SCRIPT = {"title": "T", "sections": [{"title": "The woods", "narration": "A girl walks to see her grandmother. Then the Wolf meets Little Red Riding Hood. "
                                      "At that moment he runs ahead. He wields Excalibur for 3 days."}]}
CAST = {"Grandmother": {}, "Little Red Riding Hood": {}, "Wolf": {}}


def card(k, name, **extra):
    return {"sentence": k, "character": None, "name": name, **extra}


def beats(*rows, cast=CAST):
    plan, problem = case_story.check_plan(json.dumps({"characters": cast, "sections": [{"beats": list(rows)}]}), SCRIPT, library={})
    assert plan, problem
    return plan["sections"][0]["beats"]


def test_bare_ordinary_words_are_not_cards():
    got = beats({"sentence": 1, "character": "Grandmother", "name": "Grandmother"}, card(2, "girl"), card(3, "moment"), card(4, "who"))
    assert [b["name"] for b in got] == ["Grandmother"]


def test_cards_with_something_to_show_are_kept():
    got = beats(card(1, "The long walk"), card(3, "moment", emblem="sun"), card(4, "days", big="3", label="days"))
    assert [b["sentence"] for b in got] == [1, 3, 4]
    assert case_story.is_title("Excalibur", SCRIPT["sections"][0]["narration"])
    assert not case_story.is_title("Then", SCRIPT["sections"][0]["narration"])      # capitalised only because it starts a sentence


def test_a_section_left_without_beats_opens_on_who_it_names_first():
    got = beats(card(1, "girl"), cast={"Woodcutter": {}, "Little Red Riding Hood": {}, "Wolf": {}})
    assert got[0]["sentence"] == 1 and got[0]["character"] == "Wolf"       # the narration names the Wolf before Little Red Riding Hood
    assert case_story.first_named({"Zeus": {}, "Hades": {}}, "No one is named here.") == "Zeus"
    assert case_story.first_named({}, "Anyone.") is None


def test_a_card_that_only_repeats_the_sections_heading_is_dropped_unless_it_shows_something():
    got = beats(card(1, "The Woods"), card(2, "the woods"), card(3, "The woods", emblem="sun"))
    assert [(b["sentence"], b["emblem"]) for b in got] == [(1, ""), (3, "sun")] and got[0]["character"] == "Grandmother"      # named first in this narration


def test_a_creature_that_cannot_be_drawn_is_not_left_on_screen_as_a_person():
    plan = {"characters": {"Hare": {"figure": "man"}, "Grandmother": {"figure": "woman"}},
            "sections": [{"beats": [{"sentence": 1, "character": "Hare", "name": "Hare", "role": "napping", "mood": "calm", "emblem": "", "big": "", "label": ""},
                                    {"sentence": 2, "character": "Grandmother", "name": "Grandmother", "role": "", "emblem": "", "big": "", "label": ""}]}]}
    assert story_review._drop_human_picture(plan, {"name": "the hare", "kind": "creature", "also": ["Hare"]})
    assert list(plan["characters"]) == ["Grandmother"]
    first, second = plan["sections"][0]["beats"]
    assert first["character"] is None and first["name"] == "Hare" and first["role"] == "" and second["character"] == "Grandmother"
    assert not story_review._drop_human_picture(plan, {"name": "dragon", "kind": "creature"})
    drawn = {"characters": {"Dahaka": {"creature": "x.svg"}}, "sections": []}
    assert not story_review._drop_human_picture(drawn, {"name": "Dahaka", "kind": "creature"}) and "Dahaka" in drawn["characters"]
