"""A clip title is made of words, and a built-in action title claims nothing about what happens on screen."""
import json
import re

from engine import game_moments, social_gen


def ask_with(*titles):
    replies = iter(titles)
    return lambda prompt: json.dumps({"title": next(replies), "description": "What happened here?"})


def test_a_title_of_numbers_only_is_asked_for_again():
    got = social_gen.ground_clip_metadata({"title": "1044?! 😳", "description": ""}, "1044 positive ID on the vehicle.",
                                          ask=ask_with("Positive ID on the vehicle"))
    assert got["title"] == "Positive ID on the vehicle"


def test_when_the_rewrite_is_numbers_too_words_from_the_clip_are_used():
    parsed = {"title": "1044?!", "description": ""}
    assert social_gen.ground_clip_metadata(dict(parsed), "Positive ID. 1044.", ask=ask_with("1044!"))["title"] == "Positive ID"
    assert social_gen.ground_clip_metadata(dict(parsed), "1044. 1044.", hook="Things got intense", ask=ask_with("1044"))["title"] == "Things got intense"


def test_a_title_in_another_alphabet_is_kept():
    title = "कहानी"
    assert social_gen.ground_clip_metadata({"title": title, "description": ""}, title, ask=None)["title"] == title


def test_action_titles_do_not_say_what_happens():
    claims = re.compile(r"(fight|battle|boss|race|chase|win|kill|death|ending|at the end|everyone)", re.I)
    assert not [t for t in game_moments.ACTION_HOOKS if claims.search(t)]
