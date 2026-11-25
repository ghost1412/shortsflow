"""Offline regressions for the small modes (photo reel, music, filter, explainer): odd inputs, no rendering."""
import os
import subprocess
import types

import pytest


def _args(**kw):
    base = dict(photos_dir=None, music=None, session_dir=None, reel_type=None, reel_text=None, target_duration=30,
                prompt=None, smart_story=False, use_remotion=False, caption_style="HORMOZI")
    base.update(kw)
    return types.SimpleNamespace(**base)


def _stub_renderers(monkeypatch, seen):
    import engine.beat_sync
    import engine.video_gen
    import engine.remotion_renderer
    monkeypatch.setattr(engine.beat_sync, "detect_beats", lambda *a, **k: [])
    monkeypatch.setattr(engine.video_gen, "create_photo_reel_video", lambda **k: seen.update(k))
    monkeypatch.setattr(engine.remotion_renderer, "render_with_remotion", lambda **k: seen.update(k))


def test_photo_reel_photos_dir_that_is_a_file_exits_cleanly(tmp_path):
    from engine.modes import photo_reel
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    with pytest.raises(SystemExit) as e:
        photo_reel.run(_args(photos_dir=str(f), session_dir=str(tmp_path / "s")), 0, 0)
    assert e.value.code == 1


def test_photo_reel_folder_named_like_a_photo_is_skipped(tmp_path, monkeypatch):
    from engine.modes import photo_reel
    (tmp_path / "trip.jpg").mkdir()
    (tmp_path / "real.png").write_bytes(b"x")
    seen = {}
    _stub_renderers(monkeypatch, seen)
    with pytest.raises(SystemExit) as e:
        photo_reel.run(_args(photos_dir=str(tmp_path), session_dir=str(tmp_path / "s")), 0, 0)
    assert e.value.code == 0
    assert [os.path.basename(p) for p in seen["photo_paths"]] == ["real.png"]


def test_list_photos_skips_folders(tmp_path):
    from engine.photo_reel_types import list_photos
    (tmp_path / "x.jpg").mkdir()
    (tmp_path / "y.JPG").write_bytes(b"x")
    assert [os.path.basename(p) for p in list_photos(str(tmp_path))] == ["y.JPG"]


def test_photo_reel_missing_music_falls_back_to_default_track(tmp_path, monkeypatch, capsys):
    from engine.modes import photo_reel
    (tmp_path / "a.jpg").write_bytes(b"x")
    seen = {}
    _stub_renderers(monkeypatch, seen)
    monkeypatch.setattr(photo_reel, "default_music_or_silence", lambda d, s: "default.mp3")
    with pytest.raises(SystemExit):
        photo_reel.run(_args(photos_dir=str(tmp_path), music=str(tmp_path / "gone.mp3"), use_remotion=True,
                             session_dir=str(tmp_path / "s")), 0, 0)
    assert seen["audio_path"] == "default.mp3"
    assert "Music file not found" in capsys.readouterr().out


def test_photo_reel_extra_text_lines_warn(tmp_path, monkeypatch, capsys):
    from engine.modes import photo_reel
    import engine.photo_reel_types as t
    for n in "abc":
        (tmp_path / f"{n}.jpg").write_bytes(b"x")
    seen = {}
    _stub_renderers(monkeypatch, seen)
    hashes = {"a": (0, 0), "b": ((1 << 64) - 1, (1 << 64) - 1), "c": (0x5555555555555555, 0x0F0F0F0F0F0F0F0F)}
    monkeypatch.setattr(t, "analyse", lambda p: {"path": p, "sharp": 10.0, "date": None, "mtime": 0.0,
                                                  "hash": hashes[os.path.basename(p)[0]][0],
                                                  "dhash": hashes[os.path.basename(p)[0]][1]})
    monkeypatch.setattr(photo_reel, "default_music_or_silence", lambda d, s: None)
    with pytest.raises(SystemExit):
        photo_reel.run(_args(photos_dir=str(tmp_path), reel_type="tribute", reel_text="a|b|c|d|e",
                             session_dir=str(tmp_path / "s")), 0, 0)
    assert "5 lines for 3 photos" in capsys.readouterr().out


