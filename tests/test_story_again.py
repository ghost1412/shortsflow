"""A cast member comes back on screen in each section whose narration names them (a wolf is drawn when it kills the sheep, not only at its first mention)."""
from engine import story_review as sr

SCRIPT = {"sections": [
    {"narration": "A shepherd boy tricked the villagers. He shouted wolf for fun."},
    {"narration": "The wolf came for real. The wolf ate the sheep."},
    {"narration": "The boy cried for help. Nobody came."},
]}


def beat(sentence, character):
    return {"sentence": sentence, "character": character, "name": character, "role": "", "emblem": "", "big": "", "label": ""}


def plan():
    return {"characters": {"Boy": {"figure": "child"}, "Wolf": {"creature": "x.svg"}, "Villager": {"figure": "man"}},
            "sections": [{"beats": [beat(1, "Boy"), beat(2, "Wolf")], "props": []},
                         {"beats": [beat(1, "Boy")], "props": []},
                         {"beats": [beat(1, "Boy")], "props": []}]}


def test_a_card_that_names_a_drawn_creature_shows_it_and_not_a_symbol():
    p = {"characters": {"Boy": {"figure": "child"}, "Wolf": {"creature": "x.svg"}},
         "sections": [{"beats": [{"sentence": 1, "character": None, "name": "Wolf", "emblem": "spear", "big": "", "label": ""},
                                 {"sentence": 2, "character": None, "name": "Dawn", "emblem": "sun", "big": "", "label": ""},
                                 {"sentence": 3, "character": None, "name": "Wolf", "emblem": "", "big": "2024", "label": ""}], "props": []}]}
    report = {}
    sr.creatures_as_figures(p, report)
    first, other, dated = p["sections"][0]["beats"]
    assert first["character"] == "Wolf" and first["emblem"] == "" and report["figures"][0]["was"] == "spear"
    assert other["emblem"] == "sun" and not other["character"]                 # a card for something else keeps its symbol
    assert dated["big"] == "2024" and not dated["character"]                   # a card that shows a date is left alone


def test_the_sentence_where_the_wolf_is_the_subject_beats_an_earlier_mention_and_a_one_sentence_section_is_left_alone():
    script = {"sections": [{"narration": "Hello there. Fine."},
                           {"narration": "When the boy cried wolf for real, nobody came. The wolf easily killed the sheep."},
                           {"narration": "The real wolf appeared, and the boy cried for help."}]}
    p = {"characters": {"Boy": {"figure": "child"}, "Wolf": {"creature": "x.svg"}},
         "sections": [{"beats": [beat(1, "Wolf")], "props": []}, {"beats": [beat(1, "Boy")], "props": []}, {"beats": [beat(1, "Boy")], "props": []}]}
    report = {}
    sr.show_again(p, script, report)
    assert [(b["sentence"], b["character"]) for b in p["sections"][1]["beats"]] == [(1, "Boy"), (2, "Wolf")]        # "The wolf easily killed ...", not "cried wolf"
    assert [b["character"] for b in p["sections"][2]["beats"]] == ["Boy"]                                             # one sentence: kept as it was
    assert [(a["section"], a["sentence"]) for a in report["again"]] == [(2, 2)]


def test_the_wolf_is_shown_in_the_section_where_it_comes_for_real():
    p, report = plan(), {}
    sr.show_again(p, SCRIPT, report)
    second = {b["sentence"]: b["character"] for b in p["sections"][1]["beats"]}
    assert second[1] == "Wolf"                                         # "The wolf came for real."
    assert [(a["name"], a["section"], a["sentence"]) for a in report["again"]][0] == ("Wolf", 2, 1)


def test_the_face_before_comes_back_after_the_sentence_that_was_given_to_the_wolf():
    p = plan()
    sr.show_again(p, SCRIPT, {})
    assert [b["character"] for b in p["sections"][1]["beats"]] == ["Wolf", "Boy"]


def test_a_section_that_does_not_name_a_character_is_left_alone():
    p = plan()
    sr.show_again(p, SCRIPT, {})
    assert [b["character"] for b in p["sections"][2]["beats"]] == ["Boy"]          # nothing about the wolf or the villagers there


def test_a_sentence_that_already_shows_a_thing_is_never_taken_over():
    p = plan()
    p["sections"][1]["beats"][0]["emblem"] = "sword"
    sr.show_again(p, SCRIPT, {})
    assert p["sections"][1]["beats"][0]["character"] == "Boy"


def test_the_number_of_extra_appearances_is_limited():
    many = {"sections": [{"narration": "The wolf howled. " * 2} for _ in range(10)]}
    p = {"characters": {"Wolf": {"creature": "x.svg"}}, "sections": [{"beats": [beat(1, "Wolf")], "props": []}] + [{"beats": [beat(1, "Other")], "props": []} for _ in range(9)]}
    report = {}
    sr.show_again(p, many, report)
    assert len(report["again"]) <= sr.MAX_AGAIN
