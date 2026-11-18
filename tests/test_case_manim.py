import json

import pytest

from engine import case_manim as cm

GOOD = "from manim import *\nclass ExplainerScene(Scene):\n    def construct(self):\n        self.wait(1)\n"
SECTION = {"title": "How", "narration": "A file broke a thing.", "on_screen": ["File", "Crash"]}


def test_extract_code_fenced_json_and_plain():
    assert cm.extract_code("text\n```python\n" + GOOD + "```\n").startswith("from manim import *")
    assert cm.extract_code(json.dumps({"code": GOOD})) == GOOD.strip()
    assert cm.extract_code(GOOD) == GOOD.strip()
    assert cm.extract_code("no scene here") == ""


def test_code_problem_catches_latex_and_syntax():
    assert cm.code_problem(GOOD) is None
    assert "Tex" in cm.code_problem(GOOD + "x = MathTex('a')\n")
    assert "SyntaxError" in cm.code_problem("class ExplainerScene(Scene):\n  def (:\n")
    assert cm.code_problem("") is not None


def test_make_section_clip_retries_with_the_error(tmp_path):
    prompts, calls = [], []
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")

    def ask(prompt):
        prompts.append(prompt)
        return "```python\n" + (GOOD if len(prompts) > 1 else "class ExplainerScene(Scene):\n  def (:\n") + "```"

    def render(code, d, portrait):
        calls.append(portrait)
        return str(clip)
    assert cm.make_section_clip(SECTION, 20, str(tmp_path), ask, render, topic="T") == str(clip)
    assert len(prompts) == 2 and "SyntaxError" in prompts[1] and calls == [False]


def test_make_section_clip_gives_up_after_the_tries(tmp_path):
    def render(code, d, portrait):
        raise RuntimeError("boom")
    assert cm.make_section_clip(SECTION, 20, str(tmp_path), lambda p: GOOD, render, tries=2) is None


def test_render_scene_asks_for_a_transparent_clip_and_returns_the_webm(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        class R:
            returncode, stderr = 0, ""
        seen.setdefault("cmds", []).append(cmd)
        if "manim" in cmd:
            folder = tmp_path / "videos" / "scene" / "1080p30"
            folder.mkdir(parents=True)
            (folder / "ExplainerScene.mov").write_bytes(b"mov")
        else:
            open(cmd[-1], "wb").write(b"webm")
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(cm, "check_clip", lambda mov, portrait=False: [])
    monkeypatch.setattr("engine.manim_overlap.overlap_problems", lambda code, d, portrait=False: [])
    out = cm.render_scene(GOOD, str(tmp_path), portrait=False)
    assert out.endswith("ExplainerScene.webm")
    assert "-t" in seen["cmds"][0] and any("yuva420p" in c for c in seen["cmds"])


def _canvas(draw, w=480, h=270):
    import numpy as np
    a = np.zeros((h, w), dtype="uint8")
    for x0, y0, x1, y1 in draw:
        a[y0:y1, x0:x1] = 255
    return a


def test_frame_problems_flags_cut_off_empty_and_small_drawings():
    good = [_canvas([(60, 50, 420, 220)])]
    assert cm.frame_problems(good) == []
    assert "cut off at the right" in cm.frame_problems([_canvas([(60, 50, 480, 220)])])[0]
    assert "cut off at the left" in cm.frame_problems([_canvas([(0, 50, 300, 220)])])[0]
    assert "almost nothing" in cm.frame_problems([_canvas([(200, 120, 204, 124)])])[0]
    assert "small part" in cm.frame_problems([_canvas([(200, 110, 280, 170)])])[0]
    assert "thin strip" in cm.frame_problems([_canvas([(40, 120, 440, 150)])])[0]
    assert cm.frame_problems([], False)
    tall = [_canvas([(40, 20, 440, 140)], w=480, h=600)]
    assert "tall frame" in cm.frame_problems(tall, portrait=True)[0]
    # a frame early in the scene may be nearly empty as long as another one fills it
    assert cm.frame_problems([_canvas([]), _canvas([(60, 50, 420, 220)])]) == []


def test_the_kit_is_copied_next_to_the_scene_and_a_failed_check_raises(tmp_path, monkeypatch):
    import os
    import pytest

    def fake_run(cmd, **kw):
        class R:
            returncode, stderr = 0, ""
        if "manim" in cmd:
            folder = tmp_path / "videos" / "scene" / "1080p30"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "ExplainerScene.mov").write_bytes(b"mov")
        else:
            open(cmd[-1], "wb").write(b"webm")
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(cm, "check_clip", lambda mov, portrait=False: ["everything sits in a small part of the frame; make it larger"])
    with pytest.raises(RuntimeError) as e:
        cm.render_scene(GOOD, str(tmp_path), portrait=False)
    assert "small part" in str(e.value) and os.path.isfile(tmp_path / "manim_kit.py")
    monkeypatch.setattr(cm, "check_clip", lambda mov, portrait=False: [])
    assert cm.render_scene(GOOD, str(tmp_path), portrait=False).endswith(".webm")
    assert cm.render_scene(GOOD, str(tmp_path), portrait=False, check=False).endswith(".webm")


