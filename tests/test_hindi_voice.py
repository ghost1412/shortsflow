"""Hindi narration: a Hindi standard voice, and the voice server told the language, given a Hindi sample and matched word by word."""
from engine import expressive_voice as ev

HINDI = "अकबर ने इनाम रखा। बीरबल ने खिचड़ी लटकाई।"


def test_the_language_is_read_from_the_letters():
    assert [ev.language_of(t) for t in (HINDI, "Akbar offered a reward.", "雨が降った。川が増えた。", "Пошёл дождь.", "2026", "Akbar (अकबर) ruled for many years.")] == \
        ["hi", "en", "ja", "ru", "en", "en"]
    assert ev.standard_voice("hi") == "hi-IN-SwaraNeural" and ev.standard_voice("en") is None


def test_the_voice_server_is_told_the_language_only_when_it_is_not_english(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(ev.subprocess, "run", lambda cmd, **kw: open(cmd[-1], "wb").write(b"x") and None)
    for text in (HINDI, "A king offered a reward."):
        ev.speak(text, str(tmp_path / "a.mp3"), str(tmp_path / "a.json"), post=lambda url, body: sent.append(body) or b"0" * 2000,
                 listen=lambda audio, t: [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(t.split())])
    assert sent[0]["language"] == "hi" and "language" not in sent[1]


def test_heard_hindi_words_are_matched_to_the_scripts_words():
    heard = [{"word": w, "start": 1.0 + i, "end": 1.5 + i} for i, w in enumerate("अकबर ने इनाम रखा".split())]
    got = ev.align("अकबर ने इनाम रखा।", heard)
    assert [round(w["start"], 1) for w in got] == [1.0, 2.0, 3.0, 4.0]
    assert ev._norm("खिचड़ी!") == "खिचड़ी" and ev._norm("की") != ev._norm("का")


def test_the_sample_to_copy_is_spoken_in_the_storys_language(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(ev.subprocess, "run", lambda cmd, **kw: type("R", (), {"returncode": 0})())
    ev.language_sample("hi", str(tmp_path), make=lambda line, mp3, subs, voice: asked.append((voice, ev.language_of(line))))
    assert asked == [("hi-IN-SwaraNeural", "hi")]
    assert ev.language_sample("en", str(tmp_path)) is None
