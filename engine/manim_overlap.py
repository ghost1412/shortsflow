"""Find texts that overlap in a Manim scene, by looking at where Manim puts them (not at pixels).

`overlap_problems(code, workdir)` runs the scene once at a tiny size and a few frames per second with a recorder added: after every `play` and
`wait` the recorder lists the Text objects that are on screen and not faded, and notes every pair whose boxes cover each other. A pair counts
when the shared area is more than 12% of the smaller text, or when one text sits more than half inside another. The answer is a list of plain
sentences naming the texts, ready to be sent back to the model that wrote the scene. If the probe itself cannot run (Manim missing, a crash),
the answer is [] so that a good scene is never blocked by the check.
"""
import json
import os
import subprocess
import sys

# Added right after `from manim import *` in a copy of the scene. It only records; it changes nothing the scene draws.
PRELUDE = '''
import json as _json
import os as _os
from manim import Scene as _Scene, Text as _Text, Rectangle as _Rect

_OVERLAP_OUT = _os.environ.get("MANIM_OVERLAP_OUT")
_OVERLAP_FOUND = {}


def _overlap_box(m):
    return float(m.get_left()[0]), float(m.get_right()[0]), float(m.get_bottom()[1]), float(m.get_top()[1])


def _overlap_visible(m):
    try:
        return m.get_fill_opacity() >= 0.25 or m.get_stroke_opacity() >= 0.25
    except Exception:
        return True


def _overlap_snapshot(scene):
    texts, rects = [], []
    for m in scene.get_mobject_family_members():
        try:
            if isinstance(m, _Text) and str(getattr(m, "text", "")).strip() and _overlap_visible(m):
                shown = str(getattr(m, "original_text", None) or m.text).strip().replace(chr(10), " ")
                texts.append((shown[:40],) + _overlap_box(m))
            elif isinstance(m, _Rect) and _overlap_visible(m):
                box = _overlap_box(m)
                if box[1] - box[0] < 13 and box[3] - box[2] < 7.5:         # not the whole frame
                    rects.append(box)
        except Exception:
            continue
    def inter(a, b):
        w, h = min(a[1], b[1]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[2], b[2])
        return (w * h) if (w > 0 and h > 0) else 0.0
    def inside(a, b, tol=0.06):
        return a[0] >= b[0] - tol and a[1] <= b[1] + tol and a[2] >= b[2] - tol and a[3] <= b[3] + tol
    for i in range(len(texts)):
        ta = texts[i][1:]
        area_a = max(1e-9, (ta[1] - ta[0]) * (ta[3] - ta[2]))
        for j in range(i + 1, len(texts)):
            tb = texts[j][1:]
            area_b = max(1e-9, (tb[1] - tb[0]) * (tb[3] - tb[2]))
            share = inter(ta, tb) / min(area_a, area_b)
            if share > 0.04:
                key = ("text", ) + tuple(sorted((texts[i][0], texts[j][0])))
                _OVERLAP_FOUND[key] = max(share, _OVERLAP_FOUND.get(key, 0))
        for r in rects:                       # a text may sit inside a box, or clear of it; crossing its edge is the fault
            x = inter(ta, r)
            if x / area_a > 0.05 and not inside(ta, r) and not inside(r, ta):
                key = ("box", texts[i][0], "")
                _OVERLAP_FOUND[key] = max(x / area_a, _OVERLAP_FOUND.get(key, 0))
    if _OVERLAP_OUT:
        with open(_OVERLAP_OUT, "w", encoding="utf-8") as f:
            _json.dump([[list(k), round(v, 2)] for k, v in _OVERLAP_FOUND.items()], f)


_overlap_play, _overlap_wait = _Scene.play, _Scene.wait


def _play_recorded(self, *a, **k):
    r = _overlap_play(self, *a, **k)
    _overlap_snapshot(self)
    return r


def _wait_recorded(self, *a, **k):
    r = _overlap_wait(self, *a, **k)
    _overlap_snapshot(self)
    return r


_Scene.play, _Scene.wait = _play_recorded, _wait_recorded
'''


def with_probe(code):
    """`code` with the recorder inserted after its `from manim import *` line (None when that line is missing)."""
    marker = "from manim import *"
    if marker not in code:
        return None
    return code.replace(marker, marker + "\n" + PRELUDE, 1)


def sentences(found):
    """Plain sentences for [[[kind, a, b], share]] findings, worst first, at most three. kind "text": two texts cover each other; "box": a text
    crosses the edge of a box it is not inside."""
    out = []
    for key, share in sorted(found, key=lambda p: -p[1])[:3]:
        kind, a, b = (list(key) + ["", ""])[:3]
        if kind == "box":
            out.append(f"the text \"{a}\" crosses the edge of a box (it is neither inside it nor clear of it); move it clear or into the box")
        else:
            out.append(f"the texts \"{a}\" and \"{b}\" overlap ({int(share * 100)}% of the smaller); move them apart, or show one after the other")
    return out


def overlap_problems(code, workdir, portrait=False, timeout=180):
    """Overlapping texts in the scene `code` (see the module text): a list of sentences, [] when none or when the probe could not run."""
    probe = with_probe(code)
    if probe is None:
        return []
    folder = os.path.join(workdir, "overlap_probe")
    os.makedirs(folder, exist_ok=True)
    script = os.path.join(folder, "scene.py")
    out = os.path.join(folder, "found.json")
    if os.path.exists(out):
        os.remove(out)
    with open(script, "w", encoding="utf-8") as f:
        f.write(probe)
    for name in ("manim_kit.py",):
        kit = os.path.join(workdir, name)
        if os.path.isfile(kit):
            with open(kit, encoding="utf-8") as src, open(os.path.join(folder, name), "w", encoding="utf-8") as dst:
                dst.write(src.read())
    size = "270,340" if portrait else "480,270"
    env = dict(os.environ, MANIM_OVERLAP_OUT=out, PYTHONIOENCODING="utf-8")
    try:
        res = subprocess.run([sys.executable, "-m", "manim", "-ql", "--fps", "4", "-r", size, "--media_dir", os.path.join(folder, "media"), script, "ExplainerScene"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0 or not os.path.isfile(out):
        return []
    try:
        with open(out, encoding="utf-8") as f:
            pairs = json.load(f)
    except (OSError, ValueError):
        return []
    return sentences(pairs)
