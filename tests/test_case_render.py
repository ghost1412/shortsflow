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
    assert props["theme"] == "warm" and props["verified"] is True and props["sources"] == ["example.com"]
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
    assert clips[0]["path"] == str(tmp_path / "a.mp4") and clips[0]["rate"] == 1.5 and clips[0]["aspect"] == round(16 / 9, 3)      # a clip that cannot be read counts as 16:9
    assert clips[1] is None and clips[2] is None
    assert made == [("a", 10.0), ("b", 8.0)]
    props = cr.build_props(script, [(2.0, 12.0), (12.0, 20.0), (20.0, 25.0)], [[], [], []], clips=clips)
    assert props["sections"][0]["clip"].endswith("a.mp4") and props["sections"][0]["clipRate"] == 1.5
    assert "clip" not in props["sections"][1]


def test_a_word_shared_with_a_later_step_does_not_move_that_step_ahead():
    text = "Liquid refrigerant flows through coils outside. The compressor squeezes this gas. That warmed gas then flows indoors and cools."
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(text.split())]
    labels, cues = cr.spoken_order(["Refrigerant", "Compressor", "Indoor coil"], words, duration=12)
    assert labels == ["Refrigerant", "Compressor", "Indoor coil"] and cues == sorted(cues)
    assert cr.spoken_order(["Compressor", "Indoor coil"], words[:6] + words[6:9], duration=8)[0] == ["Indoor coil", "Compressor"]   # said nowhere later: the only match counts
    said_whole = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate("the indoor coil warms before the compressor".split())]
    assert cr.spoken_order(["Compressor", "Indoor coil"], said_whole, duration=6)[0] == ["Indoor coil", "Compressor"]       # the narrator's order still wins


def test_a_label_belongs_where_most_of_its_words_are_said():
    text = "Ground source heat pumps use steady temperatures. More data sharing from heat meters could help."
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(text.split())]
    assert words[cr._first_spoken("Share heat meter data", words)]["word"] == "data"


def test_spoken_order_sorts_labels_by_when_they_are_said_and_starts_early():
    words = [{"word": w, "start": 6 + i * 0.5, "end": 6.4 + i * 0.5} for i, w in enumerate("Oil prices rose then flights were cancelled worldwide".split())]
    labels, cues = cr.spoken_order(["Flights cancelled", "Oil prices", "Never said here"], words, duration=20)
    assert labels == ["Oil prices", "Flights cancelled", "Never said here"]
    assert cues[0] == 1.5                         # the first label does not wait for the narrator to reach it
    assert cues == sorted(cues) and all(b - a >= 0.8 for a, b in zip(cues, cues[1:]))


def _spoken(text, step=0.4, start=0.0):
    out, t = [], start
    for w in text.split():
        out.append({"word": w, "start": round(t, 2), "end": round(t + step * 0.9, 2)})
        t += step
    return out


def test_beats_split_at_sentence_ends_and_cover_the_whole_section():
    words = _spoken("The first sentence is a fairly long one that goes on for a while. Second sentence follows right after it and keeps going too. "
                    "A third one closes the section with some words here.")
    duration = words[-1]["end"] + 0.5
    beats = cr.beats_for(words, duration)
    assert beats[0][0] == 0.0 and beats[-1][1] == round(duration, 2)
    assert all(a[1] == b[0] for a, b in zip(beats, beats[1:]))                    # no gaps
    assert all(b - a <= 9.5 for a, b in beats) and len(beats) >= 2           # nothing stays on screen for a whole section
    assert all(b - a >= 2.0 for a, b in beats)


def test_beats_without_words_are_even():
    beats = cr.beats_for([], 26.0)
    assert len(beats) == 4 and beats[-1][1] == 26.0


