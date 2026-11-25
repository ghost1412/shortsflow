"""Idea-to-video audit: script validators, JSON repair, narration, TTS text, backgrounds and the run itself (all offline)."""
import json
import os
import subprocess
import types

import pytest

import engine.media_gen as mg
import engine.modes.generate as gen
import engine.script_gen as sg
import engine.voice_gen as vg
from engine.voice_gen import clean_for_tts, split_hook

REFUSAL = ("I'm sorry, but I cannot help with writing that particular story because it would go against my content guidelines. "
           "Please try some other topic instead.")


# --- scripts ---------------------------------------------------------------------------------
@pytest.mark.parametrize("d", [
    {"option_a": "", "option_b": "x"}, {"option_a": "x", "option_b": None}, {"option_a": ["a"], "option_b": "b"},
    {"option_a": "Same", "option_b": " same "}, [], None,
])
def test_wyr_rejects_empty_null_list_or_repeated_options(d):
    assert sg.validate_wyr(d) is False
    assert sg.validate_wyr({"option_a": "Fly", "option_b": "Swim"}) is True


def trivia(**kw):
    return {"question": "q?", "opt_a": "Saturn", "opt_b": "Mars", "opt_c": "Venus", "answer": "Mars", **kw}


def test_trivia_answer_must_be_one_of_three_different_options():
    assert sg.validate_trivia(trivia()) is True
    assert sg.validate_trivia(trivia(answer="Jupiter")) is False
    assert sg.validate_trivia(trivia(opt_c="mars")) is False
    assert sg.validate_trivia({"question": "q?", "answer": "x"}) is False        # no options: the video script would KeyError


@pytest.mark.parametrize("kw", [
    {"answer": "B"}, {"answer": "b)"}, {"answer": "Option B"}, {"answer": "B) Mars"}, {"answer": "mars"},
    {"opt_a": "A) Saturn", "opt_b": "B) Mars", "opt_c": "C) Venus", "answer": "B) Mars"},
    {"opt_a": None, "opt_b": None, "opt_c": None, "options": ["Saturn", "Mars", "Venus"], "answer": "B"},
])
def test_trivia_reply_shapes_become_the_option_text(kw):
    t = sg.normalize_trivia(trivia(**kw))
    assert (t["opt_a"], t["opt_b"], t["opt_c"], t["answer"]) == ("Saturn", "Mars", "Venus", "Mars") and sg.validate_trivia(t)


def test_trivia_numbers_are_text_and_a_contradicting_letter_is_rejected():
    t = sg.normalize_trivia(trivia(opt_a=1969, opt_b=1971, opt_c=1972, answer=1969))
    assert t["answer"] == "1969" and sg.validate_trivia(t)             # the renderer calls .upper() on them
    assert sg.validate_trivia(sg.normalize_trivia(trivia(answer="B) Saturn"))) is False


def test_riddle_needs_a_real_question_and_gets_a_hook(monkeypatch):
    assert sg.validate_riddle({"question": "", "hint": "x"}) is False
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: json.dumps({"question": "What has keys but no locks?", "answer": "A piano"}))
    r = sg.generate_riddle("music")
    assert r["answer"] == "A piano" and r["hook"]


def test_a_refusal_is_never_a_story(monkeypatch):
    d = sg.robust_json_parse(REFUSAL)
    assert not sg.validate_story(d) and not sg.validate_news(d) and not sg.validate_jwst_script(d)
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: REFUSAL)
    with pytest.raises(RuntimeError):
        sg.generate_story("space")


def test_news_needs_its_hook():
    d = {"title": "T", "hook": "Big", "story": " ".join(["word"] * 12)}
    assert sg.validate_news(d) and not sg.validate_news({k: v for k, v in d.items() if k != "hook"})


def test_story_as_a_list_of_paragraphs_is_joined(monkeypatch):
    monkeypatch.setattr(sg, "get_llm_response", lambda *a, **k: json.dumps({"title": "T", "story": ["one two three"] * 10}))
    assert sg.generate_story("space")["story"].startswith("one two three one")


def test_emojis_as_a_list():
    assert sg.normalize_emoji_guess({"emojis": ["🦁", "👑"], "answer": "X", "script": "s"})["emojis"] == "🦁 👑"


def test_json_repair_keeps_urls():
    assert sg.robust_json_parse('{\n"title":"T",\n"source":"https://x.com/a",\n"ok":true,\n}') == \
        {"title": "T", "source": "https://x.com/a", "ok": True}


