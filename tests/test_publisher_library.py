import json
import os
import shutil
import subprocess

import pytest

from shortsflow import settings as st

from test_youtube_direct import FakeUploader, _connected    # noqa: E402  (the fakes are shared)


def _session(root, name, files, script=None, metadata=None):
    folder = root / "sessions" / name
    folder.mkdir(parents=True)
    for f in files:
        (folder / f).write_bytes(b"x" * 200)
    if script:
        (folder / "script.json").write_text(json.dumps(script), encoding="utf-8")
    if metadata:
        (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return folder


def test_the_library_lists_finished_videos_of_every_kind_and_skips_drafts_voice_and_work_folders(tmp_path):
    _session(tmp_path, "case_a", ["case_16x9.mp4", "case_9x16.mp4", "case_draft_16x9.mp4", "voice_all_16x9.mp4"], script={"title": "Heartbleed", "sections": [{"narration": "One. Two."}]})
    _session(tmp_path, "extraction_1", ["clip_1.mp4", "clip_2.mp4"], metadata=[{"file": "clip_1.mp4", "title": "First clip", "description": "d", "tags": ["a"]}])
    work = tmp_path / "sessions" / "case_a" / "manim_02_16x9"
    work.mkdir()
    (work / "ExplainerScene.mp4").write_bytes(b"x" * 200)
    videos = st.list_videos(str(tmp_path), min_bytes=0)
    names = sorted(os.path.basename(v["path"]) for v in videos)
    assert names == ["case_16x9.mp4", "case_9x16.mp4", "clip_1.mp4", "clip_2.mp4"]
    by_name = {os.path.basename(v["path"]): v for v in videos}
    assert by_name["case_9x16.mp4"]["shape"] == "tall" and by_name["case_16x9.mp4"]["shape"] == "wide"       # from the file name when the picture cannot be read
    assert by_name["case_16x9.mp4"]["title"] == "Heartbleed" and by_name["clip_1.mp4"]["title"] == "First clip" and by_name["clip_1.mp4"]["tags"] == ["a"]
    assert by_name["clip_2.mp4"]["title"] == "Clip 2"                                                          # no metadata: the file name, tidied
    assert "9:16 tall" in by_name["case_9x16.mp4"]["label"] and "MB" in by_name["case_9x16.mp4"]["label"]


def test_the_library_filters_by_format_and_by_size_and_is_newest_first(tmp_path):
    a = _session(tmp_path, "case_old", ["case_9x16.mp4"])
    b = _session(tmp_path, "case_new", ["case_16x9.mp4"])
    os.utime(a / "case_9x16.mp4", (1_000_000_000, 1_000_000_000))
    assert [v["shape"] for v in st.list_videos(str(tmp_path), min_bytes=0)] == ["wide", "tall"]
    assert [v["shape"] for v in st.list_videos(str(tmp_path), shape="tall", min_bytes=0)] == ["tall"]
    assert st.list_videos(str(tmp_path), shape="square", min_bytes=0) == []
    assert st.list_videos(str(tmp_path)) == []                                                                # the default size floor ignores tiny stubs
    assert st.list_videos(str(tmp_path / "nowhere")) == []
    assert b.exists()


def test_the_real_picture_size_decides_the_format_when_ffmpeg_can_read_it(tmp_path):
    ff = shutil.which("ffmpeg")
    if not ff:
        pytest.skip("ffmpeg not installed")
    folder = tmp_path / "sessions" / "x"
    folder.mkdir(parents=True)
    out = folder / "mystery.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1:r=10", str(out)], check=True)
    info = st.video_info(str(out))
    assert (info["width"], info["height"]) == (360, 640) and 0.5 < info["seconds"] < 2
    assert st.shape_of(str(out)) == "tall"                                                                    # named nothing like 9x16: the picture decides
    assert st.list_videos(str(tmp_path), min_bytes=0)[0]["shape"] == "tall"