def test_the_prompt_lists_the_kit_blocks():
    text = cm.manim_prompt({"title": "A", "narration": "n", "on_screen": []}, 20)
    for name in ("chain(", "branch(", "cycle(", "before_after(", "bar(", "from manim_kit import *"):
        assert name in text


def test_every_kit_block_named_in_the_prompt_exists_in_the_kit():
    from pathlib import Path
    kit = (Path(__file__).resolve().parents[1] / "engine" / "manim_kit.py").read_text(encoding="utf-8")
    prompt = cm.manim_prompt({"title": "A", "narration": "n", "on_screen": []}, 20)
    for needed in ("chain", "play_chain", "branch", "play_branch", "cycle", "play_cycle", "before_after", "play_before_after", "bar", "play_bar",
                   "box", "label", "callout", "fit", "highlight_each"):
        assert f"def {needed}(" in kit
        assert needed in prompt, f"the prompt does not mention {needed}"


def test_overlap_sentences_name_the_texts():
    from engine import manim_overlap as mo
    out = mo.sentences([[["text", "Ransom", "Deadline"], 0.5], [["box", "Label", ""], 0.2], [["text", "A", "B"], 0.9]])
    assert out[0].startswith('the texts "A" and "B" overlap (90%') and 'crosses the edge of a box' in out[2] and len(out) == 3
    assert mo.with_probe("print(1)") is None and "_overlap_snapshot" in mo.with_probe("from manim import *\nx = 1")


def test_a_scene_with_overlapping_texts_fails_the_render_before_the_picture_is_made(tmp_path, monkeypatch):
    import pytest
    ran = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError("manim must not run")))
    monkeypatch.setattr("engine.manim_overlap.overlap_problems", lambda code, d, portrait=False: ['the texts "A" and "B" overlap (50% of the smaller); move them apart'])
    with pytest.raises(RuntimeError) as e:
        cm.render_scene(GOOD, str(tmp_path), portrait=False)
    assert 'the texts "A" and "B" overlap' in str(e.value) and not ran


def test_the_overlap_probe_finds_a_real_overlap_and_passes_a_clean_scene(tmp_path):
    pytest.importorskip("manim")
    from engine import manim_overlap as mo
    bad = ("from manim import *\nclass ExplainerScene(Scene):\n    def construct(self):\n"
           "        a = Text('First label here', font_size=40)\n        b = Text('Second label here', font_size=40).shift(RIGHT * 0.5 + DOWN * 0.1)\n"
           "        self.play(FadeIn(a), FadeIn(b))\n        self.wait(0.5)\n")
    good = ("from manim import *\nclass ExplainerScene(Scene):\n    def construct(self):\n"
            "        a = Text('First label here', font_size=30).shift(UP)\n        b = Text('Second label here', font_size=30).shift(DOWN)\n"
            "        box = RoundedRectangle(width=5, height=1.2).shift(UP)\n        self.play(FadeIn(a), FadeIn(b), Create(box))\n        self.wait(0.5)\n")
    assert mo.overlap_problems(bad, str(tmp_path / "bad"))
    assert mo.overlap_problems(good, str(tmp_path / "good")) == []
