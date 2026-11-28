"""A chapter title written as a heading is not thrown out for its capitals."""
from engine import chapters as ch

SAID = "eye retinal issues and there are four different maladies that happen to your eyeball when you are up here for 6 months"


def test_a_short_heading_in_the_models_own_words_is_kept():
    assert ch.grounded_title("Eye Health Issues", SAID)


def test_a_heading_about_something_never_said_is_not():
    assert not ch.grounded_title("Rocket Fuel Prices", SAID)


def test_invented_numbers_and_invented_names_in_a_sentence_are_still_refused():
    assert not ch.grounded_title("Eye Issues After 9 Months", SAID)
    assert not ch.grounded_title("What happens to eyes in Houston", SAID)


def test_an_unreadable_reply_is_asked_again_and_then_said_out_loud(capsys):
    replies = ["not json", {"titles": ["Eye Health Issues"]}]
    assert ch.llm_titles([SAID], ask=lambda p: replies.pop(0)) == ["Eye Health Issues"]
    assert ch.llm_titles([SAID], ask=lambda p: "still not json") is None
    assert "using keywords" in capsys.readouterr().out


def test_a_refused_title_is_asked_for_once_more_and_only_then_replaced_by_keywords(capsys):
    highlights = [{"start": 0.0, "end": 20.0}, {"start": 30.0, "end": 50.0}, {"start": 60.0, "end": 80.0}]
    segments = [{"start": s, "end": s + 10, "text": t} for s, t in ((1.0, SAID), (31.0, "water flows along the channel to your mouth"), (61.0, "we are returning to Earth soon"))]
    replies = [{"titles": ["Eye Health Issues", "Rocket Fuel Prices", "Returning to Earth"]}, {"titles": ["Other", "Drinking From a Channel", "Other"]}]
    chapters = ch.build_chapters(highlights)
    ch.title_chapters(chapters, highlights, segments, ask=lambda p: replies.pop(0))
    assert [c["title"] for c in chapters] == ["Eye Health Issues", "Drinking From a Channel", "Returning to Earth"] and not replies
    assert "Rocket Fuel Prices" in capsys.readouterr().out
