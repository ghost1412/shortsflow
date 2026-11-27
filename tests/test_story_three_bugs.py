"""A saved person is reused only when clearly named; a new face never takes another's only one; what is needed and not shown is reported."""
from engine import case_story, story_review

RAMAYANA = {"title": "The story of the Ramayana", "sections": [{"narration": "Rama was the prince of Ayodhya. The prince left with Sita. Grandmother told it once."}]}


def test_a_title_like_the_prince_never_leaks_into_another_story():
    saved = {"The Prince": {"x": 1}, "Rama": {"x": 2}, "Sita": {"x": 3}, "Grandmother": {"x": 4}, "prince": {"x": 5}, "Ayodhya Guard": {"x": 6}}
    assert set(case_story.named_here(saved, RAMAYANA)) == {"Rama", "Sita"}


def test_a_proper_name_counts_wherever_it_stands_and_a_role_or_an_ordinary_word_does_not():
    assert case_story.clearly_named("Rama", "Rama was a prince.")
    assert case_story.clearly_named("King Saul", "King Saul waited.")
    assert not case_story.clearly_named("Grandmother", "Grandmother waited.")
    assert not case_story.clearly_named("Hope", "Hope came late, and with it hope of rain.")
    assert not case_story.clearly_named("The Prince", "The Prince waited. Then The Prince left.")


def beat(k, who):
    return {"sentence": k, "character": who, "name": who or "card", "role": "", "mood": "", "emblem": "", "big": "", "label": ""}


def test_a_new_face_does_not_take_anothers_only_appearance():
    plan = {"characters": {}, "sections": [{"beats": [beat(1, "Rama"), beat(3, "Sita")]}]}
    assert not story_review._put_on_screen(plan, {"section": 0, "sentence": 3, "count": 4}, "Lakshmana")
    assert [b["character"] for b in plan["sections"][0]["beats"]] == ["Rama", "Sita"]


def test_a_face_that_is_seen_again_elsewhere_can_give_way():
    plan = {"characters": {}, "sections": [{"beats": [beat(1, "Rama"), beat(3, "Rama")]}]}
    assert story_review._put_on_screen(plan, {"section": 0, "sentence": 3, "count": 3}, "Lakshmana")
    assert [b["character"] for b in plan["sections"][0]["beats"]] == ["Rama", "Lakshmana"]


def test_whoever_is_needed_and_ends_up_off_screen_is_reported_once():
    plan = {"characters": {"Rama": {}}, "sections": [{"beats": [beat(1, "Rama")]}]}
    report = {"left": [{"name": "Sugriva", "kind": "person", "why": "limit"}]}
    wanted = [{"name": n, "kind": "person"} for n in ("Rama", "Sita", "Sugriva")] + [{"name": "bridge", "kind": "thing"}]
    story_review.note_lost(plan, wanted, report)
    assert [(x["name"], x["why"]) for x in report["left"]] == [("Sugriva", "limit"), ("Sita", "no picture of them is on screen")]