def test_music_long_title_is_shrunk_to_fit_and_text_is_one_line():
    from engine.modes.music import fit_fontsize, escape_ffmpeg_text
    assert fit_fontsize("Short") == 54
    from engine.modes.music import MAX_TITLE_CHARS
    assert fit_fontsize("x" * MAX_TITLE_CHARS) * 0.55 * MAX_TITLE_CHARS <= 961
    assert fit_fontsize("x" * 400) == 30
    assert escape_ffmpeg_text("a\nb\tc") == "a b c"
    assert escape_ffmpeg_text("it's 50%, ok: 1") == "it'\\''s 50\\%\\, ok\\: 1"


def test_music_creates_sessions_folder_for_a_custom_session_dir(tmp_path, monkeypatch):
    import engine.comfy_bridge as cb
    import engine.social_gen as sg
    from engine.modes import music
    monkeypatch.chdir(tmp_path)
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    monkeypatch.setattr(cb, "is_comfy_available", lambda: True)
    monkeypatch.setattr(cb, "generate_ai_audio", lambda *a, **k: str(audio))
    monkeypatch.setattr(cb, "generate_cinematic_backgrounds", lambda *a, **k: [str(audio)])
    monkeypatch.setattr(sg, "generate_expanded_music_prompt", lambda p: p)
    monkeypatch.setattr(sg, "generate_viral_metadata", lambda *a, **k: {"title": "T\nitle"})
    cmds = []

    def fake_run(cmd, **k):
        cmds.append(cmd)
        return types.SimpleNamespace(returncode=1, stderr="x")
    monkeypatch.setattr(subprocess, "run", fake_run)
    args = types.SimpleNamespace(prompt="p", script=None, user_context=None, target_duration=10, ckpt_name=None,
                                 video_id="1", session_dir=str(tmp_path / "elsewhere"))
    with pytest.raises(SystemExit):
        music.run(args, 0, 0)
    assert os.path.isdir(tmp_path / "sessions")
    assert "\n" not in cmds[-1][cmds[-1].index("-vf") + 1]


def _filter_args(src, **kw):
    d = dict(source_video=src, session_dir=None, video_filter="none", user_context=None, style_context=None,
             category=None, prompt=None)
    d.update(kw)
    return types.SimpleNamespace(**d)


def test_filter_missing_source_exits_1_without_traceback(tmp_path):
    from engine.modes import video_filter
    with pytest.raises(SystemExit) as e:
        video_filter.run(_filter_args(str(tmp_path / "nope.mp4"), session_dir=str(tmp_path / "s")), 0, 0)
    assert e.value.code == 1


def test_filter_without_hq_attribute_still_runs(tmp_path, monkeypatch):
    from engine.modes import video_filter
    import engine.video_gen as vg
    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    seen = {}
    monkeypatch.setattr(vg, "apply_standalone_video_filter", lambda *a, **k: seen.update(k))
    with pytest.raises(SystemExit) as e:
        video_filter.run(_filter_args(str(src), session_dir=str(tmp_path / "s")), 0, 0)
    assert e.value.code == 0 and seen["use_hq"] is False


def test_filter_failed_download_exits_1(tmp_path, monkeypatch):
    from engine.modes import video_filter
    monkeypatch.setattr(video_filter, "download_source_video_from_url", lambda *a, **k: None)
    with pytest.raises(SystemExit) as e:
        video_filter.run(_filter_args("https://example.com/v.mp4", session_dir=str(tmp_path / "s")), 0, 0)
    assert e.value.code == 1


def test_explainer_unreadable_audio_length_is_not_a_tenth_of_a_second(tmp_path, monkeypatch):
    from engine.modes import explainer
    import engine.script_gen as sg
    import engine.video_gen as vg
    import engine.voice_gen as vo
    video, audio = tmp_path / "m.mp4", tmp_path / "v.mp3"
    video.write_bytes(b"x")
    audio.write_bytes(b"x")
    monkeypatch.setattr(sg, "generate_manim_script", lambda *a, **k: {"title": "t", "code": "c", "voiceover_text": "hi"})
    monkeypatch.setattr(vg, "render_manim_scene", lambda *a, **k: str(video))
    monkeypatch.setattr(vo, "generate_voice", lambda *a, **k: (str(audio), None))
    cmds = []

    def fake_run(cmd, **k):
        cmds.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="N/A", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    args = types.SimpleNamespace(prompt="t", category=None, extract_mode="shorts", video_id="1",
                                 session_dir=str(tmp_path / "s"))
    with pytest.raises(SystemExit) as e:
        explainer.run(args, 0, 0)
    assert e.value.code == 0
    assert not any(c and c[0] == "ffmpeg" for c in cmds)       # nothing merged: the animation is kept
