"""What a small local model leaves out is read from names and the narration: a poor country boy is a boy, an ogre has fangs, a card with a stand-in symbol goes."""
import json

from engine import case_story as cs
from engine import story_review as sr


def test_a_boy_with_a_couple_of_adjectives_is_a_child_but_a_relation_is_not():
    assert cs.facts_from("Jack", "Jack is a poor country boy. He sells a cow.")["figure"] == "child"
    assert cs.facts_from("Tom", "Tom was a strong young farm boy.")["figure"] == "child"
    assert cs.facts_from("Bill", "Bill is taller than the boy.") == {}
    assert cs.facts_from("Bill", "Bill is a good friend of the boy.") == {}
    assert cs.facts_from("Sam", "Sam is the father of the boy.") == {}


def ask_for(*rows):
    return lambda prompt: json.dumps({"needed": list(rows)})


SCRIPT = {"title": "Jack", "sections": [{"narration": "The ogre returns home. Jack takes the hen that lays golden eggs. The ogre's wife warns him."}]}


def test_the_name_says_what_to_draw_when_the_model_gave_nothing():
    got = sr.needed(SCRIPT, ask_for({"name": "Ogre", "kind": "creature", "at": "1.1"}, {"name": "Hen", "kind": "creature", "at": "1.2"},
                                    {"name": "Ogre's wife", "kind": "creature", "at": "1.3"}))
    by = {g["name"]: g for g in got}
    assert by["Ogre"]["species"] == "human" and by["Ogre"]["features"] == ["fangs"]
    assert by["Hen"]["species"] == "bird"
    assert by["Ogre's wife"]["species"] == "" and by["Ogre's wife"]["features"] == []          # the noun is "wife": a woman, not a monster


def test_what_the_model_did_say_is_never_changed():
    got = sr.needed(SCRIPT, ask_for({"name": "Ogre", "kind": "creature", "at": "1.1", "species": "bear", "features": ["horns"]}))
    assert got[0]["species"] == "bear" and got[0]["features"] == ["horns"]


def beat(sentence, character=None, name="", emblem=""):
    return {"sentence": sentence, "character": character, "name": name or character or "", "role": "", "mood": "", "emblem": emblem, "big": "", "label": ""}


def test_a_card_for_a_thing_that_could_not_be_drawn_gives_the_screen_back_to_the_character():
    plan = {"characters": {"Jack": {}}, "sections": [{"beats": [beat(1, "Jack"), beat(2, name="beanstalk", emblem="wings"), beat(3, name="Dawn", emblem="sun")]}]}
    report = {"left": [{"name": "Beanstalk", "kind": "thing", "why": "not drawn"}, {"name": "Ogre", "kind": "creature", "why": "x"}]}
    sr.drop_stand_ins(plan, report)
    beats = plan["sections"][0]["beats"]
    assert beats[1]["character"] == "Jack" and beats[1]["sentence"] == 2 and not beats[1].get("emblem")
    assert beats[2]["emblem"] == "sun"                                         # another card keeps its symbol
    assert report["stand_ins"] == [{"name": "Beanstalk", "was": "wings", "section": 1, "sentence": 2}]
