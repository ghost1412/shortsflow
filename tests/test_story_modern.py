"""People of the modern age have clothes of their own time, and the planner is told to use them."""
import xml.dom.minidom

from engine import case_story, story_art as sa

NEW_OUTFITS = ("suit", "shirt", "uniform", "lab_coat", "dress", "spacesuit")
NEW_HEADGEAR = ("hat", "cap", "military_cap", "space_helmet")


def svg(**spec):
    text = sa.character_svg(spec)
    xml.dom.minidom.parseString(text)
    return text


def test_every_new_part_is_kept_draws_valid_svg_and_changes_the_picture():
    plain = svg()
    for outfit in NEW_OUTFITS:
        assert sa.clean_spec({"outfit": outfit})["outfit"] == outfit and svg(outfit=outfit) != svg(outfit="simple")
    for headgear in NEW_HEADGEAR:
        assert sa.clean_spec({"headgear": headgear})["headgear"] == headgear and svg(headgear=headgear) != plain
    assert svg(ornaments=["glasses"]) != plain and svg(hair="bun", figure="woman") != svg(hair="short", figure="woman")


def test_modern_clothes_wear_no_old_jewels_and_long_hair_stays_inside_a_space_helmet():
    for outfit in NEW_OUTFITS:
        assert 'r="9" fill="#3aa6a6"' not in svg(outfit=outfit)                 # the armour's bead necklace
    suited = svg(outfit="spacesuit", headgear="space_helmet", hair="long", figure="woman")
    assert "M300 132 C190 134" not in suited                                   # no hair falling outside the helmet


def test_the_planner_is_offered_the_new_parts_and_told_to_dress_people_for_their_time():
    prompt = case_story.request({"sections": [{"id": "a", "title": "t", "narration": "Yuri flew into space."}]}, {})
    for part in (*NEW_OUTFITS, *NEW_HEADGEAR, "glasses"):
        assert part in prompt
    assert "Dress each person for their OWN time and job" in prompt


def test_someone_in_modern_clothes_keeps_nothing_of_an_old_tale():
    spec = sa.clean_spec({"outfit": "uniform", "figure": "man", "hair": "braid", "marking": "stripe", "ornaments": ["halo", "glasses"], "weapon": "sword",
                          "headgear": "helmet"})
    assert (spec["hair"], spec["marking"], spec["ornaments"], spec["weapon"], spec["headgear"]) == ("short", "none", ["glasses"], "none", "none")
    kept = sa.clean_spec({"outfit": "suit", "headgear": "turban", "marking": "scar", "figure": "woman", "hair": "braid", "ornaments": ["earrings"]})
    assert (kept["headgear"], kept["marking"], kept["hair"], kept["ornaments"]) == ("turban", "scar", "braid", ["earrings"])
    old = sa.clean_spec({"outfit": "armour", "ornaments": ["halo"], "weapon": "bow", "marking": "paint", "hair": "braid"})
    assert old["ornaments"] == ["halo"] and old["weapon"] == "bow" and old["marking"] == "paint" and old["hair"] == "braid"


def test_a_long_name_is_kept_whole():
    name = "Konstantin Fyodorovich Borodin"
    script = {"sections": [{"title": "t", "narration": f"{name} taught him."}]}
    plan, _ = case_story.check_plan({"characters": {name: {}}, "sections": [{"beats": [{"sentence": 1, "character": name}]}]}, script, library={})
    assert list(plan["characters"]) == [name] and plan["sections"][0]["beats"][0]["name"] == name
