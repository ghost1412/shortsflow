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