def test_attach_footage_one_clip_per_phrase_and_skips_misses(tmp_path):
    script = {"sections": [{"footage": ["ships at sea", "none", "ships at sea", "harbour cranes"]}, {"footage": "single phrase"}, {"footage": []}]}

    def fetch(phrase, cache, orientation):
        return None if phrase == "none" else (str(tmp_path / (phrase.replace(" ", "_") + ".mp4")), 10.0)
    got = cr.attach_footage(script, str(tmp_path), "16:9", fetch=fetch, cache_dir=str(tmp_path))
    assert [f["seconds"] for f in got[0]] == [10.0, 10.0] and len(got[0]) == 2     # the miss and the repeat are dropped
    assert len(got[1]) == 1 and got[2] is None
    props = cr.build_props(dict(SCRIPT, sections=SCRIPT["sections"][:1] * 1), [(2.0, 12.0)], [[]], footage=[got[0]])
    assert props["sections"][0]["footage"][0]["src"].endswith("ships_at_sea.mp4") and props["sections"][0]["beats"]


def test_source_chips_and_the_removed_claims_reach_the_props():
    script = dict(SCRIPT, dropped=[{"sentence": "x", "unsupported": ["9"]}, {"sentence": "y", "unsupported": ["Zed"]}],
                  sources=[{"id": "S1", "ref": "https://www.example.com/a/b"}, {"id": "S2", "ref": "C:/docs/notes.txt"}])
    script["sections"] = [dict(SCRIPT["sections"][0], cites=["S2"]), dict(SCRIPT["sections"][1], cites=[])]
    props = cr.build_props(script, [(2.0, 8.0), (8.0, 12.0)], [[], []])
    assert props["sections"][0]["sourceLabels"] == ["notes.txt"]
    assert props["sections"][1]["sourceLabels"] == ["example.com", "notes.txt"]       # no citation given: every source
    assert props["sources"] == ["example.com", "notes.txt"] and props["removedClaims"] == 2
    assert cr.source_label("pasted notes") == "pasted notes" and cr.source_label("https://a.b/c") == "a.b"
    unverified = cr.build_props(dict(script, verified=False, sources=[]), [(2.0, 8.0), (8.0, 12.0)], [[], []])
    assert unverified["sections"][0]["sourceLabels"] == []


def test_compare_chart_and_quote_keep_the_authored_label_order_and_start_early():
    words = [{"word": w, "start": 6 + i * 0.5, "end": 6.4 + i * 0.5} for i, w in enumerate("After the patch ports were blocked and before it they were open".split())]
    script = dict(SCRIPT, sections=[dict(SCRIPT["sections"][0], scene="compare", on_screen=["Before | After", "Open | Blocked"]),
                                    dict(SCRIPT["sections"][0], scene="flow", on_screen=["Blocked ports", "After the patch"])])
    props = cr.build_props(script, [(2.0, 20.0), (20.0, 40.0)], [words, words])
    assert props["sections"][0]["labels"] == ["Before | After", "Open | Blocked"] and props["sections"][0]["cues"][0] <= 1.5
    assert props["sections"][1]["labels"] == ["After the patch", "Blocked ports"]                  # a flow follows the narration (a timeline keeps its order of time: see below)


def test_build_props_hands_the_clip_aspect_to_the_renderer_and_defaults_to_16x9():
    script = dict(SCRIPT, sections=[dict(SCRIPT["sections"][0], scene="flow"), dict(SCRIPT["sections"][1], scene="flow")])
    timing = [(2.0, 12.0), (12.0, 20.0)]
    clips = [{"path": "a.webm", "rate": 1.0, "aspect": 2.2}, {"path": "b.webm", "rate": 1.0}]       # the second one is an old clip without an aspect
    props = cr.build_props(script, timing, [[], []], clips=clips)
    assert props["sections"][0]["clipAspect"] == 2.2 and props["sections"][1]["clipAspect"] == round(16 / 9, 3)


def test_build_props_carries_the_hook_to_the_cover():
    script = dict(SCRIPT, hook="One bug, millions of servers")
    props = cr.build_props(script, [(2.0, 12.0), (12.0, 20.0)], [[], []])
    assert props["hook"] == "One bug, millions of servers"
    assert cr.build_props(dict(SCRIPT), [(2.0, 12.0), (12.0, 20.0)], [[], []])["hook"] == ""


