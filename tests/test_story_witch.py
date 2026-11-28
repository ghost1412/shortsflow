"""A witch a model lists as a "creature" is a person the kit can draw: she must not go missing because no image model could check a new drawing."""
import json

from engine import case_story, story_review

SCRIPT = {"title": "Two in the woods", "sections": [{"id": "a", "title": "The house", "narration": (
    "Hansel and Gretel are young children. A witch lives in the house. Gretel runs away.")}]}


def covered(kind_extra, describe=None):
    plan, _ = case_story.check_plan({"characters": {"Gretel": {}}, "sections": [{"beats": [{"sentence": 1, "character": "Gretel"}]}]}, SCRIPT, library={})
    needed = {"needed": [{"name": "The Witch", "kind": "creature", "at": "1.2", "species": "human", **kind_extra}]}

    def ask(prompt):
        return json.dumps(needed if '"needed"' in prompt else {"people": describe or []})
    report = {"added": [], "left": [], "notes": [], "needed": []}
    story_review.review_coverage(plan, SCRIPT, ask, "unused", {}, None, None, report)
    return plan, report


def test_a_witch_without_monster_features_is_drawn_as_a_woman_even_when_the_model_describes_nobody():
    plan, report = covered({})
    witch = plan["characters"]["The Witch"]
    assert (witch["figure"], witch["age"], witch["facial_hair"]) == ("woman", "old", "none")
    assert [a["name"] for a in report["added"]] == ["The Witch"] and not report["left"]
    assert any(b["character"] == "The Witch" and b["sentence"] == 2 for b in plan["sections"][0]["beats"])


def test_a_witch_with_monster_features_is_still_built_as_a_creature():
    plan, _ = covered({"features": ["horns"]})
    assert "horns" in plan["characters"]["The Witch"]["ornaments"]


def test_someone_already_in_the_cast_but_never_shown_is_not_added_a_second_time():
    plan, _ = case_story.check_plan({"characters": {"Gretel": {}, "Witch": {"hair": "snakes"}}, "sections": [{"beats": [{"sentence": 1, "character": "Gretel"}]}]},
                                    SCRIPT, library={})
    assert plan["characters"]["Witch"]["hair"] == "long"                     # no snakes in this story

    def ask(prompt):
        return json.dumps({"needed": [{"name": "the witch", "kind": "creature", "at": "1.2", "species": "human"}]} if '"needed"' in prompt else {"people": []})
    story_review.review_coverage(plan, SCRIPT, ask, "unused", {}, None, None, {"added": [], "left": [], "notes": [], "needed": []})
    assert sorted(plan["characters"]) == ["Gretel", "Witch"]
    assert any(b["character"] == "Witch" for b in plan["sections"][0]["beats"])


def test_snakes_stay_where_the_story_has_them():
    assert case_story.no_stray_snakes("Medusa", {"hair": "snakes"}, "She turns men to stone.")["hair"] == "snakes"
    assert case_story.no_stray_snakes("Queen", {"hair": "snakes"}, "Her hair was a nest of serpents.")["hair"] == "snakes"
