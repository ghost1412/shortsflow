"""A Hindi story: a file per person, sentences end at the Hindi full stop, a Hindi opening line, and an honest end card."""
from engine import case_render, case_story, case_study

HINDI = "अकबर ने इनाम रखा। एक आदमी रात भर पानी में खड़ा रहा॥ बीरबल ने खिचड़ी लटकाई! क्या वह पकेगी?"


def test_hindi_names_never_share_a_file():
    names = ["अकबर", "बीरबल", "गरीब आदमी", "Akbar", "José", "!!!", "???"]
    slugs = [case_story._slug(n) for n in names]
    assert len(set(slugs)) == len(slugs) and all(slugs)
    assert case_story._slug("बीरबल") == "बीरबल" and case_story._slug("Old Woman") == "old_woman"     # vowel signs kept, old file names unchanged


def test_two_hindi_people_are_saved_and_read_back_separately(tmp_path):
    for name, colour in (("अकबर", "gold"), ("बीरबल", "blue")):
        case_story.save_character(name, case_story.story_art.clean_spec({"outfit_colour": colour}), str(tmp_path))
    got = case_story.load_library(str(tmp_path))
    assert [got[n]["outfit_colour"] for n in ("अकबर", "बीरबल")] == ["gold", "blue"]


def test_the_hindi_full_stop_ends_a_sentence():
    assert len(case_story.sentences(HINDI)) == 4
    assert len(case_study.split_sentences("雨が降った。川が増えた。")) == 2
    assert case_study.split_sentences("It rose 3.5 metres. Then it fell.") == ["It rose 3.5 metres.", "Then it fell."]
    assert case_study.clean_narration(HINDI, "अकबर बीरबल")[0].count(" ") > 5


def test_a_hindi_opening_line_is_accepted_and_a_stray_bracket_is_still_not():
    assert case_study.check_hook("क्या दूर का दीपक गर्मी देता है?")[0]
    assert not case_study.check_hook("{")[0] and not case_study.check_hook("7 8 9")[0]


def test_the_end_card_only_claims_a_name_check_it_could_make():
    assert case_render.names_can_be_checked({"sections": [{"narration": "Akbar offered a reward."}]})
    assert not case_render.names_can_be_checked({"sections": [{"narration": HINDI}]})
