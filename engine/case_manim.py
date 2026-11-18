"""Manim clips for the sections of a case explainer: a diagram that is drawn, step by step, for what the narrator says.

The sectioned explainer (engine/case_study.py, case_render.py) draws simple scenes itself. For a section that is better shown as a
real animation (a mechanism, a process, a graph, a formula built up piece by piece) a model writes one short Manim scene, it is rendered
with the same Manim set-up the EXPLAINER mode uses, and the clip is laid over the section on a black background with a screen blend,
so the network background shows through. A scene that fails to parse or to render is retried with the error; when every try fails the
caller keeps the plain scene. No LaTeX is installed on most PCs, so the scene is told to use Text() only.
"""
import ast
import json
import os
import re

BACKGROUND = "#05070d"
MAX_TRIES = 3


def manim_prompt(section, seconds, topic="", portrait=False, accent="#00e5a8", error=None):
    """The model prompt for one section's Manim scene."""
    bounds = "x in [-3.8, 3.8], y in [-6.5, 6.5] (a tall vertical screen: stack things downwards)" if portrait else "x in [-4.2, 4.2], y in [-2.3, 2.3]"
    labels = "; ".join(str(x) for x in section.get("on_screen") or [])
    text = f"""Write ONE Manim Community Edition scene that visually explains this part of a video, in about {int(seconds)} seconds of animation.

Topic of the video: {topic}
Section: {section.get('title', '')}
What the narrator says over it: {section.get('narration', '')}
Key labels to show: {labels}

Rules:
- One class `ExplainerScene(Scene)`. Start the file with `from manim import *`. First line of construct: `self.camera.background_color = "{BACKGROUND}"`.
- NO LaTeX: never use Tex or MathTex, no backslash macros. Use Text() with short strings, font_size 28-40. Plain symbols such as ^2, =, +, x are fine.
- Show the mechanism as a diagram with shapes: RoundedRectangle boxes, Arrow, Line, Circle, a grid of squares, a bar that fills, Dot moving along a path.
  Colours: accent "{accent}", text "#e8f1ff", failure "#ff5d73", secondary "#3b82f6", dim "#7d8ba3".
- Build it step by step in the order of the narration, with self.play(..., run_time=...) and self.wait(...). About {int(seconds)} seconds in total.
- The screen has {bounds}. Keep every element inside it. Never put text on top of a shape: use next_to(..., buff=0.3) or place labels above or below.
- Do NOT draw a title or a section heading: the video shows one. Use the whole screen for the diagram, centred.
- Give every Text the argument font="Segoe UI" (a clean sans-serif; other fonts are substituted when it is missing).
- Never place two texts in the same corner or row: lay out with VGroup(...).arrange(DOWN or RIGHT, buff=0.4) and keep a margin of 0.6 from the edges.
- Real line breaks in the code, valid Python 3. Return ONLY one fenced python block."""
    if error:
        text += f"\n\nYour previous attempt failed with this error, fix it:\n{str(error)[-600:]}"
    return text


FENCE = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.S)


def extract_code(reply):
    """The python code of a model reply: the first fenced block, else the "code" field of a JSON answer, else the whole text when it
    looks like code. '' when none."""
    reply = str(reply or "")
    m = FENCE.search(reply)
    code = m.group(1).strip() if m else ""
    if not code:
        blob = re.search(r"\{.*\}", reply, re.S)
        try:
            data = json.loads(blob.group(0)) if blob else None
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("code"), str):
            code = data["code"].strip()
    if not code:
        code = reply.strip()
    return code if "ExplainerScene" in code else ""


def code_problem(code):
    """Why `code` cannot be used (a short sentence), None when it can."""
    if not code:
        return "no ExplainerScene class"
    if re.search(r"\b(Math)?Tex\(", code):
        return "Tex/MathTex needs LaTeX; use Text()"
    if re.search(r"\\(Psi|theta|alpha|beta|gamma|lambda|sigma|omega|rangle|langle|sqrt|frac|int|sum)", code):
        return "LaTeX macro inside Text()"
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"
    return None


def render_scene(code, out_dir, portrait=False, fps=30, timeout=300):
    """Render `code` (an ExplainerScene) with the Manim command line at 1080p and `fps`. Returns the mp4 path; raises RuntimeError
    with Manim's message when it fails."""
    import subprocess
    import sys
    os.makedirs(out_dir, exist_ok=True)
    script = os.path.join(out_dir, "scene.py")
    if not portrait:      # a smaller frame (9 x 5.06 units) makes everything drawn in it larger on screen
        code = code.replace("from manim import *", "from manim import *\nconfig.frame_width = 9\nconfig.frame_height = 5.0625", 1)
    with open(script, "w", encoding="utf-8") as f:
        f.write(code)
    size = "1080,1920" if portrait else "1920,1080"
    cmd = [sys.executable, "-m", "manim", "-ql", "--fps", str(fps), "-r", size, "--media_dir", out_dir, script, "ExplainerScene"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError("Manim render failed: " + (res.stderr or "")[-600:])
    found = [os.path.join(root, name) for root, _, names in os.walk(out_dir) for name in names if name == "ExplainerScene.mp4"]
    if not found:
        raise RuntimeError("Manim finished but no ExplainerScene.mp4 was written.")
    return max(found, key=os.path.getmtime)


def make_section_clip(section, seconds, out_dir, ask, render, topic="", portrait=False, accent="#00e5a8", tries=MAX_TRIES):
    """Path of a rendered Manim clip for the section, None when every try fails. `ask(prompt)` returns the model's text;
    `render(code, out_dir, portrait)` returns the mp4 path or raises. Each retry is told what went wrong."""
    error = None
    for _ in range(max(1, tries)):
        code = extract_code(ask(manim_prompt(section, seconds, topic, portrait, accent, error)))
        problem = code_problem(code)
        if problem:
            error = problem
            continue
        try:
            path = render(code, out_dir, portrait)
        except Exception as e:      # Manim errors are long: the end holds the cause
            error = str(e)[-600:]
            continue
        if path and os.path.exists(path):
            return path
        error = "the render produced no file"
    return None
