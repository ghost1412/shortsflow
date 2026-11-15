import argparse
import json
import subprocess

import pytest

from engine import auto_edit, style_clone as sc


def _colour(**kw):
    base = {"p1": 0.05, "p50": 0.45, "p99": 0.85, "r": 0.4, "g": 0.4, "b": 0.4, "sat": 0.25, "noise": 0.0}
    base.update(kw)
    return base


def _m(shot=2.0, colour=None, **kw):
    base = {"duration": 30.0, "width": 1080, "height": 1920, "analysed_seconds": 30.0, "cuts": int(30 / shot) - 1, "shot_seconds": shot,
            "first_shot_seconds": shot, "colour": colour or _colour(), "mean_db": -20.0, "peak_db": -3.0}
    base.update(kw)
    return base


def test_pace_decides_the_inferred_settings():
    fast, lines = sc.to_template(_m(shot=1.5))
    assert fast["remove_fillers"] and fast["broll"] and not fast["auto_zoom"] and fast["sfx"]["cut"] == "whoosh"
    slow, _ = sc.to_template(_m(shot=7.0))
    assert not slow["tighten"] and slow["auto_zoom"] and not slow["broll"]
    assert "inferred" in " ".join(lines).lower() or "guess" in " ".join(lines).lower()
    assert any("not detected" in line for line in lines)


def test_colour_look_only_when_clear():
    assert sc.grade_for(_colour())[0] is None
    assert sc.grade_for(_colour(p50=0.2))[0] == "moody_dark"
    assert sc.grade_for(_colour(sat=0.5))[0] == "vibrant_action"
    assert sc.grade_for(_colour(r=0.5, g=0.4, b=0.3))[0] == "cinematic_warm"
    assert sc.grade_for(_colour(r=0.3, g=0.4, b=0.5))[0] == "cold_thriller"
    assert sc.grade_for(None)[0] is None


def test_template_is_valid_and_usable(tmp_path):
    tpl, _ = sc.to_template(_m(shot=2.0, colour=_colour(r=0.5, g=0.4, b=0.3)), caption_style="BOUNCE")
    path = auto_edit.save_user_template("clone-test", tpl, str(tmp_path))
    saved = json.loads(open(path, encoding="utf-8").read())
    assert saved["caption_style"] == "BOUNCE" and saved["video_filter"] == "cinematic_warm"
    args = argparse.Namespace(caption_style="HORMOZI", use_remotion=False, tighten_mode="cut", layout="single", video_filter="none",
                              tighten=False, remove_fillers=False, clean_audio=False, hook_overlay=False, auto_zoom=False, stat_pops=False,
                              cold_open=False, broll=False, caption_emoji=False, visual_template=None, template_text=None)
    auto_edit.apply_preset(args, "clone-test", argv=[])
    assert args.broll and args.video_filter == "cinematic_warm" and args.caption_style == "BOUNCE"


def test_clone_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValueError):
        sc.clone(str(tmp_path / "nope.mp4"), "x", folder=str(tmp_path))


def test_real_reference_with_cuts(tmp_path):
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pytest.skip("no ffmpeg")
    out = tmp_path / "ref.mp4"
    cols = ["red", "blue", "green", "black", "white", "blue"]
    cmd = [ff, "-y"]
    for c in cols:
        cmd += ["-f", "lavfi", "-t", "2", "-i", f"color=c={c}:s=180x320:r=25"]
    cmd += ["-filter_complex", "".join(f"[{i}:v]" for i in range(6)) + "concat=n=6:v=1:a=0[v]", "-map", "[v]", "-pix_fmt", "yuv420p", str(out)]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        pytest.skip("ffmpeg cannot build the sample")
    path, lines = sc.clone(str(out), "real-ref", folder=str(tmp_path / "templates"), frames=[])
    assert path.endswith("real-ref.json") and lines[0].startswith("Pace: fast")


