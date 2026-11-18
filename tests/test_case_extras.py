import wave

from engine import case_footage, case_sfx


def test_pick_link_prefers_the_width_closest_to_the_wish():
    files = [{"link": "a", "width": 640}, {"link": "b", "width": 1280}, {"link": "c", "width": 3840}, {"link": "d", "width": 1920, "file_type": "video/webm"}]
    assert case_footage.pick_link(files, 1280) == "b"
    assert case_footage.pick_link([], 1280) is None


def test_fetch_needs_a_key_and_uses_the_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)           # a key in the environment must not make the test call the network
    assert case_footage.fetch("ships", str(tmp_path), api_key="") is None
    calls = []

    class R:
        def __init__(self, data=None, content=b""):
            self._d, self.content = data, content

        def raise_for_status(self):
            pass

        def json(self):
            return self._d

    def get(url, **kw):
        calls.append(url)
        if "search" in url:
            return R({"videos": [{"duration": 12, "video_files": [{"link": "https://v/1.mp4", "width": 1280}]}]})
        return R(content=b"video")
    path, secs = case_footage.fetch("ships", str(tmp_path), api_key="k", get=get)
    assert secs == 12.0 and open(path, "rb").read() == b"video"
    again = case_footage.fetch("ships", str(tmp_path), api_key="k", get=get)
    assert again == (path, 12.0) and len(calls) == 2          # the second call came from the cache


def test_sfx_track_is_a_stereo_wav_the_length_of_the_video(tmp_path):
    out = case_sfx.build_track(str(tmp_path / "s.wav"), 5.0, [0.5, 3.0], [1.0, 2.0])
    with wave.open(out) as w:
        assert w.getnchannels() == 2 and abs(w.getnframes() / w.getframerate() - 6.0) < 0.1


def test_fetch_image_picks_the_size_for_the_shape_and_uses_the_cache(tmp_path):
    seen = []

    class R:
        def __init__(self, data=None, content=b""):
            self._d, self.content = data, content

        def raise_for_status(self):
            pass

        def json(self):
            return self._d

    def get(url, **kw):
        seen.append(url)
        if "search" in url:
            return R({"photos": [{"src": {"large2x": "https://p/wide.jpg", "portrait": "https://p/tall.jpg"}}]})
        return R(content=b"jpg")
    wide = case_footage.fetch_image("ships", str(tmp_path), "landscape", api_key="k", get=get)
    tall = case_footage.fetch_image("ships", str(tmp_path), "portrait", api_key="k", get=get)
    assert wide.endswith(".jpg") and tall.endswith(".jpg") and wide != tall
    assert "https://p/wide.jpg" in seen and "https://p/tall.jpg" in seen
    n = len(seen)
    assert case_footage.fetch_image("ships", str(tmp_path), "landscape", api_key="k", get=get) == wide and len(seen) == n


def test_backgrounds_for_every_choice(tmp_path):
    from engine import case_render as cr
    script = {"sections": [{"footage": []}, {"footage": []}]}
    photo = tmp_path / "bg.jpg"
    photo.write_bytes(b"x")
    clip = tmp_path / "bg.mp4"
    clip.write_bytes(b"x")
    assert cr.backgrounds_for(script, str(tmp_path), "16:9", "none") is None
    assert cr.backgrounds_for(script, str(tmp_path), "16:9", "footage", has_pexels=False) is None
    assert cr.backgrounds_for(script, str(tmp_path), "16:9", "images", has_pexels=False) is None
    own = cr.backgrounds_for(script, str(tmp_path), "16:9", str(photo))
    assert len(own) == 2 and own[0][0]["kind"] == "image" and own[0][0]["path"] == str(photo)
    assert cr.backgrounds_for(script, str(tmp_path), "16:9", str(tmp_path / "notes.txt")) is None
    video = cr.user_background(script, str(clip), probe=lambda p: 12.5)
    assert video[1][0] == {"path": str(clip), "kind": "video", "seconds": 12.5}
    props = cr.build_props(dict(title="T", verified=True, sources=[], sections=[dict(id="a", title="A", scene="quote", narration="x", on_screen=["one"])]),
                           [(2.0, 8.0)], [[]], footage=[own[0]])
    assert props["sections"][0]["footage"][0]["kind"] == "image"


def test_cached_voice_needs_every_section(tmp_path):
    import json
    from engine import case_render as cr
    script = {"sections": [{}, {}]}
    for i in (1, 2):
        (tmp_path / f"voice_{i:02d}.mp3").write_bytes(b"x")
        (tmp_path / f"subs_{i:02d}.json").write_text(json.dumps([{"word": "hi", "start": 0, "end": 0.3}]), encoding="utf-8")
    audios, words = cr.cached_voice(script, str(tmp_path))
    assert len(audios) == 2 and words[0][0]["word"] == "hi"
    (tmp_path / "subs_02.json").write_text("[]", encoding="utf-8")
    assert cr.cached_voice(script, str(tmp_path)) is None                       # a section without words is not usable
    (tmp_path / "voice_02.mp3").unlink()
    assert cr.cached_voice(script, str(tmp_path)) is None


def test_attach_clips_reuses_per_shape_and_never_generates_in_a_draft(tmp_path):
    from engine import case_render as cr
    script = {"title": "T", "sections": [{"scene": "flow", "title": "A"}, {"scene": "quote", "title": "B"}]}
    made = []
    folder = tmp_path / "manim_01_16x9" / "videos"
    folder.mkdir(parents=True)
    (folder / "ExplainerScene.webm").write_bytes(b"x")
    make = lambda *a, **k: made.append(1)
    got = cr.attach_clips(script, [(2, 10), (10, 20)], str(tmp_path), None, make=make, probe=lambda p: 8.0, tag="16x9", reuse=True, generate=False)
    assert got[0]["path"].endswith("ExplainerScene.webm") and got[0]["rate"] == 1.0 and got[1] is None and not made
    other = cr.attach_clips(script, [(2, 10), (10, 20)], str(tmp_path), None, make=make, probe=lambda p: 8.0, tag="9x16", reuse=True, generate=False)
    assert other == [None, None] and not made                                  # the portrait shape has no animation of its own yet


def test_case_tab_resume_and_draft_arguments(tmp_path):
    import json
    from shortsflow import web_args
    args = web_args.case_args("", resume="sessions/case_1", draft=True, theme="neon")
    assert "--prompt" not in args and args[args.index("--case_resume") + 1] == "sessions/case_1" and "--case_draft" in args
    assert "--session_dir" not in args
    session = tmp_path / "sessions" / "case_9"
    session.mkdir(parents=True)
    (session / "script.json").write_text(json.dumps({"title": "A title", "sections": [{}, {}]}), encoding="utf-8")
    assert web_args.list_case_sessions(str(tmp_path)) == []                    # no narration yet
    for i in (1, 2):
        (session / f"voice_{i:02d}.mp3").write_bytes(b"x")
    listed = web_args.list_case_sessions(str(tmp_path))
    assert listed == [("A title (case_9)", str(session))]
    (session / "case_draft_16x9.mp4").write_bytes(b"x")
    assert web_args.find_case_videos(str(session)) == [] and len(web_args.find_case_videos(str(session), draft=True)) == 1
