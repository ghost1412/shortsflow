import json
import os
import subprocess

from engine import expressive_voice as ev


def _wav(path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1", str(path)], check=True)
    return open(path, "rb").read()


def test_alignment_keeps_the_script_words_and_fills_the_gaps():
    heard = [{"word": "Hello", "start": 0.0, "end": 0.4}, {"word": "world", "start": 0.5, "end": 0.9}, {"word": "today", "start": 1.6, "end": 2.0}]
    out = ev.align("Hello, world! It's 41,000 today.", heard)
    assert [w["word"] for w in out] == ["Hello,", "world!", "It's", "41,000", "today."]
    assert out[0]["start"] == 0.0 and out[4]["start"] == 1.6
    assert 0.9 <= out[2]["start"] < out[3]["start"] < 1.6                    # the words the recogniser missed share the gap, in order
    assert ev.align("", heard) == [] and ev.align("Hi", []) == []


def test_moods_set_the_emotion_and_the_hook_is_never_flat():
    assert ev.mood_strength("excited") > ev.mood_strength("serious") > ev.mood_strength("calm")
    assert ev.mood_strength("calm", first=True) >= ev.MOODS["tense"] and ev.mood_strength("nonsense") == ev.MOODS[ev.DEFAULT_MOOD]


def test_speak_sends_the_text_mood_and_voice_sample_and_writes_timed_words(tmp_path):
    sample = tmp_path / "s.wav"
    _wav(sample)
    sent = {}

    def post(url, body):
        sent.update(body)
        return _wav(tmp_path / "server.wav")
    a, s = ev.speak("Hello world.", str(tmp_path / "v.mp3"), str(tmp_path / "v.json"), sample=str(sample), mood="excited", url="http://x",
                    post=post, listen=lambda audio, text: [{"word": "hello", "start": 0.1, "end": 0.4}, {"word": "world", "start": 0.5, "end": 0.9}])
    assert sent["input"] == "Hello world." and sent["exaggeration"] == ev.MOODS["excited"] and sent["sample_audio_b64"]
    assert os.path.isfile(a) and [w["word"] for w in json.load(open(s))] == ["Hello", "world."]
    import pytest
    with pytest.raises(RuntimeError, match="no audio"):
        ev.speak("x", str(tmp_path / "w.mp3"), str(tmp_path / "w.json"), post=lambda u, b: b"", listen=lambda a, t: [])
    assert ev.available("http://127.0.0.1:9") is False


def test_the_case_narration_uses_the_server_and_falls_back_for_the_rest(tmp_path):
    from engine import case_render
    script = {"sections": [{"title": "A", "narration": "One.", "mood": "tense"}, {"title": "B", "narration": "Two."}, {"title": "C", "narration": "Three."}]}
    spoken, edge = [], []

    def speak(text, audio, subs, sample=None, mood=None, first=False):
        spoken.append((text, mood, first))
        if text == "Two.":
            raise RuntimeError("out of memory")
        open(audio, "wb").write(b"x")
        json.dump([{"word": text, "start": 0, "end": 0.5}], open(subs, "w"))
        return audio, subs

    def gen(text, **kw):
        edge.append(text)
        open(kw["output_audio"], "wb").write(b"x")
        json.dump([{"word": text, "start": 0, "end": 0.5}], open(kw["output_subs"], "w"))
        return kw["output_audio"], kw["output_subs"]
    case_render.speak_sections(script, str(tmp_path), generate=gen, expressive={"speak": speak, "sample": None})
    assert spoken == [("One.", "tense", True), ("Two.", None, False)] and edge == ["Two.", "Three."]
    cache = json.load(open(tmp_path / "voice_cache.json"))
    assert cache["narrator"] == "standard"                                    # it fell back: a redo with the server speaks it again
    assert case_render.cached_voice(script, str(tmp_path), "voice_server") is None
    assert case_render.cached_voice(script, str(tmp_path), "standard") is not None


def test_the_narrator_choice_travels_from_the_app_to_the_pipeline():
    from engine import case_options
    from shortsflow import web_args
    assert case_options.parse(["narrator=voice_server"])["narrator"] == "voice_server" and case_options.parse([])["narrator"] == "standard"
    assert "narrator=voice_server" in web_args.case_args("T", narrator="voice_server")
    assert not any("narrator" in a for a in web_args.case_args("T"))


def test_your_own_recording_can_be_the_voice_and_a_new_one_respeaks(tmp_path):
    import pytest
    from engine import case_options
    from engine.modes import case
    from shortsflow import web_args
    rec = tmp_path / "me.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=12", str(rec)], check=True)
    short = tmp_path / "short.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=2", str(short)], check=True)
    assert case_options.parse([f"voice_sample={rec}"])["voice_sample"] == str(rec)
    with pytest.raises(Exception, match="not found"):
        case_options.parse([f"voice_sample={tmp_path / 'missing.wav'}"])
    wav = ev.own_sample(str(rec), str(tmp_path / "s"))
    assert wav.endswith(".wav") and os.path.isfile(wav)
    with pytest.raises(RuntimeError, match="10-30 seconds"):
        ev.own_sample(str(short), str(tmp_path / "s"))
    args = web_args.case_args("T", narrator="voice_server", voice_sample=str(rec))
    assert f"voice_sample={rec}" in args
    assert not any("voice_sample" in a for a in web_args.case_args("T", voice_sample=str(rec)))     # only with the expressive narrator
    own = case._narrator_tag("voice_server", str(rec), None)
    assert own.startswith("voice_server:own_") and own == case._narrator_tag("voice_server", str(rec), None)
    assert case._narrator_tag("voice_server", "", None) != own and case._narrator_tag("standard", str(rec), None) == "standard"
