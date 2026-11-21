import json

import numpy as np
import pytest

from engine import dubbing, speakers


def _voice(hz, seconds=2.0):
    t = np.arange(int(seconds * speakers.SAMPLE_RATE)) / speakers.SAMPLE_RATE
    return sum(np.sin(2 * np.pi * hz * k * t) / k for k in range(1, 6)).astype("float32") * 0.2


def _talk():
    """A low voice, then a high one, then the low one again (2 s each)."""
    audio = np.concatenate([_voice(110), _voice(220), _voice(110)])
    segs = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.0, "end": 4.0, "text": "b"}, {"start": 4.0, "end": 6.0, "text": "c"}]
    return audio, segs


def test_pitch_is_measured():
    audio = _voice(120)
    assert speakers.median_pitch(audio, 0, 2) == pytest.approx(120, rel=0.05)


def test_two_voices_are_told_apart_and_one_voice_is_left_alone():
    audio, segs = _talk()
    out, hz = speakers.label_segments("x.mp4", segs, samples=audio)
    assert [s["speaker"] for s in out] == [0, 1, 0]
    assert hz[0] < hz[1]
    same, hz_one = speakers.label_segments("x.mp4", segs, samples=np.concatenate([_voice(110)] * 3))
    assert "speaker" not in same[0] and len(hz_one) < 2


def test_voice_plan_follows_pitch_and_shifts_a_same_gender_pair():
    plan = speakers.voice_plan([110.0, 130.0, 220.0], "es")
    assert [p["gender"] for p in plan] == ["male", "male", "female"]
    assert plan[0]["voice"] == dubbing.EDGE_VOICES_MALE["es"] and plan[2]["voice"] == dubbing.EDGE_VOICES["es"]
    assert plan[0]["pitch_hz"] == 0 and plan[1]["pitch_hz"] != 0


def test_parse_speakers():
    assert [dubbing.parse_speakers(v) for v in (None, "off", "auto", "3")] == [1, 1, 4, 3]
    with pytest.raises(ValueError):
        dubbing.parse_speakers("9")
    with pytest.raises(ValueError):
        dubbing.parse_speakers("many")


def test_lines_of_two_speakers_are_never_joined():
    segs = [{"start": 0, "end": 1, "text": "a", "speaker": 0}, {"start": 1.1, "end": 2, "text": "b", "speaker": 1}]
    assert len(dubbing.merge_short_segments(segs)) == 2


def test_dub_gives_each_speaker_a_voice(tmp_path, monkeypatch):
    audio, segs = _talk()
    transcript = tmp_path / "t.json"
    transcript.write_text(json.dumps({"language": "en", "segments": segs}), encoding="utf-8")
    calls = []

    def fake_synth(text, lang, out, provider, voice, delivery="neutral", pitch_hz=0):
        calls.append((text, voice))
        with open(out, "wb") as f:
            f.write(b"x" * 500)

    monkeypatch.setattr(dubbing, "synthesize", fake_synth)
    monkeypatch.setattr(dubbing, "media_duration", lambda p: 1.0)
    llm = lambda prompt: json.dumps({"translations": [{"id": i, "text": f"t{i}"} for i in range(3)]})  # noqa: E731
    res = dubbing.dub_video("clip.mp4", "es", str(tmp_path), transcribe=lambda: str(transcript), llm=llm, speakers="auto",
                            label_speakers=lambda v, s, m: speakers.label_segments(v, s, m, samples=audio),
                            mixer=lambda *a, **k: None)
    voices = dict(calls)
    assert voices["t0"] == voices["t2"] == dubbing.EDGE_VOICES_MALE["es"]
    assert voices["t1"] == dubbing.EDGE_VOICES["es"]
    assert res["failed_voices"] == 0


def test_web_dub_args_add_the_speakers_flag_only_when_chosen():
    from shortsflow import web_args
    assert "--dub_speakers" not in web_args.dub_args("a.mp4", "es")
    both = web_args.dub_args("a.mp4", "es", speakers="auto")
    assert both[both.index("--dub_speakers") + 1] == "auto"
