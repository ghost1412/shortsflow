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
