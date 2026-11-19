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


def manim_prompt(section, seconds, topic="", portrait=False, accent="#00e5a8", error=None, full=False):
    """The model prompt for one section's Manim scene."""
    bounds = ("x in [-3.4, 3.4], y in [-6.0, 6.0] (a tall frame: stack things downwards, use the whole height)" if full else
              "x in [-3.4, 3.4], y in [-4.2, 4.2] (a tall frame: stack things downwards)") if portrait else "x in [-4.2, 4.2], y in [-2.3, 2.3]"
    labels = "; ".join(str(x) for x in section.get("on_screen") or [])
    text = f"""Write ONE Manim Community Edition scene that visually explains this part of a video, in about {int(seconds)} seconds of animation.

Topic of the video: {topic}
Section: {section.get('title', '')}
What the narrator says over it: {section.get('narration', '')}
Key labels to show: {labels}

Rules:
- One class `ExplainerScene(Scene)`. Start the file with `from manim import *`. Do NOT set a background colour: the clip is transparent and is laid over a video, so draw light shapes and text that read on a dark picture.
- NO LaTeX: never use Tex or MathTex, no backslash macros. Use Text() with short strings, font_size 28-40. Plain symbols such as ^2, =, +, x are fine.
- Show the mechanism as a diagram with shapes: RoundedRectangle boxes, Arrow, Line, Circle, a grid of squares, a bar that fills, Dot moving along a path.
  Colours: accent "{accent}", text "#e8f1ff", failure "#ff5d73", secondary "#3b82f6", dim "#7d8ba3".
- Build it step by step in the order of the narration, with self.play(..., run_time=...) and self.wait(...). About {int(seconds)} seconds in total.
- The screen has {bounds}. Keep every element inside it. Never put text on top of a shape: use next_to(..., buff=0.3) or place labels above or below.
- Do NOT draw a title or a section heading: the video shows one. Use the whole screen for the diagram, centred.
- Build the scene from the ready-made blocks of `manim_kit` (put `from manim_kit import *` right after `from manim import *`). They already fit the frame, space things and size the text; add your own motion on top (fades, highlights, moving dots, colour changes). Blocks:
  chain(labels, colors=None) + play_chain(self, group)        boxes joined by arrows, in order
  branch(root_text, child_texts) + play_branch(self, group)   one box with several below it
  cycle(labels) + play_cycle(self, group)                      a loop of steps
  before_after(before_text, after_text) + play_before_after(self, group)
  bar(caption, fraction) + play_bar(self, group)               a bar that fills to a share (0 to 1)
  box(text, color), label(text, size), callout(text, target), fit(group)    single pieces; colours ACCENT, TEXT, DIM, FAIL, BLUE
  highlight_each(self, group_or_list)                           pulse each part in turn, to keep a diagram moving
  Every builder returns a group already centred and inside the frame, so do NOT scale() or move() it; show several blocks one after another (FadeOut the last before the next).
  Reveal with the play_* helper (one part at a time), never with one FadeIn of the whole group.
- Texts are checked: no text may cover another text or cross the edge of a box (inside the box, or clear of it). Show things one after another instead of stacking them.
- Also checked: no line, arrow or dot may pass through a text. Put a label BESIDE the thing it names (label.next_to(thing, RIGHT or LEFT, buff=0.4)), never on it or on the path of a moving dot or line; keep a title at the top and the drawing below it. Use only the colour names ACCENT, TEXT, DIM, FAIL, BLUE.
- Keep it moving: something on screen must change at least every 3 seconds (reveal a part, highlight_each, a bar filling, a dot travelling). Never self.wait() longer than 2 seconds in one go; spread the time over the steps instead.
- Give every Text the argument font="Segoe UI" (a clean sans-serif; other fonts are substituted when it is missing).
- Never place two texts in the same corner or row: lay out with VGroup(...).arrange(DOWN or RIGHT, buff=0.4) and keep a margin of 0.6 from the edges.
- Real line breaks in the code, valid Python 3. Return ONLY one fenced python block."""
    if full:
        text += ("\n\nThis animation is the WHOLE picture of the video, running under the narration from the first word to the last, so it must keep building. "
                 "If the idea is geometric or numeric (shapes, areas, angles, graphs, curves, quantities), DRAW it with real Manim shapes (Polygon, Square, Circle, "
                 "Line, Axes, plots, bars) placed and coloured to show the idea, and move them (Transform, shift, rotate, fade, change colour) as the narrator says each "
                 "thing. Make the main drawing BIG: it should span at least 70% of the frame's width or height, with labels beside it, not a small figure in the middle. "
                 "Use the kit's chain, branch and box blocks only for steps and relationships, and label() / box() for short labels next to the shapes. Pass strings, "
                 "never Manim objects, to the kit's label functions.")
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