def test_a_timeline_keeps_the_order_of_time_and_spreads_its_events():
    cues = cr.even_cues(4, 30.0)
    assert cues[0] == 0.8 and cues == sorted(cues) and cues[-1] <= 27.5 and len(set(cues)) == 4
    assert cr.even_cues(1, 30.0) == [0.8] and cr.even_cues(0, 30.0) == [] and cr.even_cues(3, 2.0)[-1] >= 0.8
    script = dict(SCRIPT, sections=[dict(SCRIPT["sections"][0], scene="timeline", on_screen=["2013: bug", "2021: found", "2022: fixed"],
                                         narration="Fixed in 2022. Found in 2021. The bug dates from 2013.")] + SCRIPT["sections"][1:])
    props = cr.build_props(script, [(2.0, 32.0), (32.0, 40.0)], [[{"word": "Fixed", "start": 0.0, "end": 0.4}], []])
    assert props["sections"][0]["labels"] == ["2013: bug", "2021: found", "2022: fixed"]          # not re-ordered by the narration
    assert props["sections"][0]["cues"] == cr.even_cues(3, 30.0)


def test_transitions_travel_to_the_props_and_the_narration_is_told_naturally(tmp_path):
    from engine import case_options, case_render
    from shortsflow import web_args
    assert case_options.parse(["transition=slide"])["transition"] == "slide" and case_options.parse([])["transition"] == "number"
    assert "transition=zoom" in web_args.case_args("Topic", transition="zoom") and not any("transition" in a for a in web_args.case_args("Topic"))
    script = {"title": "T", "sections": [{"title": "A", "scene": "quote", "on_screen": ["x"], "narration": "x"}], "sources": []}
    assert case_render.build_props(script, [(1.8, 5.0)], [[]], transition="wipe")["transition"] == "wipe"
    import os
    tsx = open(os.path.join(os.path.dirname(__file__), "..", "remotion-video", "src", "CaseVideo.tsx"), encoding="utf-8").read()
    assert all(f'"{t}"' in tsx.split("CASE_TRANSITIONS = [")[1].split("]")[0] for t in case_options.TRANSITIONS)
    import engine.voice_gen as vg
    seen = {}

    class Com:
        def __init__(self, text, voice, rate=None, pitch=None):
            seen.update(text=text, voice=voice, rate=rate)

        async def stream(self):
            yield {"type": "audio", "data": b"x"}
            yield {"type": "WordBoundary", "offset": 0, "duration": 1000000, "text": "Hi"}
    old = vg.edge_tts.Communicate
    vg.edge_tts.Communicate = Com
    try:
        vg.generate_voice("First point. Second point.", str(tmp_path / "a.mp3"), str(tmp_path / "a.json"), voice_name="en-US-AvaMultilingualNeural",
                          rate="+0%", add_cta=False, provider="edgetts", style="narration")
    finally:
        vg.edge_tts.Communicate = old
    assert seen["text"] == "First point. Second point." and seen["rate"] == "+0%"          # no "..." pauses, no hook split, normal pace


def test_labels_the_narrator_never_says_share_the_time_left_instead_of_bunching_up():
    words = [{"word": w, "start": 1 + i * 0.5, "end": 1.4 + i * 0.5} for i, w in enumerate("Sunlight enters the air".split())]
    labels, cues = cr.spoken_order(["Sunlight", "Dragon", "Castle", "Wizard"], words, duration=30)
    assert labels[0] == "Sunlight" and cues == sorted(cues)
    assert cues[-1] - cues[1] >= 6 and cues[-1] <= 30 - 0.5                  # spread over the section, not 1.2 s apart
    assert cr.spoken_order(["Dragon", "Castle"], words, duration=None)[1][1] - cr.spoken_order(["Dragon", "Castle"], words, duration=None)[1][0] >= 1.2