def test_web_box_saves_a_template_and_explains(tmp_path, monkeypatch):
    gr = pytest.importorskip("gradio")
    import webui
    monkeypatch.setenv("SHORTSFLOW_TEMPLATES", str(tmp_path))
    ref = tmp_path / "ref.mp4"
    ref.write_bytes(b"x")
    monkeypatch.setattr(sc, "analyse", lambda *a, **k: _m(shot=2.0))
    msg, update = webui.copy_reel_style(None, str(ref), "web-ref", "HORMOZI")
    assert "Saved as **web-ref**" in msg and "Pace: fast" in msg and "not detected" in msg
    assert update["value"] == "web-ref"
    msg, _ = webui.copy_reel_style(None, "", "x", "HORMOZI")
    assert "Upload a reel" in msg
    msg, _ = webui.copy_reel_style(None, str(tmp_path / "gone.mp4"), "x", "HORMOZI")
    assert msg.startswith("Not saved")


def test_a_link_is_downloaded_first_and_failures_are_plain(tmp_path, monkeypatch):
    ref = tmp_path / "reference.mp4"
    ref.write_bytes(b"x")
    seen = {}

    def fake_download(url, folder, filename="x.mp4"):
        seen["url"] = url
        return str(ref)
    assert sc.fetch_reference("https://example.com/v", download=fake_download) == str(ref)
    assert seen["url"] == "https://example.com/v"

    def broken(url, folder, filename="x.mp4"):
        raise RuntimeError("Video unavailable")
    with pytest.raises(ValueError, match="could not be downloaded"):
        sc.fetch_reference("https://example.com/v", download=broken)

    monkeypatch.setattr(sc, "fetch_reference", lambda u: str(ref))
    monkeypatch.setattr(sc, "analyse", lambda *a, **k: _m(shot=2.0))
    path, lines = sc.clone("https://youtu.be/abc", "from-link", folder=str(tmp_path / "t"))
    assert path.endswith("from-link.json") and lines[0].startswith("Pace: fast")


ENTRIES = [
    {"id": 1, "text": ["DAY 1", "Shillong"], "position": "upper", "role": "label", "font": "script"},
    {"id": 2, "text": ["DAY 2", "Falls"], "position": "upper", "role": "label", "font": "script"},
    {"id": 3, "text": ["DAY 3", "Valley"], "position": "upper", "role": "label", "font": "script"},
    {"id": 4, "text": ["Win a free trip", "Comment now"], "position": "middle", "role": "cta", "font": "bold"},
]


def test_structure_is_read_from_the_frames():
    s = sc.summarise_structure(ENTRIES)
    assert s["labels_over_footage"] and s["day_labels"] and s["label_position"] == "upper" and s["font"] == "script" and s["closing_cta"]
    assert sc.summarise_structure([{"id": 1, "text": [], "position": "none", "role": "none", "font": "none"}])["labels_over_footage"] is False
    assert sc.summarise_structure([])["day_labels"] is False


def test_recipe_for_an_itinerary_reel():
    recipe, lines = sc.to_recap_recipe(_m(shot=2.1), sc.summarise_structure(ENTRIES), days=5)
    assert recipe["recap_style"] == "cinematic" and recipe["recap_itinerary"] and recipe["recap_safe_text"]
    assert recipe["recap_font"] == "handwritten" and recipe["recap_end"] == "result" and recipe["recap_pace"] == "fast"
    assert recipe["recap_aspect"] == "9:16" and recipe["video_filter"] == "none"
    assert recipe["recap_length"] == round(2.8 * 7)                   # one readable shot per day plus opening and ending
    assert any("not copied" in line for line in lines)


def test_recipe_length_never_passes_the_limit_and_works_without_a_reader():
    recipe, lines = sc.to_recap_recipe(_m(shot=9.0), None, days=12, max_seconds=60)
    assert recipe["recap_length"] == 60 and "recap_style" not in recipe
    assert any("not read" in line for line in lines)


def test_recipe_does_not_override_what_the_user_typed():
    args = argparse.Namespace(recap_length=45, recap_style="auto", recap_font="default")
    done = sc.apply_recipe(args, {"recap_length": 20, "recap_style": "cinematic", "recap_font": "handwritten"}, ["--recap_length", "45"])
    assert args.recap_length == 45 and args.recap_style == "cinematic" and args.recap_font == "handwritten"
    assert "recap_length" not in done