def frame_problems(alphas, portrait=False):
    """What is wrong with a rendered scene, from the alpha channel of sample frames (2-D uint8 arrays, 0 = nothing drawn): a list of plain
    sentences, empty when it looks fine. Checks: drawing cut off at an edge, almost nothing drawn, drawing confined to a small part of the frame."""
    import numpy as np
    if not alphas:
        return ["no frames could be read"]
    h, w = alphas[0].shape
    band_x, band_y = max(2, int(w * 0.012)), max(2, int(h * 0.012))
    cut, best, x0, y0, x1, y1 = set(), 0.0, w, h, 0, 0
    for a in alphas:
        on = a > 24
        best = max(best, float(on.mean()))
        if on[:, :band_x].sum() > 30:
            cut.add("left")
        if on[:, -band_x:].sum() > 30:
            cut.add("right")
        if on[:band_y, :].sum() > 30:
            cut.add("top")
        if on[-band_y:, :].sum() > 30:
            cut.add("bottom")
        ys, xs = np.where(on)
        if len(xs):
            x0, x1, y0, y1 = min(x0, int(xs.min())), max(x1, int(xs.max())), min(y0, int(ys.min())), max(y1, int(ys.max()))
    out = []
    if best < 0.006:
        return ["almost nothing is drawn: show the diagram larger and keep it on screen"]
    if cut:
        out.append(f"drawing is cut off at the {', '.join(sorted(cut))} edge; keep everything inside the frame (use the kit blocks or fit(group))")
    if (x1 - x0) < w * 0.42 and (y1 - y0) < h * 0.42:
        out.append("everything sits in a small part of the frame; make it larger and centre it")
    elif (y1 - y0) < h * 0.36 and not portrait:
        out.append("the drawing is a thin strip; use more of the frame height")
    elif portrait and (y1 - y0) < h * 0.45:
        out.append("the drawing fills only part of the height of the tall frame; stack things downwards and use the whole height")
    return out


def check_clip(mov, portrait=False, ffmpeg=None, every=2.5):
    """Sample frames of the transparent .mov (one every `every` seconds, saved small next to it in check_frames/) and return frame_problems."""
    import shutil
    import subprocess
    import numpy as np
    from PIL import Image
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    folder = os.path.join(os.path.dirname(mov), "check_frames")
    os.makedirs(folder, exist_ok=True)
    for stale in os.listdir(folder):               # the frames of an earlier attempt
        if stale.startswith("f_") and stale.endswith(".png"):
            os.remove(os.path.join(folder, stale))
    res = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", mov, "-vf", f"fps=1/{every},scale=480:-1", os.path.join(folder, "f_%02d.png")],
                         capture_output=True, text=True)
    if res.returncode != 0:
        return []                      # the check itself failed: do not block a clip over that
    alphas = []
    for name in sorted(os.listdir(folder)):
        if name.startswith("f_") and name.endswith(".png"):
            im = Image.open(os.path.join(folder, name)).convert("RGBA")
            alphas.append(np.asarray(im)[:, :, 3])
    return frame_problems(alphas, portrait) if alphas else []


