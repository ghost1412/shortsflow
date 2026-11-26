"""The story look's reading and drawing kit: a long page's plot is read first; women, bald heads, markings, more weapons and objects; a mood for the moment."""
import json
import os
import xml.dom.minidom

from engine import case_story as st, case_study as cs, story_art as sa


def page(*parts):
    return "<html><body>" + "".join(parts) + "</body></html>"


def paragraphs(word, n):
    return "".join(f"<p>The {word} sentence number {i} says something plain about the {word} part of this long page.</p>" for i in range(n))


LONG = page(paragraphs("opening", 40), "<h2>Gameplay</h2>", paragraphs("gameplay", 200), "<h2><span>Synopsis</span></h2><h3>Setting</h3>", paragraphs("setting", 20),
            "<h3>Plot</h3>", paragraphs("telling", 30), "<h2>Reception</h2>", paragraphs("reception", 50))


def test_a_story_video_reads_the_plot_right_after_the_opening_even_on_a_long_page():
    plain = cs.gather_sources(["https://x.test/a"], fetch=lambda u: LONG)[0][0]["text"]
    story = cs.gather_sources(["https://x.test/a"], fetch=lambda u: LONG, focus="story")[0][0]["text"]
    assert "telling sentence" not in plain                                   # past the limit: the model never saw the story
    assert story.index("telling sentence") < cs.LEAD_CHARS + 600 and story.startswith(plain[:cs.LEAD_CHARS])
    assert len(story) <= cs.MAX_SOURCE_CHARS and story.count("setting sentence") == 0     # the Plot heading wins over the whole Synopsis


def test_a_heading_that_only_sums_up_is_used_when_there_is_no_plot_and_a_page_without_either_is_read_as_before():
    only = page(paragraphs("opening", 60), "<h2>Gameplay</h2>", paragraphs("gameplay", 200), "<h2>Synopsis</h2>", paragraphs("summed", 20))
    assert "summed sentence" in cs.story_text(only)[:cs.MAX_SOURCE_CHARS]
    none = page(paragraphs("opening", 60), "<h2>Plotting devices</h2>", paragraphs("devices", 20))
    assert cs.story_text(none) == cs._plain(none)
    short = page(paragraphs("opening", 60), "<h2>Plot</h2><p>Too short.</p>")
    assert cs.story_text(short) == cs._plain(short)


def test_women_children_bald_heads_and_markings_are_drawn_and_a_woman_has_long_hair_and_no_beard():
    woman = sa.clean_spec({"figure": "woman", "facial_hair": "long_beard"})
    assert woman["hair"] == "long" and woman["facial_hair"] == "none" and sa.clean_spec({})["hair"] == "short"
    assert sa.clean_spec({"age": "old"})["hair_colour"] == "white" and sa.clean_spec({"figure": "dragon", "hair": "mohawk", "marking": "glitter"})["figure"] == "man"
    for figure in sa.FIGURES:
        for hair in sa.HAIR:
            for marking in sa.MARKINGS:
                xml.dom.minidom.parseString(sa.character_svg({"figure": figure, "hair": hair, "marking": marking, "headgear": "crown"}))
    assert sa.character_svg({"figure": "woman"}) != sa.character_svg({"figure": "man"})
    assert sa.character_svg({"marking": "stripe"}) != sa.character_svg({"marking": "none"})
    for weapon in sa.WEAPONS:
        xml.dom.minidom.parseString(sa.character_svg({"weapon": weapon}))
    assert "scale(0.8)" in sa.character_svg({"figure": "child"})


def test_a_feather_sits_in_the_hair_of_a_bare_head_and_not_where_a_crown_would_be():
    bare = sa.character_svg({"ornaments": ["feather"]})
    crowned = sa.character_svg({"ornaments": ["feather"], "headgear": "crown"})
    assert "translate(374 214)" in bare and "translate(372 96)" in crowned


def test_a_beat_can_change_the_mood_and_each_mood_is_its_own_drawing(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "lib"))
    script = {"title": "t", "sections": [{"scene": "story", "title": "a", "narration": "He flies. He falls. He is gone."}]}
    plan = {"characters": {"Icarus": {"mood": "proud"}}, "sections": [{"beats": [{"sentence": 1, "character": "Icarus"}, {"sentence": 2, "character": "Icarus", "mood": "sad"},
                                                                             {"sentence": 3, "character": "Icarus", "mood": "ecstatic"}]}]}
    out = st.attach(script, str(tmp_path), "9:16", lambda p: json.dumps(plan), [[]], [(0.0, 9.0)])[0]["beats"]
    assert out[0]["character"] != out[1]["character"] and out[0]["character"] == out[2]["character"]       # an unknown mood keeps the person's own
    assert os.path.isfile(out[1]["character"]) and st.load_library(str(tmp_path / "lib"))["Icarus"]["mood"] == "proud"


def test_the_planner_is_told_about_every_part_it_may_choose():
    prompt = st.request({"sections": [{"narration": "A. B.", "title": "t"}]}, {})
    for word in ("woman", "bald", "stripe", "twin_blades", "lightning", "wings", "ashen", "mood"):
        assert word in prompt, word


def faces(*who):
    return {"characters": {}, "sections": [{"beats": [{"sentence": n, "character": c, "name": c, "role": "", "mood": "", "emblem": "", "big": "", "label": ""} for n, c in who]}]}


def one(narration):
    return {"sections": [{"narration": narration}]}


def test_a_sentence_about_an_object_gets_a_card_and_the_face_comes_back_after_it():
    plan = st.add_object_cards(faces((1, "Kratos")), one("Kratos climbs. Zeus throws his lightning bolt. Kratos falls."))
    beats = plan["sections"][0]["beats"]
    assert [(b["sentence"], b["character"], b["emblem"]) for b in beats] == [(1, "Kratos", ""), (2, None, "lightning"), (3, "Kratos", "")]
    assert beats[1]["name"] == "The Thunderbolt"


def test_no_card_hides_a_new_face_or_the_first_sentence_and_a_planned_card_is_enough():
    new_face = st.add_object_cards(faces((1, "A"), (2, "B")), one("A waits. B opens the box."))
    assert [b["character"] for b in new_face["sections"][0]["beats"]] == ["A", "B"]
    first = st.add_object_cards(faces((1, "A")), one("The box is open."))
    assert [b["emblem"] for b in first["sections"][0]["beats"]] == [""]
    planned = faces((1, "A"))
    planned["sections"][0]["beats"].append({"sentence": 2, "character": None, "name": "X", "emblem": ""})
    assert len(st.add_object_cards(planned, one("A. The box. The wheel."))["sections"][0]["beats"]) == 2


def test_each_object_gets_one_card_a_video_gets_three_at_most_and_words_inside_words_do_not_count():
    script = {"sections": [{"narration": n} for n in ("A. The box.", "A. The box again.", "A. A wheel.", "A. A sword.", "A. His wings.")]}
    plan = {"characters": {}, "sections": [faces((1, "A"))["sections"][0] for _ in range(5)]}
    cards = [b["emblem"] for s in st.add_object_cards(plan, script)["sections"] for b in s["beats"] if not b["character"]]
    assert cards == ["box", "wheel", "sword"]
    none = st.add_object_cards(faces((1, "A")), one("A. The boxer paid a surprising amount on Sunday."))
    assert all(b["character"] for b in none["sections"][0]["beats"])
