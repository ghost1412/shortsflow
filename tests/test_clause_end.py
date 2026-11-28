"""A clip cut inside a very long sentence stops at a comma or a breath, not on "... development on the"."""
from engine import highlight_quality as hq


def run_on(comma_after="yet,", pause_after=None):
    text = ("We saw it. " + "and so we kept going with the work on " * 3 + "the data side where there is no policy " + comma_after +
            " this is much harder but there has been a lot of development on the " + "side of the systems that people use " * 8 + "today.")
    words, t = [], 10.0
    for w in text.split():
        words.append({"word": w, "start": round(t, 2), "end": round(t + 0.35, 2)})
        t += 1.2 if w == pause_after else 0.4
    return {"segments": [{"start": words[0]["start"], "end": words[-1]["end"], "text": text, "words": words}]}


def last_word(data, clip):
    return [w["word"] for w in data["segments"][0]["words"] if w["start"] < clip["end"] - 0.05][-1]


def cut_on_the(data):
    words = data["segments"][0]["words"]
    first = words[3]["start"]
    on_the = next(w for i, w in enumerate(words) if w["word"] == "the" and words[i - 1]["word"] == "on" and words[i - 2]["word"] == "development")
    return {"start": first, "end": on_the["end"] + 0.02}


def test_the_clip_stops_after_the_nearest_comma_and_stays_there_on_a_second_pass():
    data = run_on()
    clip = hq.snap_highlights([cut_on_the(data)], data, min_len=8.0)[0]
    assert clip["clause_end"] and last_word(data, clip) == "yet,"
    assert hq.snap_highlights([clip], data, min_len=8.0)[0]["end"] == clip["end"]


def test_with_no_comma_or_breath_the_clip_is_left_as_it_was():
    data = run_on(comma_after="yet")
    asked = cut_on_the(data)
    assert not hq.snap_highlights([asked], data, min_len=8.0)[0].get("clause_end")


def test_a_clip_that_ends_a_sentence_is_untouched():
    data = {"segments": [{"words": [{"word": w, "start": 10.0 + i * 0.5, "end": 10.4 + i * 0.5} for i, w in
                                    enumerate("One two three, four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty. Next line here.".split())]}]}
    clip = hq.snap_highlights([{"start": 10.0, "end": 20.0}], data, min_len=8.0)[0]
    assert not clip.get("clause_end") and last_word(data, clip) == "twenty."


def test_a_moment_chosen_by_the_user_is_cut_as_given():
    data = run_on()
    asked = dict(cut_on_the(data), user_moment=True)
    assert hq.snap_highlights([asked], data, min_len=8.0)[0]["end"] == asked["end"]
