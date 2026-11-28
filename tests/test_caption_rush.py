"""Caption times that cram words together are not used: the audio is listened to again, and failing that the words are spread out."""
from engine import expressive_voice as ev

TEXT = " ".join(f"word{i}" for i in range(20))


def heard(starts):
    return [{"word": f"word{i}", "start": s, "end": s + 0.3} for i, s in enumerate(starts)]


GOOD = heard([i * 0.5 for i in range(20)])
BAD = heard([i * 0.5 for i in range(10)] + [9.0 + i * 0.08 for i in range(10)])


def test_rushed_times_are_recognised_and_ordinary_quick_words_are_not():
    assert ev.rushed(ev.align(TEXT, BAD)) and not ev.rushed(ev.align(TEXT, GOOD))
    assert not ev.rushed(heard([0, 0.5, 0.6, 0.7, 0.8, 1.4, 2.0]))


def test_a_rushed_pass_is_listened_to_again():
    passes = [BAD, GOOD]
    got = ev.timed(TEXT, "a.mp3", lambda audio, text: passes.pop(0))
    assert not passes and [w["start"] for w in got] == [w["start"] for w in GOOD]


def test_when_every_pass_is_rushed_the_words_are_spread_over_the_speech():
    got = ev.timed(TEXT, "a.mp3", lambda audio, text: BAD)
    assert not ev.rushed(got) and got[0]["start"] == 0.0 and 9.5 < got[-1]["end"] <= 10.1 and len(got) == 20