def render_scene(code, out_dir, portrait=False, fps=30, timeout=900, check=True, full=False):
    """Render `code` (an ExplainerScene) with the Manim command line at 1080p and `fps`. Returns the path of the transparent .mov clip; raises RuntimeError
    with Manim's message when it fails."""
    import subprocess
    import sys
    os.makedirs(out_dir, exist_ok=True)
    script = os.path.join(out_dir, "scene.py")
    kit = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manim_kit.py")
    if os.path.isfile(kit):          # the ready-made blocks a scene may import (from manim_kit import *)
        import shutil
        shutil.copy2(kit, os.path.join(out_dir, "manim_kit.py"))
    # a smaller frame makes everything drawn in it larger on screen: 9 x 5.06 units for 16:9, 7.2 x 9 for the 4:5 portrait panel
    if portrait:
        frame = "config.frame_width = 7.2\nconfig.frame_height = 12.8" if full else "config.frame_width = 7.2\nconfig.frame_height = 9"
    else:
        frame = "config.frame_width = 9\nconfig.frame_height = 5.0625"
    code = code.replace("from manim import *", "from manim import *\n" + frame, 1)
    with open(script, "w", encoding="utf-8") as f:
        f.write(code)
    if check:
        from engine import manim_overlap
        crowded = manim_overlap.overlap_problems(code, out_dir, portrait)      # texts on top of each other, found from where Manim puts them
        if crowded:
            raise RuntimeError("The picture was checked and is not good enough yet: " + "; ".join(crowded))
    size = ("1080,1920" if full else "1080,1350") if portrait else "1920,1080"
    cmd = [sys.executable, "-m", "manim", "-ql", "-t", "--fps", str(fps), "-r", size, "--media_dir", out_dir, script, "ExplainerScene"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError("Manim render failed: " + (res.stderr or "")[-600:])
    found = [os.path.join(root, name) for root, _, names in os.walk(out_dir) for name in names if name == "ExplainerScene.mov"]
    if not found:
        raise RuntimeError("Manim finished but no ExplainerScene.mov was written.")
    mov = max(found, key=os.path.getmtime)
    if check:
        problems = check_clip(mov, portrait)
        if problems:
            raise RuntimeError("The picture was checked and is not good enough yet: " + "; ".join(problems))
    return to_alpha_webm(mov)


def to_alpha_webm(mov, ffmpeg=None):
    """The transparent Manim .mov as a VP9 .webm with alpha, which the Remotion renderer can decode (it has no QuickTime RLE decoder).
    Returns the .webm path; raises RuntimeError when FFmpeg fails."""
    import shutil
    import subprocess
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = os.path.splitext(mov)[0] + ".webm"
    res = subprocess.run([ffmpeg, "-y", "-i", mov, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32",
                          "-deadline", "realtime", "-cpu-used", "6", "-auto-alt-ref", "0", "-an", out], capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("Converting the animation to WebM failed: " + (res.stderr or "")[-300:])
    return out


def find_clip(folder):
    """The newest rendered animation (ExplainerScene.webm) under `folder`, None when there is none."""
    found = [os.path.join(root, name) for root, _, names in os.walk(folder) for name in names if name == "ExplainerScene.webm"]
    return max(found, key=os.path.getmtime) if found else None


CHECKED = "The picture was checked and is not good enough yet"       # the start of the message render_scene raises when only its checks object


# known crashes and the fix to tell the model on the retry (the error text alone did not teach a small model: it repeated the mistake)
HINTS = (
    ("camera' object has no attribute 'frame'", "The scene is a plain Scene: there is no self.camera.frame. Do not move or zoom the camera; keep everything in the fixed frame."),
    ("needs latex", "No LaTeX is installed: never use Tex or MathTex. Use Text() for every formula, written in plain characters."),
    ("name 'dim' is not defined", "Start the file with `from manim import *` and `from manim_kit import *`; only the names ACCENT, TEXT, DIM, FAIL, BLUE exist as colours."),
    ("is not defined", "Use only names that Manim or manim_kit define (start with `from manim import *` and `from manim_kit import *`); colours are ACCENT, TEXT, DIM, FAIL, BLUE."),
    ("'numpy.ndarray' object has no attribute", "A position such as LEFT or point.get_center() is a numpy array, not an object: draw a Dot, Line or Text and move that object instead."),
)


def with_hint(error):
    """The error text plus, when it is a known mistake, the way to avoid it."""
    low = " ".join(str(error).lower().split())
    for needle, hint in HINTS:
        if needle in low:
            return f"{error}\nHOW TO FIX: {hint}"
    return error


def make_section_clip(section, seconds, out_dir, ask, render, topic="", portrait=False, accent="#00e5a8", tries=MAX_TRIES, full=False, log=print):
    """Path of a rendered Manim clip for the section, None when every try fails. `ask(prompt)` returns the model's text;
    `render(code, out_dir, portrait)` returns the clip path or raises (it takes `check=False` to skip the picture checks). Each retry is told what
    went wrong, and each failure is logged. When the tries run out and the last scene failed only the picture checks (overlapping text, drawing cut
    off), not a crash, it is rendered once without the checks: an animation with a small flaw is better than none."""
    error, flawed, label = None, None, str(section.get("title", ""))[:40]
    for attempt in range(1, max(1, tries) + 1):
        code = extract_code(ask(manim_prompt(section, seconds, topic, portrait, accent, error, full)))
        problem = code_problem(code)
        if problem:
            error = problem
            log(f"[Log] Animation for '{label}', try {attempt}: {problem[:150]}")
            continue
        try:
            path = render(code, out_dir, portrait)
        except Exception as e:      # Manim errors are long: the end holds the cause
            error = str(e)[-600:]
            flawed = (code, error) if CHECKED in error else None
            log(f"[Log] Animation for '{label}', try {attempt}: {' '.join(error.split())[-170:]}")
            error = with_hint(error)
            continue
        if path and os.path.exists(path):
            return path
        error = "the render produced no file"
        log(f"[Log] Animation for '{label}', try {attempt}: {error}")
    if flawed:
        try:
            path = render(flawed[0], out_dir, portrait, check=False)
            if path and os.path.exists(path):
                log(f"[Warning] The animation for '{label}' is used with a known flaw: {' '.join(flawed[1].split())[-170:]}")
                return path
        except Exception as e:
            log(f"[Log] Animation for '{label}', last try without the checks: {' '.join(str(e).split())[-170:]}")
    return None
