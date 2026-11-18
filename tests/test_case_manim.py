import json

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
    out = cm.render_scene(GOOD, str(tmp_path), portrait=False)
    assert out.endswith("ExplainerScene.webm")
    assert "-t" in seen["cmds"][0] and "yuva420p" in seen["cmds"][1]
