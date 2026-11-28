"""A clip's subtitle file holds only what is said inside the clip, on the clip's own timeline."""
import json

from engine import pipeline, video_gen


def seg(text, start, step=0.5):
    words = text.split()
    return {"start": start, "end": start + step * len(words), "text": " " + text,
            "words": [{"word": " " + w, "start": start + step * i, "end": start + step * i + step - 0.05} for i, w in enumerate(words)]}


def test_a_segment_that_began_before_the_clip_keeps_only_the_words_inside_it():
    segs = [seg("And how is the movement changing things", 10.0)]          # "And" 10.0-10.45, "how" from 10.5
    cues = pipeline.clip_cues(segs, 10.5, 30.0)
    assert [c["text"] for c in cues] == ["how is the movement changing things"] and cues[0]["start"] == 0.0


def test_words_after_the_clip_end_are_left_out_and_times_are_relative():
    cues = pipeline.clip_cues([seg("one two three four five six", 100.0)], 99.0, 102.0)
    assert cues[0]["text"] == "one two three four" and abs(cues[0]["start"] - 1.0) < 1e-6 and cues[0]["end"] <= 3.0


def test_a_segment_without_word_times_keeps_its_text_clamped_to_the_clip():
    cues = pipeline.clip_cues([{"start": 8.0, "end": 14.0, "text": " Hello there"}], 10.0, 12.0)
    assert cues == [{"start": 0.0, "end": 2.0, "text": "Hello there"}]


def test_chinese_words_are_not_given_spaces():
    s = {"start": 0.0, "end": 1.0, "text": "你好", "words": [{"word": "你", "start": 0.0, "end": 0.4}, {"word": "好", "start": 0.4, "end": 0.9}]}
    assert pipeline.cue_text(s) == "你好"


def test_export_srt_writes_the_words_the_segment_has(tmp_path):
    out = tmp_path / "a.srt"
    pipeline.export_srt({"segments": pipeline.clip_cues([seg("And how is it going", 10.0)], 10.5, 20.0)}, str(out))
    assert "how is it going" in out.read_text(encoding="utf-8") and "And" not in out.read_text(encoding="utf-8")


def test_the_tightened_transcript_is_found_only_for_a_segment_cut_in_this_run(tmp_path):
    segment, transcript = str(tmp_path / "seg_0.mp4"), tmp_path / "transcript_clip_0.json"
    transcript.write_text(json.dumps({"segments": []}), encoding="utf-8")
    video_gen._save_tight(segment, str(transcript))
    assert video_gen.load_tight(segment) == str(transcript)
    video_gen._save_tight(segment, "")                       # the next cut of this segment was not tightened
    assert video_gen.load_tight(segment) is None
    assert video_gen.load_tight(str(tmp_path / "seg_9.mp4")) is None
