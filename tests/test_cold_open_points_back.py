"""A cold open never starts on a line that is about somebody the viewer has not heard of yet."""
from engine import cold_open


def line(start, text):
    return [{"word": w, "start": start + 0.5 * i, "end": start + 0.5 * i + 0.45} for i, w in enumerate(text.split())]


def test_a_line_starting_with_they_or_it_is_passed_over_for_one_that_stands_alone():
    words = (line(0.0, "Here is how we started.") + line(6.0, "It took a long while.") + line(12.0, "They've now called it the secret pillar!")
             + line(18.0, "Why would anyone hide the data?") + line(24.0, "That was the end of it."))
    score = lambda t: 10.0 if "secret" in t else 5.0 if "hide" in t else 1.0      # noqa: E731
    assert "hide the data" in cold_open.pick_hook(words, 30.0, score_fn=score)["text"]
    only_back = line(0.0, "Here is how we started.") + line(6.0, "It took a long while.") + line(12.0, "They've now called it the secret pillar!")
    assert cold_open.pick_hook(only_back, 20.0, score_fn=score) is None
