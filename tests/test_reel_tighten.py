"""--tighten on the highlights video: captions and subtitles follow the pieces that were kept."""
from engine import reel_captions as rc


def data():
    words = [{"word": w, "start": s, "end": s + 0.5} for w, s in [("one", 10.0), ("um", 13.0), ("two", 16.0), ("three", 30.0)]]
    return {"segments": [{"start": 10.0, "end": 10.5, "text": "one", "words": words[:1]},
                         {"start": 13.0, "end": 13.5, "text": "um", "words": words[1:2]},
                         {"start": 16.0, "end": 16.5, "text": "two", "words": words[2:3]},
                         {"start": 30.0, "end": 30.5, "text": "three", "words": words[3:]}]}


def test_words_after_a_cut_pause_move_earlier_and_cut_words_vanish():
    parts = [(10.0, 17.0, 2.0, [[0.0, 1.0], [6.0, 7.0]]), (30.0, 31.0, 1.0)]      # seconds 1..6 of the first moment were cut
    words = rc.reel_words(parts, data(), xf=0.0)
    assert [(t, round(s, 2)) for s, _e, t in words] == [("one", 0.0), ("two", 1.0), ("three", 2.0)]
    cues = rc.reel_cues(parts, data(), xf=0.0)
    assert [(c["text"], c["start"]) for c in cues] == [("one", 0.0), ("two", 1.0), ("three", 2.0)]


def test_the_cut_piece_is_what_later_steps_measure_and_a_new_render_forgets_it(tmp_path):
    for name in ("seg_0.mp4", "seg_0_tight.mp4"):
        (tmp_path / name).write_bytes(b"x" * 2000)
    seconds = lambda p: 2.0 if p.endswith("_tight.mp4") else 7.0      # noqa: E731
    moments = [{"start": 10.0, "end": 17.0}]
    rc.save_kept(str(tmp_path), 0, str(tmp_path / "seg_0_tight.mp4"), [(0.0, 1.0), (6.0, 7.0)])
    assert rc.reel_parts(moments, str(tmp_path), seconds=seconds) == [(10.0, 17.0, 2.0, [[0.0, 1.0], [6.0, 7.0]])]
    rc.save_kept(str(tmp_path), 0)                                     # rendered again without --tighten
    assert rc.reel_parts(moments, str(tmp_path), seconds=seconds) == [(10.0, 17.0, 7.0)]
