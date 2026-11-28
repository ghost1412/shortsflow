"""A card that loses its picture hands the screen to the nearest character, not to a lone title on an empty backdrop."""
from engine import story_review as sr


def beat(sentence, character=None, name="", emblem=""):
    return {"sentence": sentence, "character": character, "name": name or character or "", "role": "", "mood": "", "emblem": emblem, "big": "", "label": ""}


def test_a_card_at_the_start_of_a_section_takes_the_last_character_of_the_section_before():
    plan = {"characters": {"Jack": {}}, "sections": [{"beats": [beat(1, "Jack")]}, {"beats": [beat(1, name="House", emblem="crown"), beat(2, name="Wife")]}]}
    sr.drop_unrelated_symbols(plan, {})
    assert [b["character"] for b in plan["sections"][1]["beats"]][0] == "Jack" and plan["sections"][1]["beats"][0]["sentence"] == 1


def test_with_nobody_before_it_the_next_character_is_used():
    plan = {"characters": {"Jack": {}}, "sections": [{"beats": [beat(1, name="House", emblem="crown")]}, {"beats": [beat(1, "Jack")]}]}
    sr.drop_unrelated_symbols(plan, {})
    assert plan["sections"][0]["beats"][0]["character"] == "Jack"


def test_with_nobody_on_screen_anywhere_the_card_keeps_its_title():
    plan = {"characters": {}, "sections": [{"beats": [beat(1, name="House", emblem="crown")]}]}
    sr.drop_unrelated_symbols(plan, {})
    assert plan["sections"][0]["beats"][0]["character"] is None and plan["sections"][0]["beats"][0]["emblem"] == ""


def test_a_creature_that_could_not_be_drawn_keeps_a_name_card_not_another_persons_face():
    plan = {"characters": {"Jack": {"figure": "child"}, "Ogre's wife": {"figure": "woman"}},
            "sections": [{"beats": [beat(1, "Jack")]}, {"beats": [beat(1, "Ogre's wife"), beat(2, "Jack")]}]}
    assert sr._drop_human_picture(plan, {"name": "Ogre's wife", "also": []})
    first = plan["sections"][1]["beats"][0]
    assert first["character"] is None and first["name"] == "Ogre's wife"           # a name misleads less than somebody else's face (decided earlier, pinned in test_story_cards)