def test_recipe_for_uses_the_reader_and_the_frames(tmp_path):
    ref = tmp_path / "ref.mp4"
    ref.write_bytes(b"x")
    import engine.style_clone as mod
    orig = mod.analyse
    mod.analyse = lambda *a, **k: _m(shot=2.0)
    try:
        recipe, _ = sc.recipe_for(str(ref), days=4, ask=lambda frames, prompt: ENTRIES, grab=lambda v, a, b, n: [b"jpg"] * n)
    finally:
        mod.analyse = orig
    assert recipe["recap_itinerary"] and recipe["recap_style"] == "cinematic"
    with pytest.raises(ValueError):
        sc.recipe_for(str(tmp_path / "none.mp4"))


def test_full_bleed_reference_gives_a_crop_layout():
    entries = [dict(e, fills_frame=True) for e in ENTRIES]
    s = sc.summarise_structure(entries)
    assert s["full_bleed"]
    recipe, lines = sc.to_recap_recipe(_m(shot=2.1), s, days=4)
    assert recipe["layout"] == "crop" and any("fills the whole frame" in line for line in lines)
    recipe, _ = sc.to_recap_recipe(_m(shot=2.1), sc.summarise_structure(ENTRIES), days=4)
    assert "layout" not in recipe


def test_label_gets_a_dark_band_behind_it(tmp_path):
    from PIL import Image
    from engine import trip_recap as tr
    layers = tr.cinematic_layers(str(tmp_path / "t"), "Charyn Canyon", small="DAY 2", safe=True, scrim=True)
    first, start = layers[0]
    assert first.endswith("_scrim.png") and start == 0.0
    img = Image.open(first)
    mid = img.getpixel((img.width // 2, int(img.height * 0.215)))[3]
    assert mid > 50 and img.getpixel((10, img.height - 5))[3] == 0          # dark behind the text, clear far away from it
    assert not any(png.endswith("_scrim.png") for png, _ in tr.cinematic_layers(str(tmp_path / "u"), "Charyn Canyon", small="DAY 2")[:1])


def _jpeg(colour_text=None, size=(200, 360)):
    import io
    from PIL import Image
    img = Image.new("RGB", size, (30, 120, 200))                 # blue sky
    if colour_text:
        for y in range(int(size[1] * 0.2), int(size[1] * 0.26)):
            for x in range(40, 160):
                img.putpixel((x, y), colour_text)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


def test_text_colour_is_measured_from_the_pixels():
    cream = sc.measure_text_colour([_jpeg((250, 240, 160)) for _ in range(6)])
    assert cream and cream.startswith("#f") and cream[3:5] > "d0"
    assert sc.measure_text_colour([_jpeg(None) for _ in range(6)]) is None             # blue sky alone is not text
    assert sc.measure_text_colour([]) is None


def test_text_look_reaches_the_recipe():
    entries = [dict(e, color="#ffffff", size="large", weight="bold", glow=True, fills_frame=True) for e in ENTRIES[:3]] + [ENTRIES[3]]
    s = sc.summarise_structure(entries)
    s["text_color"] = "#f8f0a4"
    recipe, lines = sc.to_recap_recipe(_m(shot=2.1), s, days=4)
    assert recipe["recap_text_style"] == "color=#f8f0a4,size=1.4,bold,glow"
    assert recipe["recap_end"] == "result"
    from engine import trip_recap as tr
    ts = tr.parse_text_style(recipe["recap_text_style"])
    assert ts == {"color": (248, 240, 164), "scale": 1.4, "bold": True, "glow": True}
    assert tr.parse_text_style("nonsense,size=x")["scale"] == 1.0


def test_styled_label_draws_in_the_chosen_colour(tmp_path):
    from PIL import Image
    from engine import trip_recap as tr
    png = tr.cinematic_layers(str(tmp_path / "t"), "Place", small="DAY 2", safe=True, style="color=#f8f0a4,bold")[-1][0]
    px = [p for p in Image.open(png).getdata() if p[3] > 250]
    assert px and any(abs(p[0] - 248) < 8 and abs(p[2] - 164) < 8 for p in px)


def test_two_readings_are_merged_so_one_bad_answer_cannot_drop_the_font():
    a = [{"id": 1, "text": ["DAY 1", "Place"], "role": "label", "font": "sans", "weight": "regular", "glow": False, "fills_frame": True, "size": "medium"}] * 2
    b = [{"id": 1, "text": ["DAY 1", "Place"], "role": "label", "font": "script", "weight": "bold", "glow": True, "fills_frame": True, "size": "large"}] * 2
    m = sc.merge_entries(a, b)
    assert m[0]["font"] == "script" and m[0]["weight"] == "bold" and m[0]["glow"] and m[0]["size"] == "large"
    assert sc.merge_entries([], b) == b and sc.merge_entries(a, b[:1]) == a
    assert sc.summarise_structure(m + m)["font"] == "script"


def test_a_display_serif_reference_gets_the_display_font():
    entries = [dict(e, font="display_serif") for e in ENTRIES[:3]] + [ENTRIES[3]]
    recipe, lines = sc.to_recap_recipe(_m(shot=2.1), sc.summarise_structure(entries), days=4)
    assert recipe["recap_font"] == "display" and any("Abril" in line for line in lines)
    a = [dict(ENTRIES[0], font="script")] * 2
    b = [dict(ENTRIES[0], font="display_serif")] * 2
    assert sc.merge_entries(a, b)[0]["font"] == "display_serif"


def test_itinerary_typography_uses_the_display_font_and_a_tiered_headline(tmp_path):
    from PIL import Image
    from engine import trip_recap as tr
    tr.set_text_font("display")
    try:
        assert tr._text_font_file("Charyn Canyon")[0] == "AbrilFatface-Regular.ttf"
        layers = tr.cinematic_layers(str(tmp_path / "t"), "Charyn Canyon", small="DAY 2", safe=True, scrim=True, style="color=#f8fea5,size=1.4")
        assert len(layers) == 3 and layers[0][0].endswith("_scrim.png")             # band, "DAY 2", place name
        head = tr.headline_layers(str(tmp_path / "h"), "5-DAY", "Almaty", "Trip Plan")
        assert head[0][0].endswith("_scrim.png") and head[1][0].endswith("_headline.png")
        assert any(p[3] > 250 for p in Image.open(head[1][0]).getdata())
    finally:
        tr.set_text_font("default")
    assert tr._text_font_file("Charyn Canyon")[0] == "Anton-Regular.ttf"


def test_itinerary_picks_the_most_scenic_shot_of_a_day():
    from engine import trip_recap as tr
    cands = [{"file": f"v{i}.mp4", "start": 0.0, "end": 3.0} for i in range(5)]
    colour = {f"v{i}.mp4": s for i, s in enumerate([0.2, 0.9, 0.5, 0.8, 0.1])}
    grab = lambda f, a, b: [f.encode()]                                  # the "frame" is just the file name
    chosen, others = tr.pick_scenic(cands, 1, grab, rate=None, score=lambda jpg: colour[jpg.decode()])
    assert chosen[0]["file"] == "v1.mp4" and others[0]["file"] == "v3.mp4"          # best first, the rest as alternatives
    # the vision model overrules the colour score: it finds v3 a real view and v1 a face close-up, and drops v2 (added text)
    ratings = {"v1.mp4": {"score": 1, "overlay": False}, "v3.mp4": {"score": 9, "overlay": False}, "v2.mp4": {"score": 10, "overlay": True}}
    rate = lambda frames: [ratings.get(f.decode(), {"score": 0, "overlay": False}) for f in frames]
    chosen, others = tr.pick_scenic(cands, 1, grab, rate=rate, score=lambda jpg: colour[jpg.decode()])
    assert chosen[0]["file"] == "v3.mp4" and "v2.mp4" not in [c["file"] for c in chosen + others[:2]]
    two, _ = tr.pick_scenic(cands, 2, grab, rate=None, score=lambda jpg: colour[jpg.decode()])
    assert [c["file"] for c in two] == ["v1.mp4", "v3.mp4"]                          # time order within the day


def test_recap_plan_is_written_and_reviewed_shots_replace_the_picks(tmp_path):
    import json
    from engine import trip_recap as tr
    infos = [("a.mp4", 60.0, 1920, 1080), ("b.mp4", 40.0, 1080, 1920)]
    days = [{"infos": infos, "moments": [{"file": "a.mp4", "start": 5.0, "end": 8.0, "size": (1920, 1080), "place": "Lake"}],
             "alts": [{"file": "b.mp4", "start": 10.0, "end": 13.0, "size": (1080, 1920)}] * 5, "places": [{"name": "Lake"}]}]
    path = tr.write_recap_plan(str(tmp_path), "Trip", days, layout="crop")
    plan = tr.read_recap_plan(str(tmp_path))
    assert plan["layout"] == "crop"
    assert path.endswith("recap_plan.json") and plan["days"][0]["place"] == "Lake"
    assert plan["days"][0]["moments"][0]["file"] == "a.mp4" and len(plan["days"][0]["alternatives"]) == 3
    chosen = tmp_path / "chosen.json"
    chosen.write_text(json.dumps({"days": [[{"file": "b.mp4", "start": 12, "end": 15.5}]]}), encoding="utf-8")
    tr.apply_chosen_moments(days, str(chosen))
    assert days[0]["moments"][0]["file"] == "b.mp4" and days[0]["moments"][0]["size"] == (1080, 1920)
    for bad in ({"days": []}, {"days": [[]]}, {"days": [[{"file": "x.mp4", "start": 0, "end": 3}]]}, {"days": [[{"file": "a.mp4", "start": 1, "end": 1.2}]]}):
        chosen.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            tr.apply_chosen_moments(days, str(chosen))
    assert tr.read_recap_plan(str(tmp_path / "none")) is None


def test_web_review_of_recap_shots_builds_the_chosen_file_and_the_command(tmp_path, monkeypatch):
    import json
    pytest.importorskip("gradio")
    import webui
    from engine import plan as plan_mod
    monkeypatch.setattr(webui, "ROOT", str(tmp_path))
    session = tmp_path / "sessions" / "trip_20261115_000000"
    session.mkdir(parents=True)
    plan = {"title": "T", "days": [
        {"day": 1, "place": "Lake", "moments": [{"file": "a.mp4", "start": 5.0, "end": 8.0, "w": 1920, "h": 1080, "place": "Lake"}],
         "alternatives": [{"file": "b.mp4", "start": 20.0, "end": 23.0, "w": 1080, "h": 1920}]},
        {"day": 2, "place": "Pass", "moments": [{"file": "c.mp4", "start": 1.0, "end": 4.0, "w": 1920, "h": 1080, "place": "Pass"}], "alternatives": []}]}
    (session / "recap_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    webui.save_command(str(session), ["py", "main.py", "--mode", "TRIP", "--recap_plan_only", "--recap_aspect", "9:16"])
    monkeypatch.setattr(plan_mod, "make_preview", lambda *a, **k: "preview.mp4")
    shown = webui.latest_recap_plan(str(tmp_path))
    assert shown["days"][0]["moments"][0]["preview"] == "preview.mp4" and shown["days"][0]["alternatives"][0]["preview"] == "preview.mp4"
    seen = {}
    monkeypatch.setattr(webui, "_run", lambda cmd: iter([("log", [])]) if seen.update(cmd=cmd) is None else iter(()))
    # day 1: take alternative 1; day 2: keep the shot but trim it
    out = list(webui.render_recap_plan(str(session), True, True, "1", "current", 5.0, 2.0, 8.0, 3.5))
    assert "--recap_plan_only" not in seen["cmd"] and seen["cmd"][seen["cmd"].index("--recap_moments") + 1].endswith("recap_moments.json")
    chosen = json.loads((session / "recap_moments.json").read_text(encoding="utf-8"))
    assert chosen["days"][0] == [{"file": "b.mp4", "start": 20.0, "end": 23.0}] and chosen["days"][1] == [{"file": "c.mp4", "start": 2.0, "end": 3.5}]
    with pytest.raises(Exception):                                   # no shot left for day 2
        list(webui.render_recap_plan(str(session), True, False, "current", "current", 5.0, 2.0, 8.0, 3.5))


def test_recap_review_ignores_files_that_look_like_sessions(tmp_path):
    pytest.importorskip("gradio")
    import webui
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "trip_20261115_000001.log").write_text("log", encoding="utf-8")
    assert webui.latest_recap_plan(str(tmp_path)) is None


def test_render_handler_repeats_the_status_for_the_panel(monkeypatch):
    pytest.importorskip("gradio")
    import webui
    monkeypatch.setattr(webui, "render_recap_plan", lambda session, *v: iter([("Working...", "log", None, None), ("Done", "log", "v.mp4", None)]))
    out = list(webui.render_recap_plan_handler("s")(1, 2))
    assert out == [("Working...", "log", None, None, "Working..."), ("Done", "log", "v.mp4", None, "Done")]
