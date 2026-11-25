"""Regression tests for the recap audit (engine/trip_recap.py, engine/geo.py, engine/visual_context.py): odd inputs that used to be dropped or mis-handled."""
import json
import os
import subprocess

import pytest

from engine import geo, trip_recap as tr


def test_a_video_given_twice_counts_once_and_a_path_that_gives_nothing_is_named(tmp_path):
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"x")
    notes = tmp_path / "notes.txt"
    notes.write_text("hi")
    assert len(tr.collect_videos([str(tmp_path), str(clip)])) == 1
    said = tr.left_out([str(tmp_path), str(clip), str(notes), str(tmp_path / "missing.mp4")])
    assert len(said) == 2 and "not a video" in said[0] and "no such file" in said[1]


def test_only_a_real_day_word_numbers_a_day():
    names = ["day2", "TripDay3", "Day_04"]
    assert [int(tr._DAY_NUMBER.search(n).group(1)) for n in names] == [2, 3, 4]
    assert not tr._DAY_NUMBER.search("Holiday 2024") and not tr._DAY_NUMBER.search("monday_1")


def test_a_date_in_a_file_name_is_not_a_time_of_day():
    assert tr.file_seconds("083015_ab.mp4") == 8 * 3600 + 30 * 60 + 15
    assert tr.file_seconds("240502_ab.mp4") is None and tr.file_seconds("996060_x.mp4") is None


def test_a_shot_is_moved_earlier_so_it_does_not_run_past_its_video():
    assert tr.fit_in_file(10.0, 5.0, 100.0) == (10.0, 5.0)
    assert tr.fit_in_file(98.0, 5.0, 100.0) == (95.0, 5.0)
    assert tr.fit_in_file(1.0, 5.0, 3.0) == (0.0, 3.0)
    assert tr.fit_in_file(5.0, 5.0, 0) == (5.0, 5.0)


def test_a_title_does_not_repeat_its_own_day_number():
    assert tr.own_title("Day 2: Cliffs", "Day", 2) == "Cliffs" and tr.own_title("Day 2", "Day", 2) == ""
    assert tr.own_title("Day 22 on the coast", "Day", 2) == "Day 22 on the coast"


def test_the_names_after_a_day_with_no_readable_video_do_not_move_onto_other_days():
    assert tr.keep_names(["A", "B", "C"], [0, 2]) == ["A", "C"]
    assert tr.keep_names(["A"], [0, 1, 2]) == ["A"]


def test_a_day_always_keeps_one_shot_even_when_every_shot_is_boring():
    shots = [{"file": "a.mp4", "start": 0.0, "end": 4.0, "visual": {"empty": True}}, {"file": "a.mp4", "start": 5.0, "end": 9.0, "visual": {"empty": True}}]
    out = tr.drop_repeats(list(shots), [], lambda m: m, alike=lambda a, b: False)
    assert len(out) >= 1


def test_a_shot_already_shown_is_not_swapped_in_again_or_offered_as_an_alternative():
    shown = [{"file": "a.mp4", "start": 1.0, "end": 5.0}]
    assert tr.is_shown({"file": "a.mp4", "start": 1.0, "end": 5.0}, shown)
    assert not tr.is_shown({"file": "a.mp4", "start": 9.0, "end": 12.0}, shown)


def test_a_long_word_is_broken_instead_of_running_off_the_card():
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = tr._font(60, "x")
    lines = tr._wrap(draw, "Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch is long", font, 300)
    assert len(lines) >= 3 and all(draw.textlength(w, font=font) <= 300 for ln in lines for w in ln.split())


def test_an_iphone_location_tag_is_read_and_one_bad_tag_does_not_hide_a_good_one():
    reply = lambda tags: subprocess.CompletedProcess([], 0, stdout=json.dumps({"format": {"tags": tags}}))
    assert geo.video_location("v.mp4", run=lambda *a, **k: reply({"com.apple.quicktime.location.ISO6709": "+48.8584+002.2945/"})) == pytest.approx((48.8584, 2.2945))
    both = reply({"location": "garbage", "com.apple.quicktime.location.ISO6709": "+10.0+020.0/"})
    assert geo.video_location("v.mp4", run=lambda *a, **k: both) == pytest.approx((10.0, 20.0))


def test_a_cache_file_that_is_not_a_dict_is_ignored(tmp_path):
    cache = tmp_path / "names.json"
    cache.write_text("[1, 2]", encoding="utf-8")
    assert geo._load_cache(str(cache)) == {} and geo._load_cache(None) == {} and geo._load_cache(str(tmp_path / "none.json")) == {}
    cache.write_text('{"a": 1}', encoding="utf-8")
    assert geo._load_cache(str(cache)) == {"a": 1}


def test_loudness_is_one_value_per_second_whatever_the_sample_rate_of_the_sound(tmp_path):
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav = tmp_path / "tone.wav"
    made = subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=4:sample_rate=48000", str(wav)], capture_output=True)
    if made.returncode != 0 or not wav.exists():
        pytest.skip("ffmpeg could not make a test tone here")
    levels = tr.loudness_per_second(str(wav), ffmpeg=ffmpeg)
    assert len(levels) in (4, 5) and all(-60 < v < 0 for v in levels[:3])           # 6 values per second (720 for 2 minutes) before