def test_json_repair_skips_an_unopened_think_block():
    assert sg.robust_json_parse('maybe {"title":"draft"}</think>{"title":"real"}') == {"title": "real"}
    assert sg.robust_json_parse('{"title":"the </think> tag"}') == {"title": "the </think> tag"}


# --- narration -------------------------------------------------------------------------------
@pytest.mark.parametrize("out,want", [("N/A\n", None), ("", None), ("0.0\n", None), ("nan", None), ("23.5\n", 23.5)])
def test_probe_duration(monkeypatch, out, want):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=out, stderr="", returncode=0))
    assert gen.probe_duration("x.mp3") == want


def test_narration_duration_falls_back_to_last_word_then_stops(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise FileNotFoundError("ffprobe")
    monkeypatch.setattr(subprocess, "run", boom)
    subs = tmp_path / "subs.json"
    subs.write_text(json.dumps([{"word": "a", "start": 0, "end": 1}, {"word": "b", "start": 1, "end": 42.5}]))
    assert gen.narration_duration("v.mp3", str(subs)) == 42.5
    subs.write_text("[]")
    with pytest.raises(SystemExit) as e:
        gen.narration_duration("v.mp3", str(subs))
    assert e.value.code == 1


@pytest.mark.parametrize("raw,want", [
    ("slow—and steady", "slow, and steady"), ("open 24/7", "open 24 7"), ("Q&A and 5+3", "Q and A and 5 plus 3"),
    ("don’t stop…", "don't stop..."), ("costs £500", "costs £500"), ("1990–1995", "1990-1995"), ("3×4", "3 4"),
    ("100°C or 90° now", "100 degrees Celsius or 90 degrees now"), ("I ❤️ it", "I it"), ("hi \U0001F600 there", "hi there"),
])
def test_clean_for_tts_glues_and_loses_nothing(raw, want):
    assert clean_for_tts(raw) == want


def test_split_hook_keeps_a_decimal_whole():
    assert split_hook("Pi is 3.14 exactly. Yes.") == ("Pi is 3.14 exactly", "Yes.")


def _edge_down(monkeypatch):
    class Down:
        def __init__(self, *a, **k):
            raise OSError("offline")
    monkeypatch.setattr(vg.edge_tts, "Communicate", Down)
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setenv("VOICE_PROVIDER", "edgetts")
    from engine import kokoro_tts
    monkeypatch.setattr(kokoro_tts, "is_available", lambda download=False: False)


def _gtts(monkeypatch, save):
    import sys
    mod = types.ModuleType("gtts")
    mod.gTTS = lambda **k: types.SimpleNamespace(save=save)
    monkeypatch.setitem(sys.modules, "gtts", mod)


def test_no_voice_means_no_audio_not_a_silent_video(monkeypatch, tmp_path):
    _edge_down(monkeypatch)

    def fail(path):
        raise OSError("offline")
    _gtts(monkeypatch, fail)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0))
    audio = tmp_path / "v.mp3"
    assert vg.generate_voice("Hello there.", str(audio), str(tmp_path / "s.json")) == (None, None)
    assert not audio.exists()                       # some callers only look whether the file is there


def test_gtts_captions_follow_the_real_audio(monkeypatch, tmp_path):
    import wave
    _edge_down(monkeypatch)

    def save(path):
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"\0\0" * 8000 * 6)
    _gtts(monkeypatch, save)
    subs = tmp_path / "s.json"
    vg.generate_voice("only four words here", str(tmp_path / "v.wav"), str(subs))
    assert json.loads(subs.read_text())[-1]["end"] == pytest.approx(6.0, abs=0.2)


def test_voice_server_without_audio_is_a_failure(monkeypatch, tmp_path):
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: types.SimpleNamespace(
        raise_for_status=lambda: None, headers={"content-type": "application/json"}, json=lambda: {"error": "busy"}))
    with pytest.raises(RuntimeError):
        vg.generate_voice_voicestudio("hi", str(tmp_path / "v.mp3"), str(tmp_path / "s.json"))


# --- backgrounds -----------------------------------------------------------------------------
class Resp:
    def __init__(self, data=None, content=b"", status=200):
        self.data, self.content, self.status_code = data, content, status

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise mg.requests.HTTPError(str(self.status_code))


