"""A clip given the whole video's transcript shows only what is said in the clip: nothing from before it, on the first frame or ever."""
from engine.reel_captions import join_same_moment
from engine.remotion_renderer import caption_words


def transcript(words):
    return {"segments": [{"words": [{"word": w, "start": s, "end": e} for w, s, e in words]}]}


WHOLE = [("Hello", 1.0, 1.4), ("everyone", 1.4, 2.0), ("welcome", 50.0, 50.5), ("before.", 99.2, 99.96), ("There", 100.3, 100.6), ("are", 100.6, 100.9)]


def test_words_said_before_the_clip_never_reach_its_captions():
    got = join_same_moment(caption_words(transcript(WHOLE), 100.0))
    assert [w["word"] for w in got] == ["There", "are"]


def test_a_word_the_clip_starts_in_the_middle_of_stays_and_one_over_just_before_it_does_not():
    words = [("over", 99.5, 100.02), ("straddling", 99.8, 100.4), ("next", 100.5, 100.9)]
    assert [w["word"] for w in caption_words(transcript(words), 100.0)] == ["straddling", "next"]


def test_a_narrations_own_words_are_all_kept():
    words = [{"word": "One", "start": 0.0, "duration": 0.3}, {"word": "two", "start": 0.3}]
    assert [w["word"] for w in caption_words(words)] == ["One", "two"]
