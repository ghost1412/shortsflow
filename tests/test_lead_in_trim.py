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
    ("So in that sense, there are interesting movements", 4),
    ("So in that case we all went home", 0),
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


def story():
    return transcript("We saw it. So, the first launch changed how every one of us thought about that work. And then the second one failed in front "
                      "of the whole team that had built it. We learned more from that day than from any other day in the whole of the program. It "
                      "still shapes what we do now and what we will do next year and the one after that.", step=0.8)


def test_the_reels_opening_check_does_not_jump_past_a_sentence_it_has_already_cleaned():
    data = story()
    words = data["segments"][0]["words"]
    start = next(w for w in words if w["word"] == "So,")["start"]
    snapped = hq.snap_highlights([{"start": start, "end": words[-1]["end"]}], data, min_len=8.0, max_len=180.0)
    assert snapped[0]["lead_trim"] > 0
    assert hq.polish_reel(snapped, data, None)[0]["start"] == snapped[0]["start"]
