import json

from engine import case_render as cr

SCRIPT = {"title": "T", "verified": True, "sources": [{"id": "S1", "ref": "https://example.com/a"}],
          "sections": [{"id": "a", "title": "A", "scene": "timeline", "narration": "x", "on_screen": ["one", "two"]},
                       {"id": "b", "title": "B", "scene": "counters", "narration": "y", "on_screen": ["5 things"]}]}


def test_plan_timing_starts_after_the_intro_and_chains():
    assert cr.plan_timing([10, 5], intro=2, pad=1) == [(2.0, 13.0), (13.0, 19.0)]


def test_read_words_both_shapes(tmp_path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps([{"word": " Hi ", "start": 0, "end": 0.4}, {"word": "", "start": 1, "end": 2}, {"bad": 1}]), encoding="utf-8")
    assert cr.read_words(str(a)) == [{"word": "Hi", "start": 0.0, "end": 0.4}]
    a.write_text(json.dumps({"segments": [{"words": [{"word": "yo", "start": 1, "duration": 0.5}]}]}), encoding="utf-8")
    assert cr.read_words(str(a)) == [{"word": "yo", "start": 1.0, "end": 1.5}]
    assert cr.read_words(str(tmp_path / "missing.json")) == []


def test_build_props_shifts_words_to_their_section():
    words = [[{"word": "a", "start": 0.0, "end": 0.5}], [{"word": "b", "start": 0.1, "end": 0.6}]]
    props = cr.build_props(SCRIPT, [(2.0, 8.0), (8.0, 12.0)], words, theme="warm")
    assert props["theme"] == "warm" and props["verified"] is True and props["sources"] == ["https://example.com/a"]
    assert [s["start"] for s in props["sections"]] == [2.0, 8.0]
    assert props["words"][1] == {"word": "b", "start": 8.1, "end": 8.6}
    assert "audioUrl" not in props and "accent" not in props


def test_speak_sections_uses_the_given_generator(tmp_path):
    calls = []

    def fake(text, **kw):
        calls.append((text, kw))
        open(kw["output_audio"], "wb").write(b"x")
        json.dump([{"word": text, "start": 0, "end": 1}], open(kw["output_subs"], "w"))
        return kw["output_audio"], kw["output_subs"]
    audios, words = cr.speak_sections(SCRIPT, str(tmp_path), provider="edgetts", generate=fake)
    assert len(audios) == 2 and words[0][0]["word"] == "x"
    assert calls[0][1]["provider"] == "edgetts" and calls[0][1]["add_cta"] is False


def test_label_cues_follow_the_spoken_words():
    words = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(
        "On July 19 CrowdStrike pushed a faulty update and roughly 8.5 million systems crashed".split())]
    cues = cr.label_cues(["July 19, 2024", "Faulty update", "8.5 million systems"], words, duration=10)
    assert cues == sorted(cues)
    assert cues[0] < cues[1] < cues[2]
    assert abs(cues[1] - (words[6]["start"] - 0.15)) < 0.01      # "faulty" is word 6


def test_label_cues_unmatched_labels_still_move_forward_and_stay_inside_the_section():
    cues = cr.label_cues(["zzz one", "zzz two", "zzz three"], [{"word": "hello", "start": 0.0, "end": 0.3}], duration=3)
    assert cues == sorted(cues) and len(set(cues)) == 3 and max(cues) <= 2.5


def test_attach_clips_only_for_the_asked_scenes_and_sets_the_rate(tmp_path):
    made = []

    def make(sec, seconds, folder, ask, render, topic="", portrait=False, accent=""):
        made.append((sec["id"], round(seconds, 1)))
        return str(tmp_path / (sec["id"] + ".mp4")) if sec["id"] == "a" else None
    script = dict(SCRIPT, sections=[dict(SCRIPT["sections"][0], scene="flow"), dict(SCRIPT["sections"][1], scene="flow"),
                                    dict(SCRIPT["sections"][1], id="c", scene="counters")])
    clips = cr.attach_clips(script, [(2.0, 12.0), (12.0, 20.0), (20.0, 25.0)], str(tmp_path), None, make=make, probe=lambda p: 15.0)
    assert clips[0] == {"path": str(tmp_path / "a.mp4"), "rate": 1.5} and clips[1] is None and clips[2] is None
    assert made == [("a", 10.0), ("b", 8.0)]
    props = cr.build_props(script, [(2.0, 12.0), (12.0, 20.0), (20.0, 25.0)], [[], [], []], clips=clips)
    assert props["sections"][0]["clip"].endswith("a.mp4") and props["sections"][0]["clipRate"] == 1.5
    assert "clip" not in props["sections"][1]


def test_spoken_order_sorts_labels_by_when_they_are_said_and_starts_early():
    words = [{"word": w, "start": 6 + i * 0.5, "end": 6.4 + i * 0.5} for i, w in enumerate("Oil prices rose then flights were cancelled worldwide".split())]
    labels, cues = cr.spoken_order(["Flights cancelled", "Oil prices", "Never said here"], words, duration=20)
    assert labels == ["Oil prices", "Flights cancelled", "Never said here"]
    assert cues[0] == 1.5                         # the first label does not wait for the narrator to reach it
    assert cues == sorted(cues) and all(b - a >= 0.8 for a, b in zip(cues, cues[1:]))
