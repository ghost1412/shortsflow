"""Whisper now and then gives spoken words no length: they must not vanish from captions, nor be trusted to cut a cold open."""
from engine import cold_open, reel_captions as rc

WORDS = [("Is", 6.76, 6.90), ("there", 6.90, 6.90), ("something", 6.90, 6.90), ("that", 6.90, 7.40), ("people", 7.40, 8.30)]


def test_words_with_no_length_are_shown_with_the_next_word():
    data = {"segments": [{"words": [{"word": w, "start": s, "end": e} for w, s, e in WORDS]}]}
    for part in ((0.0, 10.0, 10.0), (0.0, 10.0, 10.0, [[0.0, 10.0]])):       # untouched, and with its pauses cut
        shown = " ".join(t for _s, _e, t in rc.reel_words([part], data))
        assert shown == "Is there something that people"


def test_a_line_whose_first_words_have_no_timing_is_not_used_as_the_cold_open():
    def line(start, text, flat=0):
        words = text.split()
        return [{"word": w, "start": start + 0.5 * i, "end": start + 0.5 * i + (0.0 if i == flat - 1 else 0.45)} for i, w in enumerate(words)]
    early = line(0.0, "Here is how we started.") + line(6.0, "It took a long while.")
    broken = early + line(12.0, "Why would anyone hide this secret?", flat=2) + line(18.0, "That was the end of it.")
    sound = early + line(12.0, "Why would anyone hide this secret?") + line(18.0, "That was the end of it.")
    score = lambda t: 10.0 if "secret" in t else 1.0      # noqa: E731
    assert "secret" in cold_open.pick_hook(sound, 24.0, score_fn=score)["text"]
    assert "secret" not in (cold_open.pick_hook(broken, 24.0, score_fn=score) or {}).get("text", "")
    joined = [dict(w, word="would anyone hide") if w["word"] == "would" else w for w in sound if w["word"] not in ("anyone", "hide")]
    assert "secret" not in (cold_open.pick_hook(joined, 24.0, score_fn=score) or {}).get("text", "")
