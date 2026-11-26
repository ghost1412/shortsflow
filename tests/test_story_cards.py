"""A title card must show something: one ordinary word on an empty screen is not a picture."""
import json

from engine import case_story

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
