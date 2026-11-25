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


def window(start, norm=0.5, length=48.0):
    return {"start": float(start), "end": start + length, "norm_score": norm, "text": "We measured the thing and it doubled in a year."}


def test_ai_picks_all_in_the_first_half_get_the_later_parts_filled_from_signal_windows():
    windows = [window(i * 50) for i in range(40)]                              # a 2000 s video
    picks = [moment(i * 100, 85, 45.0) for i in range(5)]                      # the model chose only 0-545 s
    reel = analysis.reel_with_ai_coverage(picks, windows, 240.0)
    ordered = sorted(reel, key=lambda m: m["start"])
    assert ordered[-1]["start"] >= 1400                                        # the end of the video is in
    assert any(m.get("reason") == "Signal Peak (Coverage)" for m in reel)
    assert all(a["end"] <= b["start"] for a, b in zip(ordered, ordered[1:]))
    assert 210 <= sum(m["end"] - m["start"] for m in reel) <= 260


def test_ai_picks_that_already_cover_the_video_are_kept_over_signal_windows():
    windows = [window(i * 50, norm=1.0) for i in range(40)]
    picks = [moment(s, 80, 45.0) for s in (10, 410, 810, 1210, 1610)]
    reel = analysis.reel_with_ai_coverage(picks, windows, 225.0)
    assert sorted(m["start"] for m in reel) == [10, 410, 810, 1210, 1610]


def test_ai_coverage_without_windows_or_picks_does_not_fail():
    assert analysis.reel_with_ai_coverage([], [window(0)], 120.0) == []
    picks = [moment(0, 80, 45.0), moment(100, 70, 45.0)]
    assert len(analysis.reel_with_ai_coverage(picks, [], 90.0)) == 2