def test_publishing_one_file_to_youtube_direct_uses_the_edited_details_and_records_the_file(tmp_path):
    folder = _session(tmp_path, "case_a", ["case_9x16.mp4"])
    path = str(folder / "case_9x16.mp4")
    _connected(str(tmp_path))
    up = FakeUploader()
    ok, lines = st.publish_file(path, "  My   edited title ", "My description", "alpha, #beta ,, gamma", ["youtube_direct"], privacy="unlisted", home=str(tmp_path), uploader=up)
    assert ok and "https://youtu.be/vid123" in lines[0]
    call = up.calls[0]
    assert call["title"] == "My edited title" and call["tags"] == ["alpha", "beta", "gamma"] and call["privacy"] == "unlisted"
    assert st.file_published_to(path).keys() == {"youtube_direct"}
    ok, lines = st.publish_file(path, "t", "d", "", ["youtube_direct"], home=str(tmp_path), uploader=up)
    assert not ok and "already published to youtube_direct" in lines[0] and len(up.calls) == 1
    ok, lines = st.publish_file(path, "t", "d", "", ["youtube_direct"], home=str(tmp_path), uploader=up, again=True)
    assert ok and len(up.calls) == 2


def test_a_tall_short_video_gets_the_shorts_tag_but_a_wide_one_does_not(tmp_path):
    tall = str(_session(tmp_path, "case_a", ["case_9x16.mp4"]) / "case_9x16.mp4")
    wide = str(_session(tmp_path, "case_b", ["case_16x9.mp4"]) / "case_16x9.mp4")
    _connected(str(tmp_path))
    up = FakeUploader()
    st._INFO[(tall, os.path.getmtime(tall))] = {"width": 1080, "height": 1920, "seconds": 60.0}
    st._INFO[(wide, os.path.getmtime(wide))] = {"width": 1920, "height": 1080, "seconds": 60.0}
    st.publish_file(tall, "T", "desc", "", ["youtube_direct"], home=str(tmp_path), uploader=up)
    st.publish_file(wide, "T", "desc", "", ["youtube_direct"], home=str(tmp_path), uploader=up)
    assert up.calls[0]["description"].endswith("#Shorts") and "#Shorts" not in up.calls[1]["description"]


def test_a_preview_sends_nothing_records_nothing_and_warns_about_a_format_mismatch(tmp_path):
    wide = str(_session(tmp_path, "case_b", ["case_16x9.mp4"]) / "case_16x9.mp4")
    ok, lines = st.publish_file(wide, "Title", "d", "", ["youtube_direct", "tiktok"], dry_run=True, home=str(tmp_path), env_path=str(tmp_path / ".env"), environ={})
    assert ok and any("preview only" in ln for ln in lines) and any("tiktok works best with a tall video" in ln for ln in lines)
    assert st.file_published_to(wide) == {}


def test_upload_post_gets_the_one_file_and_a_missing_key_says_where_to_add_it(tmp_path, monkeypatch):
    for name in st.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    path = str(_session(tmp_path, "case_a", ["case_9x16.mp4"]) / "case_9x16.mp4")
    env = str(tmp_path / ".env")
    ok, lines = st.publish_file(path, "T", "d", "", ["tiktok"], env_path=env, environ={})
    assert not ok and "Upload-Post key and profile in Settings" in lines[0]
    st.set_key(env, "UPLOAD_POST_API_KEY", "sk-abcdef1234567890WXYZ")
    st.set_key(env, "UPLOAD_POST_USER", "me")
    seen = {}

    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"success": True}

    def fake_post(url, headers, data, files, timeout):
        seen.update(url=url, headers=headers, fields=dict((k, v) for k, v in data if k in ("user", "title")), platforms=[v for k, v in data if k == "platform[]"])
        return Resp()
    ok, lines = st.publish_file(path, "My title", "d", "t1, t2", ["tiktok", "instagram"], env_path=env, environ={}, post=fake_post)
    assert ok and seen["platforms"] == ["tiktok", "instagram"] and seen["fields"]["user"] == "me" and seen["fields"]["title"] == "My title"
    assert st.file_published_to(path).keys() == {"tiktok", "instagram"}


def test_nothing_ticked_or_a_missing_file_is_a_clear_message(tmp_path):
    path = str(_session(tmp_path, "case_a", ["case_9x16.mp4"]) / "case_9x16.mp4")
    assert st.publish_file(path, "T", "d", "", [])[1] == ["Tick at least one place to publish to."]
    assert st.publish_file(str(tmp_path / "gone.mp4"), "T", "d", "", ["youtube_direct"])[1] == ["That video file is no longer there."]
    assert st.publish_file(path, "T", "d", "", ["nonsense"])[0] is False