def test_empty_stock_search_stops_after_a_few_tries(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    urls = []
    monkeypatch.setattr(mg.requests, "get", lambda url, **k: urls.append(url) or Resp({"videos": []}))
    assert mg.download_background_video("", "R&B music", "assets/x.mp4", orientation="landscape", force_literal=True) is None
    assert len(urls) == 4 and "query=R%26B%20music&" in urls[0] and all("orientation=landscape" in u for u in urls)


@pytest.mark.parametrize("kind", ["video", "image"])
def test_an_error_page_is_not_saved_or_cached(monkeypatch, tmp_path, kind):
    monkeypatch.chdir(tmp_path)
    os.makedirs("assets")
    found = {"videos": [{"video_files": [{"width": 1080, "link": "L"}]}], "photos": [{"src": {"large": "L"}}]}
    monkeypatch.setattr(mg.requests, "get", lambda url, **k: Resp(found) if url != "L" else Resp(content=b"<html>", status=403))
    if kind == "video":
        assert mg.download_background_video("", "sea", "assets/x.mp4", force_literal=True) is None
    else:
        assert mg.download_image("sea", "assets/x.png") is None
    assert os.listdir("assets") == []


def test_queries_in_other_scripts_do_not_share_a_cache_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    os.makedirs("assets")
    monkeypatch.setattr(mg.requests, "get", lambda url, **k: Resp(content=url.encode()) if url.startswith("L")
                        else Resp({"photos": [{"src": {"large": "L" + url}}]}))
    mg.download_image("東京", "assets/1.png")
    mg.download_image("大阪", "assets/2.png")
    assert (tmp_path / "assets/1.png").read_bytes() != (tmp_path / "assets/2.png").read_bytes()


# --- the run itself, with every outside piece replaced -------------------------------------------
class Args(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


def run_mode(monkeypatch, tmp_path, mode, bg=lambda *a, **k: "bg.mp4"):
    import engine.social_gen as social
    import engine.video_gen as video
    monkeypatch.chdir(tmp_path)
    seen = {}
    monkeypatch.setattr(gen, "generate_voice", lambda *a, **k: ("v.mp3", "s.json"))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout="20.0", stderr="", returncode=0))
    monkeypatch.setattr(mg, "download_background_video", bg)
    for name in ("download_image", "download_sfx"):
        monkeypatch.setattr(gen, name, lambda *a, **k: None)
    for name in ("create_trivia_video", "create_riddle_video", "create_sound_challenge_video"):
        monkeypatch.setattr(video, name, lambda *a, **k: seen.update(video=a) or "out.mp4")
    monkeypatch.setattr(social, "generate_viral_metadata", lambda info, **k: seen.update(meta=info) or {"title": "T", "description": "d", "tags": ["x"]})
    gen.run(Args(mode=mode, category="space", prompt="a topic", vibe="suspense", skip_upload=True), "8000k", "medium")
    return seen


@pytest.mark.parametrize("answer,letter", [("Saturn", "A"), ("Mars", "B"), ("Venus", "C")])
def test_trivia_video_is_given_the_letter_of_the_right_option(monkeypatch, tmp_path, answer, letter):
    monkeypatch.setattr(gen, "generate_trivia", lambda c: trivia(answer=answer))
    assert run_mode(monkeypatch, tmp_path, "TRIVIA")["video"][1]["answer"] == letter      # the renderer takes anything else as C


def test_metadata_is_written_from_the_script(monkeypatch, tmp_path):
    monkeypatch.setattr(gen, "generate_riddle", lambda c: {"hook": "Test!", "question": "What has keys but no locks?", "answer": "A piano"})
    meta = run_mode(monkeypatch, tmp_path, "RIDDLE")["meta"]
    assert "What has keys" in meta and "piano" not in meta


def test_sound_challenge_backgrounds_are_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(gen, "generate_sound_challenge", lambda c: {"hook": "Guess!", "object": "owl", "sound_query": "owl", "reveal_text": "Owl."})
    seen = run_mode(monkeypatch, tmp_path, "GUESS_SOUND", bg=lambda *a, output_path="", **k: output_path if "bg_gen" in output_path else None)
    assert seen["video"][4] and all(isinstance(p, str) for p in seen["video"][4])      # was [["..."]], unreadable for the renderer


@pytest.mark.parametrize("script", ["", "  ", None, ["a", "b"]])
def test_an_empty_narration_stops_the_run(monkeypatch, tmp_path, script):
    monkeypatch.setattr(sg, "generate_true_crime_script", lambda t: {"title": "T", "narrator_script": script})
    monkeypatch.setattr(gen, "create_shorts_video", lambda *a, **k: "out.mp4")
    with pytest.raises(SystemExit) as e:
        run_mode(monkeypatch, tmp_path, "TRUE_CRIME")
    assert e.value.code == 1
