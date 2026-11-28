"""The Gemini storyteller: what is asked, waiting out a short limit, giving up on a spent day, and one voice per video."""
import base64
import json

import pytest

from engine import case_options, gemini_voice as gv
from engine.modes import case as case_mode

SOUND = base64.b64encode(b"\x00\x01" * 4000).decode()
OK = (200, json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {"data": SOUND}}]}}]}))


def test_the_story_is_asked_for_acted_and_word_for_word():
    asked = []
    assert len(gv.audio_for("अकबर ने पूछा।", "tense", "Algieba", post=lambda m, p: asked.append((m, p)) or OK)) == 8000
    model, payload = asked[0]
    text = payload["contents"][0]["parts"][0]["text"]
    assert model == gv.MODELS[0] and text.endswith("अकबर ने पूछा।") and "tense and suspenseful" in text and "exactly as written" in text
    assert payload["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Algieba"


def test_a_short_limit_is_waited_out_and_a_spent_day_is_not():
    replies, waited = [(429, '{"error": {"details": [{"retryDelay": "20s"}]}}'), OK], []
    assert gv.audio_for("a b", None, None, post=lambda m, p: replies.pop(0), sleep=waited.append) and waited == [21.0]
    spent, waited = [], []
    with pytest.raises(RuntimeError, match="429"):
        gv.audio_for("a b", None, None, post=lambda m, p: spent.append(m) or (429, '{"quotaId": "GenerateRequestsPerDayPerProject", "retryDelay": "30s"}'),
                     sleep=waited.append)
    assert spent == list(gv.MODELS) and waited == []                      # one try per model, no waiting


def test_it_is_a_narrator_of_the_case_options_with_its_own_cache_tag():
    option = next(o for o in case_options.CASE.options if o.key == "narrator")
    assert "gemini" in option.choices
    assert case_mode._narrator_tag("gemini", "", None, "Sulafat") == "gemini:Sulafat" and case_mode._narrator_tag("standard", "", None) == "standard"


def test_the_browser_app_offers_both_storytellers():
    from shortsflow import web_args
    grandfather = web_args.case_args("A story", "https://example.org", "story", "dark", "9:16", narrator="gemini")
    grandmother = web_args.case_args("A story", "https://example.org", "story", "dark", "9:16", narrator="gemini:Sulafat")
    assert "narrator=gemini" in grandfather and not any(a.startswith("gemini_voice=") for a in grandfather)
    assert "narrator=gemini" in grandmother and "gemini_voice=Sulafat" in grandmother


def test_a_rerendered_storyteller_run_times_its_saved_audio_again_without_a_new_voice(tmp_path, monkeypatch):
    from engine import case_render, expressive_voice
    script = {"sections": [{"title": "A", "narration": "one two"}]}
    (tmp_path / "voice_01.mp3").write_bytes(b"x")
    (tmp_path / "subs_01.json").write_text(json.dumps([{"word": "one", "start": 9.0, "end": 9.4}]), encoding="utf-8")
    (tmp_path / "voice_cache.json").write_text(json.dumps({"narration": case_render._narration_hashes(script), "narrator": "gemini:Algieba"}), encoding="utf-8")
    monkeypatch.setattr(expressive_voice, "timed", lambda text, audio, hear: [{"word": "one", "start": 0.1, "end": 0.5}, {"word": "two", "start": 0.6, "end": 1.0}])
    monkeypatch.setattr(gv, "speak", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no new voice")))
    args = type("A", (), {"gemini_voice": "Algieba", "voice": None})()
    audios, words = case_mode._narration(args, script, str(tmp_path), True, None, "gemini", "")
    assert [w["start"] for w in words[0]] == [0.1, 0.6] and audios[0].endswith("voice_01.mp3")
