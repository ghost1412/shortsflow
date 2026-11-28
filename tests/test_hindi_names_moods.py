"""One person, one picture, in a Hindi story whose plan uses English names; and a mood for every spoken section."""
from engine import case_story as cs
from engine import expressive_voice as ev

TOLD = "अकबर ने इनाम रखा। बीरबल ने खिचड़ी लटकाई। कबीर ने गीत गाया।"
SCRIPT = {"title": "t", "sections": [{"id": "a", "title": "x", "narration": TOLD}]}


def test_the_same_name_in_two_alphabets_sounds_the_same_and_a_near_name_does_not():
    assert cs.name_sound("Akbar") == cs.name_sound("अकबर") and cs.name_sound("Birbal") == cs.name_sound("बीरबल")
    assert cs.name_sound("Kabir") == cs.name_sound("कबीर") != cs.name_sound("अकबर")
    assert cs.narrations_spelling("Akbar", TOLD) == "अकबर" and cs.narrations_spelling("Kabir", TOLD) == "कबीर"
    assert cs.narrations_spelling("Man", "वह पानी में खड़ा रहा।") is None      # not the word for "in"
    assert cs.narrations_spelling("Mina", "वह पानी में खड़ा रहा।") is None
    assert cs.narrations_spelling("Akbar", "Akbar ruled.") is None


def test_the_plans_english_names_become_the_storys_spelling():
    reply = {"characters": {"Akbar": {"headgear": "crown"}, "Birbal": {}}, "sections": [{"beats": [
        {"sentence": 1, "character": "Akbar", "name": "Akbar"}, {"sentence": 2, "character": "Birbal"}]}]}
    plan, problem = cs.check_plan(reply, SCRIPT, library={})
    assert plan, problem
    assert sorted(plan["characters"]) == sorted(["अकबर", "बीरबल"]) and plan["characters"]["अकबर"]["headgear"] == "crown"
    assert [(b["character"], b["name"]) for b in plan["sections"][0]["beats"]] == [("अकबर", "अकबर"), ("बीरबल", "बीरबल")]


def test_sections_without_a_mood_are_not_all_spoken_alike():
    texts = ["Once there was a king.", "He set a test.", "The man waited all night.", "Who would help him now?", "The king paid him."]
    moods = [ev.mood_for(None, t, i, len(texts)) for i, t in enumerate(texts)]
    assert moods[0] == "tense" and moods[-1] == "warm" and len({ev.MOODS[m] for m in moods}) >= 3
    assert ev.mood_for("calm", "Run!", 0, 5) == "calm" and ev.mood_for(None, "Run!", 2, 5) == "excited"
