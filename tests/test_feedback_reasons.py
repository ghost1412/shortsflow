"""A thumbs-down can say what was wrong; a reason that keeps coming up becomes advice."""
from engine import feedback


def down(reason=None):
    return {"title": "t", "duration": 30, "score": 60, "liked": False, **({"reason": reason} if reason else {})}


def test_a_reason_is_stored_only_with_a_thumbs_down_and_only_a_known_one(tmp_path):
    path = str(tmp_path / "f.json")
    feedback.record("a", 30, 60, False, path=path, reason="opening")
    feedback.record("b", 30, 60, True, path=path, reason="opening")            # a thumbs-up has no reason
    feedback.record("c", 30, 60, False, path=path, reason="because")           # not one of the known reasons
    got = feedback.load(path)
    assert got[0]["reason"] == "opening" and "reason" not in got[1] and "reason" not in got[2]


def test_no_advice_until_one_reason_clearly_keeps_coming_up():
    assert feedback.advice([down("opening"), down("opening")]) == ""                            # only twice
    assert feedback.advice([down("opening")] * 3 + [down("person")] * 3 + [down("cut")] * 3 + [down("title")] * 3) == ""   # none is the usual one
    assert "--cold_open" in feedback.advice([down("opening")] * 3 + [down("person")])
    assert "--layout split" in feedback.advice([down("person")] * 4 + [down("opening")])


def test_reasonless_ratings_do_not_count_and_the_summary_carries_the_advice():
    entries = [down()] * 5 + [down("captions")] * 3
    assert "caption" in feedback.advice(entries).lower()
    assert "caption" in feedback.summary(entries).lower()
    assert feedback.advice([]) == ""
