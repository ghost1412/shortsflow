"""A see-through HUD changes brightness with the scene behind it but its outline stays: the sides must not be cropped away."""
import numpy as np
import pytest

from engine import game_framing as gf

W, H = gf.THUMB_W, 180
MOMENTS = [(0.0, 30.0), (100.0, 130.0)]


def scene(t, hud=False, bars=False):
    """A moving scene (soft blocks that shift with time); `hud`: a see-through gauge outline at the lower left; `bars`: black bars above and below."""
    rng = np.random.default_rng(int(t * 10))
    coarse = rng.uniform(40, 200, (9, 16))
    frame = np.kron(coarse, np.ones((20, 20)))[:H, :W].astype(np.float32)
    frame = np.roll(frame, (int(rng.integers(20)), int(rng.integers(20))), axis=(0, 1))      # the scene's own edges move with it
    if hud:
        ys, xs = np.ogrid[:H, :W]
        for cx, cy, r in ((34, 140, 26), (286, 140, 26), (34, 30, 18)):
            ring = np.abs(np.hypot(xs - cx, ys - cy) - r) < 1.6
            frame[ring] = frame[ring] * 0.35 + 255 * 0.65                 # half see-through: its brightness follows the scene
    if bars:
        frame[:22] = 0
        frame[-22:] = 0
    return frame


@pytest.fixture
def footage(monkeypatch):
    def use(**kind):
        monkeypatch.setattr(gf, "_frame", lambda video, t, w, h: scene(t, **kind))
    return use


def test_a_see_through_hud_is_found_where_the_still_picture_test_misses_it(footage):
    footage(hud=True)
    still = gf.measure("v", 0.0, 30.0, size=(1920, 1080))
    assert still["hud"] < gf.HUD_SHARE                                    # why the old test alone cropped it
    assert gf.fixed_outlines("v", MOMENTS, size=(1920, 1080)) >= gf.OUTLINE_SHARE
    framing, reason = gf.choose("v", [{"start": s, "end": e} for s, e in MOMENTS], size=(1920, 1080))
    assert framing == "fit" and "on-screen display" in reason


def test_a_moving_scene_without_a_hud_is_still_cropped_also_with_black_bars(footage):
    for kind in ({}, {"bars": True}):
        footage(**kind)
        assert gf.fixed_outlines("v", MOMENTS, size=(1920, 1080)) < gf.OUTLINE_SHARE
        assert gf.choose("v", [{"start": s, "end": e} for s, e in MOMENTS], size=(1920, 1080))[0] == "crop"


def test_a_picture_that_does_not_move_says_nothing(monkeypatch):
    monkeypatch.setattr(gf, "_frame", lambda video, t, w, h: scene(1.0, hud=True))
    assert gf.fixed_outlines("v", MOMENTS, size=(1920, 1080)) is None
