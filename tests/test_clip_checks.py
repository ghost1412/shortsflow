"""The notes ShortsFlow makes about its own finished clips: what it noticed and an exact edit to try."""
from engine import clip_checks as cc
from engine import clip_report


def seg(start, text, step=0.4):
    words = text.split()
    return {"start": start, "end": start + step * len(words), "text": text,
            "words": [{"word": w, "start": start + step * i, "end": start + step * i + step - 0.05} for i, w in enumerate(words)]}


GOOD = [seg(10.0, "Why does nobody talk about this problem?"), seg(13.5, "Because the answer is surprisingly simple and quite old."),
        seg(18.0, "It started with a single experiment in a small lab."), seg(22.5, "Nobody expected the result that came out of it."),
        seg(27.0, "Years later the whole field changed because of that work."), seg(31.5, "That is the story I wanted to tell you today.")]


def codes(notes):
    return [n["code"] for n in notes]


def test_a_clip_that_stands_alone_gets_no_notes():
    assert cc.notes_for_clip(GOOD, 10.0, 35.0) == []


def test_an_opening_on_a_pronoun_is_noted_with_the_next_sentence_as_the_try():
    notes = cc.notes_for_clip(GOOD, 18.0, 36.0)
    assert codes(notes) == ["opening"] and "It started" in notes[0]["text"]
    assert "--start 22.5" in notes[0]["try"]


def test_an_opening_on_a_connective_is_noted():
    segs = [seg(10.0, "And then we went home for the day.")] + GOOD[1:]
    assert codes(cc.notes_for_clip(segs, 10.0, 34.0)) == ["opening"]


def test_a_clip_cut_off_mid_thought_is_noted_with_the_last_full_sentence_as_the_try():
    segs = GOOD[:5] + [seg(31.5, "That is the story about the people and")]
    notes = cc.notes_for_clip(segs, 10.0, 34.7)
    assert codes(notes) == ["ending"] and "--end" in notes[0]["try"]


def test_long_silence_is_noted_unless_the_run_already_tightened():
    segs = [seg(10.0, "Why does nobody talk about this problem?"), seg(18.0, "Because the answer is surprisingly simple and quite old."),
            seg(26.0, "Years later the whole field changed because of that work.")]
    assert "pauses" in codes(cc.notes_for_clip(segs, 10.0, 31.0))
    assert "pauses" not in codes(cc.notes_for_clip(segs, 10.0, 31.0, tightened=True))


def test_no_transcript_or_a_highlights_video_gives_empty_notes(tmp_path):
    highlights = [{"start": 1.0, "end": 30.0}]
    assert cc.notes_for_run(highlights, str(tmp_path)) == [[]]
    assert cc.notes_for_run(highlights, str(tmp_path), reel=True) == [[]]


def test_the_report_has_the_column_only_when_something_was_noticed():
    rows = clip_report.build_rows([{"start": 5, "end": 40}, {"start": 5, "end": 40}], [], [], "s",
                                  notes=[[{"code": "ending", "text": "It stops on that.", "try": "End it at 31.0 s."}], []])
    md = clip_report.to_markdown(rows)
    assert "Worth a look" in md and "End it at 31.0 s." in md and rows[1]["notes"] == ""
    assert "Worth a look" not in clip_report.to_markdown(clip_report.build_rows([{"start": 5, "end": 40}], [], [], "s"))
