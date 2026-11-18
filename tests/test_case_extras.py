import wave

from engine import case_footage, case_sfx


def test_pick_link_prefers_the_width_closest_to_the_wish():
    files = [{"link": "a", "width": 640}, {"link": "b", "width": 1280}, {"link": "c", "width": 3840}, {"link": "d", "width": 1920, "file_type": "video/webm"}]
    assert case_footage.pick_link(files, 1280) == "b"
    assert case_footage.pick_link([], 1280) is None


def test_fetch_needs_a_key_and_uses_the_cache(tmp_path):
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
