import re
from pathlib import Path

import pytest

from engine import voiceover
from engine.mode_options import OptionError


def test_split_script_cuts_at_sentences_and_keeps_paragraphs_apart():
    text = "One. Two! Three?\n\nFour is a second paragraph."
    parts = voiceover.split_script(text, limit=30)
    assert parts == ["One. Two! Three?", "Four is a second paragraph."]
    long = "word " * 200
    assert all(len(p) <= 280 for p in voiceover.split_script(long))
    assert voiceover.split_script("  \n\n ") == []


def test_options_are_a_schema_with_a_help_text():
    values = voiceover.OPTIONS.parse(["sample=my.wav", "tone=warm"])
    assert values["sample"] == "my.wav" and values["tone"] == "warm" and values["format"] == "mp3"
    with pytest.raises(OptionError):
        voiceover.OPTIONS.parse(["tone=angry"])
    with pytest.raises(OptionError) as e:
        voiceover.OPTIONS.parse(["help"])
    assert "tone" in str(e.value) and "sample" in str(e.value)


def test_a_missing_sample_or_script_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="recording of your voice"):
        voiceover.make_voiceover("Hello there.", str(tmp_path), str(tmp_path / "nope.wav"))
    sample = tmp_path / "me.wav"
    sample.write_bytes(b"x" * 500)
    with pytest.raises(ValueError, match="script is empty"):
        voiceover.make_voiceover("   ", str(tmp_path), str(sample))
    with pytest.raises(ValueError, match="Unknown tone"):
        voiceover.make_voiceover("Hi.", str(tmp_path), str(sample), tone="angry")


def test_every_passage_is_voiced_with_the_sample_and_joined_at_the_tone_speed(tmp_path):
    sample = tmp_path / "me.wav"
    sample.write_bytes(b"x" * 500)
    spoken, joined = [], {}

    def synth(text, path):
        spoken.append(text)
        Path(path).write_bytes(b"a" * 500)

    res = voiceover.make_voiceover("First sentence. " * 30, str(tmp_path), str(sample), tone="calm", synth=synth,
                                   join=lambda parts, out, speed: joined.update(parts=parts, out=out, speed=speed))
    assert res["passages"] == len(spoken) >= 2 and res["tone"] == "calm"
    assert joined["speed"] == voiceover.TONES["calm"]["speed"] < 1.0 and joined["out"].endswith("voiceover.mp3")


def test_a_server_that_is_not_running_says_what_to_do(tmp_path):
    sample = tmp_path / "me.wav"
    sample.write_bytes(b"x" * 500)

    def down(text, path):
        raise ConnectionError("refused")

    with pytest.raises(RuntimeError, match="VOICE_STUDIO_URL"):
        voiceover.make_voiceover("Hello there.", str(tmp_path), str(sample), synth=down)


def test_the_server_gets_the_sample_and_the_tone_hints(tmp_path, monkeypatch):
    from engine import voice_gen
    sample = tmp_path / "me.wav"
    sample.write_bytes(b"RIFFdata")
    seen = {}

    class Resp:
        headers = {"content-type": "audio/mpeg"}
        content = b"a" * 500

        def raise_for_status(self):
            pass

    import requests
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: seen.update(url=url, body=json) or Resp())  # noqa: A006
    voiceover._synth_chunk("Hello there.", str(tmp_path / "p.mp3"), str(sample), "excited", "http://localhost:9999")
    body = seen["body"]
    assert seen["url"].startswith("http://localhost:9999") and body["sample_audio_b64"]
    assert body["speed"] == voiceover.TONES["excited"]["speed"] and body["emotion"] == "excited" and "excited" in body["instructions"]
    assert voice_gen.generate_voice_voicestudio  # the shared cloning call, not a second client


def test_script_can_be_text_or_a_file(tmp_path):
    from engine.modes.voiceover import read_script
    f = tmp_path / "s.txt"
    f.write_text("From a file.", encoding="utf-8")
    assert read_script(str(f)) == "From a file." and read_script("Plain text.") == "Plain text." and read_script(None) == ""


def test_the_command_line_has_two_voiceover_flags_and_the_mode_is_wired():
    main = (Path(__file__).resolve().parents[1] / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    assert sorted(re.findall(r'add_argument\("(--voiceover\w*)"', main)) == ["--voiceover", "--voiceover_file"]
    assert '"VOICEOVER"' in main and "engine.modes.voiceover" in main


def test_web_args_build_the_voiceover_command():
    from shortsflow import web_args
    args = web_args.voiceover_args("s.txt", "me.wav", "warm", "mp3", "sessions/x")
    assert args[:4] == ["--mode", "VOICEOVER", "--script", "s.txt"] and args[-2:] == ["--session_dir", "sessions/x"]
    pairs = [args[i + 1] for i, a in enumerate(args) if a == "--voiceover"]
    assert "sample=me.wav" in pairs and "tone=warm" in pairs and not any(p.startswith("format=") for p in pairs)
    parsed = voiceover.OPTIONS.parse(pairs)
    assert parsed["sample"] == "me.wav" and parsed["tone"] == "warm"
