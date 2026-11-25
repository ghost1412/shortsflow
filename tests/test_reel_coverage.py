"""The no-AI highlights reel covers the whole video (engine/analysis.py: reel_with_coverage)."""
from engine import analysis


def moment(start, score, length=45.0):
    return {"start": float(start), "end": start + length, "final_score": score, "viral_score": score}


def test_the_best_moments_all_in_one_part_do_not_make_a_reel_of_only_that_part():
    late = [moment(900 + i * 50, 90 - i) for i in range(8)]            # the five best are all in the last tenth of a 1000 s video
    early = [moment(10, 40), moment(250, 45), moment(500, 42)]
    picked = analysis.reel_with_coverage(late + early, 180.0, min_len=15.0)
    starts = sorted(m["start"] for m in picked)
    assert starts[0] < 300 and any(300 <= s < 700 for s in starts) and starts[-1] >= 900          # beginning, middle and end are all there
    total = sum(m["end"] - m["start"] for m in picked)
    assert 160 <= total <= 195


def test_the_reel_is_still_filled_to_the_target_and_nothing_overlaps():
    picked = analysis.reel_with_coverage([moment(i * 60, 50 + i) for i in range(20)], 300.0)
    ordered = sorted(picked, key=lambda m: m["start"])
    assert all(a["end"] <= b["start"] for a, b in zip(ordered, ordered[1:]))
    assert 270 <= sum(m["end"] - m["start"] for m in picked) <= 330
    assert analysis.reel_with_coverage([], 120.0) == []
