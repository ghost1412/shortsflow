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
