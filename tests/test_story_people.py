"""A plan with blanks (a small model) must not turn children and an old woman into identical grown men."""
from engine import case_story as cs

SCRIPT = {"title": "Two in the woods", "sections": [{"id": "a", "title": "Home", "narration": (
    "Hansel and Gretel are the young children of a poor woodcutter. An old woman gives them a bed. "
    "The woman is a witch. Gretel saves her brother.")}]}
BLANK = {"characters": {"Hansel": {}, "Gretel": {}, "Old Woman": {"facial_hair": "beard"}, "Woodcutter": {}},
         "sections": [{"beats": [{"sentence": 1, "character": "Hansel"}]}]}


def planned():
    plan, problem = cs.check_plan(BLANK, SCRIPT, library={})
    assert plan, problem
    return plan["characters"]


def test_children_are_children_and_a_woman_by_name_has_no_beard():
    c = planned()
    assert [c[n]["figure"] for n in ("Hansel", "Gretel", "Old Woman", "Woodcutter")] == ["child", "child", "woman", "man"]
    assert c["Old Woman"]["age"] == "old" and c["Old Woman"]["facial_hair"] == "none"


def test_no_two_people_look_exactly_alike():
    looks = [tuple(spec[k] for k in cs.LOOK_KEYS) for spec in planned().values()]
    assert len(set(looks)) == len(looks)


def test_only_plain_statements_count():
    assert cs.facts_from("Anna", "Anna wrote about children for forty years. Her friend was a young girl once.") == {}
    assert cs.facts_from("Mira", "A little girl called Mira found the key.")["figure"] == "child"
    assert cs.facts_from("Ana", "He ran home to his sister Ana.") == {"girl": True, "figure": "woman"}
    assert cs.facts_from("Spider", "The children, Tom and Lucy, saw a Spider.") == {}
    assert cs.facts_from("Lucy", "The children, Tom and Lucy, saw it.")["figure"] == "child"


def test_a_saved_look_is_left_alone():
    saved = dict(cs.story_art.DEFAULT_SPEC)
    got = cs.tell_apart({"Asha": saved, "Ravi": dict(saved)}, fixed={"Asha"})
    assert got["Asha"] == saved and got["Ravi"]["outfit_colour"] != saved["outfit_colour"]
