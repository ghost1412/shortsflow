"""The review card shows what ShortsFlow itself noticed about a clip."""
import json

from shortsflow import review


def test_notes_from_the_results_file_reach_the_card_and_read_as_advice(tmp_path):
    video = tmp_path / "video_clip_1.mp4"
    video.write_bytes(b"x")
    note = {"code": "ending", "text": "It stops on \"and\".", "try": "End it at 31.0 s (--end 31.0 in the editor)."}
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"clips": [{"clip_index": 1, "video_path": str(video), "notes": [note, {"code": "x"}]}]}), encoding="utf-8")
    (card,) = review.load_results(str(path))
    assert card["notes"] == [note]                                   # a note without text is dropped
    text = review.notes_text(card)
    assert text.startswith("**Worth a look:**") and "It stops on" in text and "Try: End it at 31.0 s" in text


def test_a_clip_with_no_notes_shows_nothing():
    assert review.notes_text({"notes": []}) == "" and review.notes_text({}) == ""
