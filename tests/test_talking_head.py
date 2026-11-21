import os

import pytest
from PIL import Image

from engine import avatars as av
from engine import talking_head as th


def _photo(tmp_path, name="face.jpg"):
    p = tmp_path / name
    Image.new("RGB", (1400, 1800), "#c68e64").save(p)
    return str(p)


def test_a_photo_presenter_is_saved_with_its_picture_and_needs_it(tmp_path):
    home = str(tmp_path / "ws")
    key, path = av.save_photo(home, "Me", _photo(tmp_path))
    spec = av.load(key, home)
    assert spec["kind"] == "photo" and spec["photo"] == "me.jpg" and av.photo_path(spec, home).endswith("me.jpg")
    assert max(Image.open(av.photo_path(spec, home)).size) <= 1024
    assert ("Me (real photo, saved)", "me") in av.choices(home)
    with pytest.raises(ValueError, match="photo"):
        av.clean({"kind": "photo"})
    with pytest.raises(ValueError, match="photo"):
        av.clean({"kind": "photo", "photo": "../../secret.jpg"})
    with pytest.raises(ValueError, match="ready-made"):
        av.save_photo(home, "alex", _photo(tmp_path))
    with pytest.raises(ValueError, match="Choose a photo"):
        av.save_photo(home, "other", str(tmp_path / "missing.jpg"))


def test_the_add_on_is_reported_missing_until_installed(tmp_path):
    base = str(tmp_path / "th")
    assert not th.installed(base) and "install" in th.status(base)[1]
    with pytest.raises(RuntimeError, match="Not installed"):
        th.make(_photo(tmp_path), _photo(tmp_path), str(tmp_path / "o.mp4"), base=base)


def test_make_runs_sadtalker_once_and_caches_by_photo_and_voice(tmp_path, monkeypatch):
    base = str(tmp_path / "th")
    monkeypatch.setattr(th, "installed", lambda b=None: True)
    photo = _photo(tmp_path)
    voice = tmp_path / "v.mp3"
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=d=1", str(voice)], check=True)
    calls = []

    def fake_run(cmd, log, cwd=None):
        calls.append(cmd)
        work = cmd[cmd.index("--result_dir") + 1]
        with open(os.path.join(work, "result.mp4"), "wb") as f:
            f.write(b"video")
    out = th.make(photo, str(voice), str(tmp_path / "a.mp4"), base=base, run=fake_run, log=lambda *_: None)
    assert open(out, "rb").read() == b"video" and "--still" in calls[0] and "--enhancer" in calls[0]
    th.make(photo, str(voice), str(tmp_path / "b.mp4"), base=base, run=fake_run, log=lambda *_: None)
    assert len(calls) == 1                     # the second ask with the same photo and voice comes from the cache


def test_the_case_run_falls_back_to_the_still_photo(tmp_path, monkeypatch):
    from engine.modes import case
    home = tmp_path / "ws"
    home.mkdir()
    monkeypatch.chdir(home)
    key, _ = av.save_photo(str(home), "Me", _photo(tmp_path))
    spec = av.load(key, str(home))
    assert case._photo_presenter(spec, [], [], str(tmp_path), draft=True) == {"image": av.photo_path(spec, str(home))}
    monkeypatch.setattr(th, "installed", lambda b=None: False)
    assert "image" in case._photo_presenter(spec, [], [], str(tmp_path), draft=False)
    os.remove(av.photo_path(spec, str(home)))
    assert case._photo_presenter(spec, [], [], str(tmp_path), draft=False) == {}


def test_a_full_render_makes_the_talking_video_from_the_narration(tmp_path, monkeypatch):
    from engine import case_render
    from engine.modes import case
    home = tmp_path / "ws"
    home.mkdir()
    monkeypatch.chdir(home)
    key, _ = av.save_photo(str(home), "Me", _photo(tmp_path))
    spec = av.load(key, str(home))
    monkeypatch.setattr(th, "installed", lambda b=None: True)
    joined = []
    monkeypatch.setattr(case_render, "join_audio", lambda audios, timing, out, sfx=None: joined.append(out) or out)
    made = []

    def fake_make(photo, audio, out, **kw):
        made.append((photo, audio))
        open(out, "wb").write(b"v")
        return out
    monkeypatch.setattr(th, "make", fake_make)
    got = case._photo_presenter(spec, ["a.mp3"], [(0, 1)], str(tmp_path), draft=False)
    assert got["video"].endswith("presenter_talking.mp4") and made[0][1] == joined[0] and joined[0].endswith("presenter_voice.mp3")
    case._photo_presenter(spec, ["a.mp3"], [(0, 1)], str(tmp_path), draft=False)
    assert len(made) == 1                      # the second shape reuses the video made for the first
    monkeypatch.setattr(th, "make", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gpu out of memory")))
    os.remove(got["video"])
    assert "image" in case._photo_presenter(spec, ["a.mp3"], [(0, 1)], str(tmp_path), draft=False)
