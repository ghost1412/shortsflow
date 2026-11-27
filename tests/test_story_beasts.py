"""Animals and monsters are built from parts; the review uses them instead of a new drawing and never takes one for a person."""
import xml.dom.minidom

from engine import case_story, story_art as sa, story_beasts, story_review


def svg(**spec):
    text = sa.character_svg(spec)
    xml.dom.minidom.parseString(text)
    return text


def test_every_animal_draws_its_own_valid_picture_in_every_mood_and_dressed():
    seen = set()
    for species in story_beasts.ANIMALS:
        for mood in sa.MOODS:
            svg(species=species, mood=mood, ornaments=list(story_beasts.FEATURES))
        seen.add(svg(species=species))
        assert svg(species=species, outfit="suit", headgear="crown", weapon="staff") != svg(species=species)
    assert len(seen) == len(story_beasts.ANIMALS) and len(story_beasts.ANIMALS) >= 20
    assert all(a["coat"] in story_beasts.COATS for a in story_beasts.ANIMALS.values())


def test_monster_features_change_a_person_and_an_animal():
    for feature in story_beasts.FEATURES:
        assert svg(ornaments=[feature]) != svg() and svg(species="wolf", ornaments=[feature]) != svg(species="wolf")
    assert svg(hair="snakes") != svg(hair="short")


def test_a_spec_keeps_known_species_and_an_animal_wears_only_what_it_is_given():
    hare = sa.clean_spec({"species": "Hare", "coat_colour": "white"})
    assert (hare["species"], hare["coat_colour"], hare["outfit"]) == ("hare", "white", "none")
    person = sa.clean_spec({"species": "unicorn", "outfit": "none", "coat_colour": "white"})
    assert (person["species"], person["coat_colour"], person["outfit"]) == ("human", "", "simple")
    assert sa.is_beast(hare) and sa.is_beast(sa.clean_spec({"hair": "snakes"})) and not sa.is_beast(person)


def test_the_review_builds_a_creature_from_parts_when_it_can_and_keeps_it_on_screen():
    plan = {"characters": {"Hare": sa.clean_spec({"species": "human"})}, "sections": []}
    assert story_review._from_parts(plan, {"name": "Hare", "species": "hare", "features": []}) == "Hare" and plan["characters"]["Hare"]["species"] == "hare"
    assert story_review._from_parts(plan, {"name": "Medusa", "species": "human", "features": ["snake_hair"], "tone": "threatening"}) == "Medusa"
    assert plan["characters"]["Medusa"]["hair"] == "snakes" and plan["characters"]["Medusa"]["mood"] == "angry"
    assert story_review._from_parts(plan, {"name": "Minotaur", "species": "cow", "features": ["horns"]}) and "horns" in plan["characters"]["Minotaur"]["ornaments"]
    assert story_review._from_parts(plan, {"name": "dragon", "species": "other", "features": ["spread_wings"]}) is None
    assert story_review._from_parts(plan, {"name": "a monster", "species": "human", "features": []}) is None
    assert not story_review._drop_human_picture(plan, {"name": "Medusa", "kind": "creature"}) and "Medusa" in plan["characters"]


def test_the_planner_and_the_review_are_told_about_species():
    script = {"sections": [{"id": "a", "title": "t", "narration": "The Fox met the Crow."}]}
    prompt = case_story.request(script, {})
    assert "Never draw an animal as a human" in prompt and "hare" in prompt and "fangs" in prompt
    assert "species" in story_review.needed_question(script) and "snake_hair" in story_review.needed_question(script)
