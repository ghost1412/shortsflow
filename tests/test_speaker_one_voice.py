"""One speaker whose voice rises and falls is not two speakers (the camera went to the silent listener); mouth movement is compared fairly."""
import numpy as np

from engine import speaker_focus as sf


def lean(n, who="L"):
    other = "R" if who == "L" else "L"
    return [{who: 2.0, other: 0.5} for _ in range(n)]


def test_one_voice_rising_and_falling_is_declined():
    for seed in range(12):
        rng = np.random.default_rng(seed)
        f0 = np.exp(rng.normal(np.log(178), 0.12, 62))                       # about 158-201 Hz between the 20th and 80th percentile
        assert sf.diarize_by_pitch(list(f0), [1.0] * 62, lean(62)) is None, seed


def test_two_voices_with_a_gap_between_them_are_still_told_apart():
    for low, high in ((120, 210), (170, 235)):
        rng = np.random.default_rng(3)
        truth = ["L"] * 40 + ["R"] * 40
        f0 = [float(np.exp(rng.normal(np.log(low if t == "L" else high), 0.04))) for t in truth]
        visual = [{"L": 2.0, "R": 0.5} if t == "L" else {"L": 0.5, "R": 2.0} for t in truth]
        got = sf.diarize_by_pitch(f0, [1.0] * 80, visual)
        assert got and np.mean([g == t for g, t in zip(got, truth)]) > 0.95, (low, high)


def test_a_few_stray_pitches_do_not_make_a_second_speaker():
    f0 = [200.0] * 90 + [100.0] * 9
    assert sf.diarize_by_pitch(f0, [1.0] * 99, lean(99)) is None


def samples(rows):
    return [{"t": i / 5, "faces": dict(r)} for i, r in enumerate(rows)]


def test_who_speaks_all_through_a_clip_is_not_scaled_down_to_a_listener():
    got = sf._motion_decisions(samples([{"L": 7.7, "R": 2.8}] * 30), np.ones(30))
    assert got == ["L"] * 30


def test_head_movement_in_the_pauses_does_not_hide_who_speaks():
    rows = [{"L": 11.4, "R": 2.5}] * 20 + [{"L": 8.2, "R": 3.1}] * 40      # in the pauses the speaker's face moves even MORE than while talking
    env = np.array([0.0] * 20 + [1.0] * 40)
    got = sf._motion_decisions(samples(rows), env)
    assert got[:20] == [None] * 20 and got[25:] == ["L"] * 35


def test_a_short_doubt_does_not_cut_to_the_view_of_both_but_a_long_one_does():
    times = [i / 5 for i in range(100)]
    short = ["L"] * 40 + ["split"] * 6 + ["L"] * 54
    assert [s["target"] for s in sf.shots_from_decisions(times, short, 20.0)] == ["L"]
    long_ = ["L"] * 40 + ["split"] * 25 + ["L"] * 35
    assert [s["target"] for s in sf.shots_from_decisions(times, long_, 20.0)] == ["L", "split", "L"]


def test_a_pitch_trackers_scattered_slips_to_half_the_pitch_are_not_a_second_speaker():
    f0 = [186.0] * 135
    for i in range(3, 135, 8):
        f0[i] = 93.0                                          # one or two samples at half the pitch, here and there
        if i % 3 == 0 and i + 1 < 135:
            f0[i + 1] = 93.0
    assert sf.diarize_by_pitch(f0, [1.0] * 135, lean(135)) is None


def test_a_second_speaker_who_talks_in_sentences_is_found_even_when_rare():
    truth = ["L"] * 60 + ["R"] * 18 + ["L"] * 40
    f0 = [190.0 if t == "L" else 105.0 for t in truth]
    visual = [{"L": 2.0, "R": 0.5} if t == "L" else {"L": 0.5, "R": 2.0} for t in truth]
    assert sf.diarize_by_pitch(f0, [1.0] * len(truth), visual) == truth
