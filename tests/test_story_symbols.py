"""A built-in symbol stays on a card only when the card's title has something to do with it."""
from engine import story_review as sr


def beat(sentence, character=None, name="", emblem=""):
    return {"sentence": sentence, "character": character, "name": name or character or "", "role": "", "mood": "", "emblem": emblem, "big": "", "label": ""}


def test_the_symbols_that_were_picked_at_random_by_a_small_model_are_taken_off():
    plan = {"characters": {"Jack": {}}, "sections": [{"beats": [beat(1, "Jack"), beat(2, name="Magic Beans", emblem="spear")]},
                                                     {"beats": [beat(1, "Jack"), beat(2, name="Beanstalk", emblem="wings")]},
                                                     {"beats": [beat(1, "Jack"), beat(2, name="House", emblem="crown")]},
                                                     {"beats": [beat(1, "Jack"), beat(2, name="Oven", emblem="wings")]}]}
    report = {}
    sr.drop_unrelated_symbols(plan, report)
    assert [b["character"] for s in plan["sections"] for b in s["beats"]] == ["Jack"] * 8
    assert [r["name"] for r in report["symbols"]] == ["Magic Beans", "Beanstalk", "House", "Oven"]


def test_symbols_that_fit_their_title_or_its_theme_stay():
    plan = {"characters": {"Jack": {}}, "sections": [{"beats": [beat(1, "Jack"), beat(2, name="The Duel", emblem="sword"), beat(3, name="Dawn", emblem="sun"),
                                                                beat(4, name="Betrayal", emblem="sword"), beat(5, name="The Crown", emblem="crown"),
                                                                beat(6, name="Flying Home", emblem="wings")]}]}
    report = {}
    sr.drop_unrelated_symbols(plan, report)
    assert [b["emblem"] for b in plan["sections"][0]["beats"]] == ["", "sword", "sun", "sword", "crown", "wings"] and report["symbols"] == []


def test_a_drawn_picture_and_a_date_card_are_not_judged_here():
    plan = {"characters": {}, "sections": [{"beats": [beat(1, name="Harp", emblem="custom:harp"),
                                                     dict(beat(2, name="Oven", emblem="wings"), big="1857")]}]}
    report = {}
    sr.drop_unrelated_symbols(plan, report)
    assert plan["sections"][0]["beats"][0]["emblem"] == "custom:harp" and plan["sections"][0]["beats"][1]["emblem"] == "wings" and report["symbols"] == []


def test_the_check_runs_only_for_a_plan_made_on_this_pc(monkeypatch):
    calls = []
    monkeypatch.setattr(sr, "review_pictures", lambda *a, **k: None)
    monkeypatch.setattr(sr, "review_coverage", lambda *a, **k: None)
    monkeypatch.setattr(sr, "show_again", lambda *a, **k: None)
    monkeypatch.setattr(sr, "drop_unrelated_symbols", lambda plan, report: calls.append(plan.get("planned_locally")))
    sr.run({"characters": {}, "sections": [], "planned_locally": True}, {"sections": []}, lambda p: "{}", ".", {}, vision=("", None, "none"))
    sr.run({"characters": {}, "sections": []}, {"sections": []}, lambda p: "{}", ".", {}, vision=("", None, "none"))
    assert calls == [True]


def test_a_card_with_nobody_to_give_the_screen_to_keeps_its_title_without_the_symbol():
    plan = {"characters": {}, "sections": [{"beats": [beat(1, name="Oven", emblem="wings")]}]}
    sr.drop_unrelated_symbols(plan, {})
    assert plan["sections"][0]["beats"][0]["emblem"] == "" and plan["sections"][0]["beats"][0]["name"] == "Oven"
