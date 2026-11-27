"""While both people are shown stacked, captions move to the line between the halves."""
from engine import caption_layout as cl
from engine import speaker_focus as sf
from engine import video_gen


def test_only_the_stacked_stretches_move_and_only_from_the_default_height():
    shots = [{"start": 0.0, "end": 4.0, "target": "L"}, {"start": 4.0, "end": 9.0, "target": "split"}]
    spans = sf.split_spans(shots)
    assert cl.seam_moves(spans, cl.DEFAULT_Y) == [{"from": 4.0, "to": 9.0, "y": cl.SEAM_Y}]
    assert cl.seam_moves(spans, 1500) == []                      # a height the user chose stays
    assert cl.seam_moves([], cl.DEFAULT_Y) == []


def test_a_tightened_clip_moves_the_stretch_onto_its_shorter_timeline():
    keeps = [(0.0, 2.0), (3.0, 6.0), (7.0, 10.0)]                # two one-second pauses cut out
    assert cl.seam_moves([(4.0, 9.0)], cl.DEFAULT_Y, keeps) == [{"from": 3.0, "to": 7.0, "y": cl.SEAM_Y}]
    assert cl.seam_moves([(2.1, 2.9)], cl.DEFAULT_Y, keeps) == []   # the stretch was inside a removed pause


def test_the_stretches_stay_with_the_cut_piece_and_a_new_cut_forgets_old_ones(tmp_path):
    piece = str(tmp_path / "temp_segments" / "seg_0.mp4")
    assert video_gen._load_split_spans(piece) == []
    video_gen._save_split_spans(piece, [(4.0, 9.0)])
    assert video_gen._load_split_spans(piece) == [[4.0, 9.0]]
    video_gen._save_split_spans(piece, [])
    assert video_gen._load_split_spans(piece) == []
