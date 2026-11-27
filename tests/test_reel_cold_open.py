"""A cold open on the highlights video keeps its chapters and subtitles in time; the reel's subtitles cover every moment."""
import argparse
import json

from engine import chapters, cold_open, reel_captions
from engine.modes import clip_extract

HIGHLIGHTS = [{"start": 100.0, "end": 130.0}, {"start": 500.0, "end": 540.0}]
TRANSCRIPT = {"segments": [
    {"start": 101.0, "end": 104.0, "text": "First moment line."},
    {"start": 128.0, "end": 135.0, "text": "It runs past the cut."},
    {"start": 300.0, "end": 303.0, "text": "Not in the reel."},
    {"start": 505.0, "end": 508.0, "text": "Second moment line."}]}


def pieces(tmp_path, count=2):
    folder = tmp_path / "temp_segments"
    folder.mkdir()
    for i in range(count):
        (folder / f"seg_{i}.mp4").write_bytes(b"x" * 2000)
    return str(folder)


def test_parts_follow_the_pieces_that_are_there(tmp_path):
    folder = pieces(tmp_path, 1)
    assert reel_captions.reel_parts(HIGHLIGHTS, folder, seconds=lambda p: 29.5) == [(100.0, 130.0, 29.5)]


def test_the_reels_subtitles_cover_every_moment_on_the_reels_own_clock():
    cues = reel_captions.reel_cues([(100.0, 130.0, 30.0), (500.0, 540.0, 40.0)], TRANSCRIPT, 0.25)
    assert [c["text"] for c in cues] == ["First moment line.", "It runs past the cut.", "Second moment line."]
    assert cues[0]["start"] == 1.0 and cues[1]["end"] == 30.0 and cues[2]["start"] == 34.75
    shifted = cold_open.shift_cues(cues, {"duration": 4.0, "text": "Teaser."})
    assert shifted[0] == {"start": 0.0, "end": 4.0, "text": "Teaser."} and shifted[-1]["start"] == 38.75


def test_chapters_move_later_and_the_first_still_starts_at_zero():
    before = [{"start": 0.0, "end": 60.0, "title": "A", "timestamp": "0:00"}, {"start": 59.75, "end": 120.0, "title": "B", "timestamp": "0:59"}]
    after = chapters.delay(before, 5.0)
    assert [(c["start"], c["end"], c["timestamp"]) for c in after] == [(0.0, 65.0, "0:00"), (64.75, 125.0, "1:04")]
    assert chapters.delay(before, 0.0) == before and before[1]["start"] == 59.75


def test_the_reel_gets_its_teaser_from_its_own_words_and_is_not_held_under_a_minute(tmp_path, monkeypatch):
    pieces(tmp_path)
    words = {"segments": [dict(s, words=[{"word": w, "start": s["start"] + i * 0.5, "end": s["start"] + i * 0.5 + 0.4} for i, w in enumerate(s["text"].split())])
                          for s in TRANSCRIPT["segments"]]}
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps(words), encoding="utf-8")
    monkeypatch.setattr(reel_captions, "clip_seconds", lambda p: 30.0)
    seen = {}

    def fake(video, given, hint=None, score_fn=None, max_total=cold_open.MAX_TOTAL):
        seen.update(words=given, max_total=max_total)
        return {"start": 1.0, "end": 3.0, "duration": 2.0, "text": "x"}
    monkeypatch.setattr(cold_open, "apply_to_clip", fake)
    monkeypatch.setattr(cold_open, "load_applied", lambda v: None)
    monkeypatch.setattr(cold_open, "save_applied", lambda v, i: None)
    info = clip_extract.cold_open_reel(argparse.Namespace(tighten=False), str(tmp_path), HIGHLIGHTS, "reel.mp4", str(path))
    assert info["duration"] == 2.0 and seen["max_total"] is None
    first = seen["words"][0]
    assert first["word"] == "First" and first["start"] == 1.0 and round(first["end"], 2) == 1.4
    assert clip_extract.cold_open_reel(argparse.Namespace(tighten=True), str(tmp_path), HIGHLIGHTS, "reel.mp4", str(path))      # cut pauses no longer rule it out


def test_a_mic_check_written_as_one_number_is_still_a_mic_check():
    from engine import highlight_quality as q
    for said in ("Testing 123 testing.", "testing, 1 2 3", "Testing testing.", "Testing one two.", "Testing, 12."):
        assert q.weak_opening(said), said
    for said in ("Testing 100 users taught us a lot.", "Testing is how we found the bug.", "We spent a year testing it."):
        assert not q.weak_opening(said), said
