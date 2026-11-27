"""A clip's first words that lean on what came before are cut; the sentence stays."""
import pytest

from engine import highlight_quality as hq


@pytest.mark.parametrize("line, cut", [
    ("So, in that sense, there are also interesting movements on this", 4),
    ("Because quantitative metrics tend to miss what matters", 1),
    ("So, actually, we have an in-between period", 2),
    ("And I mean, the whole thing changed that year", 3),
    ("So I quit my job and moved away", 0),                      # a real opening
    ("Because of the war the school closed that spring", 0),
    ("Actually this is the part nobody tells you", 0),
    ("So, yes. That is the whole story", 0),                     # never past the end of a sentence
    ("And then we left.", 4 * 0 + 0),                            # too little would be left
    ("There are three reasons this fails", 0),
    ("And so there needs to be a recognition", 2),
])
def test_which_words_are_cut(line, cut):
    assert hq.lead_in_length(line.split()) == cut


def transcript(text, start=10.0, step=0.4):
    words = [{"word": w, "start": start + i * step, "end": start + i * step + 0.35} for i, w in enumerate(text.split())]
    return {"segments": [{"start": words[0]["start"], "end": words[-1]["end"], "text": text, "words": words}]}


TEXT = "We saw it. So, in that sense, there are interesting movements on research assessment and it takes a long time to get there but it is moving now for good."


def test_the_start_moves_past_the_lead_in_and_stays_there_on_a_second_pass():
    data = transcript(TEXT)
    clip = {"start": 11.2, "end": 22.0}
    once = hq.snap_highlights([clip], data, min_len=5.0)[0]
    there = next(w for w in data["segments"][0]["words"] if w["word"] == "there")
    assert there["start"] - 0.1 <= once["start"] <= there["start"]
    assert once["lead_trim"] > 1.0
    assert hq.snap_highlights([once], data, min_len=5.0)[0]["start"] == once["start"]


def test_a_moment_the_user_chose_is_cut_as_given():
    clip = {"start": 11.2, "end": 22.0, "user_moment": True}
    assert hq.snap_highlights([clip], transcript(TEXT), min_len=5.0)[0]["start"] == 11.2
