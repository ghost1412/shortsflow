"""Long stretches without words in a transcript are found and reported (engine/analysis.py: transcript_gaps, warn_transcript_gaps)."""
import json

from engine import analysis


def seg(a, b, text="words"):
    return {"start": a, "end": b, "text": text}


def test_a_long_stretch_without_words_is_a_gap_and_short_pauses_are_not():
    segs = [seg(0, 30), seg(35, 60), seg(200, 230)]
    assert analysis.transcript_gaps(segs) == [(60.0, 200.0)]
    assert analysis.transcript_gaps(segs, duration=232) == [(60.0, 200.0)]


def test_the_start_and_the_end_of_the_video_count_and_empty_text_does_not_fill_a_gap():
    assert analysis.transcript_gaps([seg(100, 120), seg(120, 400, "  ")], duration=400) == [(0.0, 100.0), (120.0, 400.0)]
    assert analysis.transcript_gaps([]) == [] and analysis.transcript_gaps([seg(0, 10)], duration=None) == []


def test_the_warning_names_the_stretch_and_a_broken_file_is_ignored(tmp_path, monkeypatch):
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps({"segments": [seg(0, 60), seg(400, 420)]}), encoding="utf-8")
    monkeypatch.setattr(analysis, "probe_duration", lambda v: 420)
    said = []
    analysis.warn_transcript_gaps(str(path), "v.mp4", log=said.append)
    assert len(said) == 1 and "1:00 to 6:40" in said[0] and "340 s" in said[0]
    analysis.warn_transcript_gaps(str(tmp_path / "missing.json"), "v.mp4", log=said.append)
    assert len(said) == 1
