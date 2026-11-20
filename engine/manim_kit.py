"""Tested building blocks for the Manim scenes of a case explainer.

The model that writes a scene is told to build it from these (`from manim_kit import *` after `from manim import *`) and add its own motion on
top. Layout, spacing and the frame limits are handled here, so the common failures of free-hand scenes (text outside the frame, boxes
colliding, half the screen empty) do not depend on the model. Every builder returns a VGroup that already fits the frame, and the
`play_*` helpers animate it in order. Text is plain Text() (no LaTeX), and the colours suit a dark picture.

The file is copied next to scene.py before a render (`engine.case_manim.render_scene`), and needs only Manim.
"""
from manim import (Arrow, Create, DOWN, FadeIn, FadeOut, GrowArrow, Indicate, LaggedStart, LEFT, Line, ORIGIN, RIGHT, RoundedRectangle, Scene, Text, Transform,
                   UP, VGroup, config)

import numpy as np

ACCENT = "#00e5a8"
TEXT = "#e8f1ff"
DIM = "#8fa0bd"
FAIL = "#ff5d73"
BLUE = "#3b82f6"
# names a model tends to invent for the same colours: they work instead of crashing the scene
PRIMARY, SECONDARY, SUCCESS = ACCENT, BLUE, ACCENT
MUTED, GRAY, GREY = DIM, DIM, DIM
WARNING, DANGER, ERROR, HIGHLIGHT = FAIL, FAIL, FAIL, ACCENT
FONT = "Segoe UI"
MARGIN = 0.07           # share of the frame kept free on every side


def frame_size():
    """(width, height) of the visible frame in Manim units."""
    return config.frame_width, config.frame_height


def _swap(scene, shown):
    """Fade out whatever an earlier play_* block left on screen, then remember `shown` as the new block, so two blocks never overlap."""
    old = [m for m in getattr(scene, "_kit_shown", []) if m in scene.mobjects]
    if old:
        scene.play(*[FadeOut(m) for m in old], run_time=0.5)
    scene._kit_shown = list(shown)


def fit(group, fill=0.92, grow=2.4):
    """Scale `group` to fill about `fill` of the room inside the frame margins (up to `grow` times larger, so a small diagram is not lost
    in a big frame, and always small enough to fit), and centre it. Returns the group."""
    w, h = frame_size()
    max_w, max_h = w * (1 - 2 * MARGIN) * fill, h * (1 - 2 * MARGIN) * fill
    factor = min(max_w / max(group.width, 1e-6), max_h / max(group.height, 1e-6))
    group.scale(min(factor, grow))
    group.move_to(ORIGIN)
    return group


def label(text, size=30, color=TEXT, max_width=None):
    """A Text that never runs wider than `max_width` (default: 40% of the frame): long text is wrapped on spaces first."""
    if not isinstance(text, (str, int, float)):
        raise TypeError("manim_kit labels must be plain text, not a Manim object (got " + type(text).__name__ + "): pass strings to chain(), box(), label()")
    max_width = max_width or frame_size()[0] * 0.4
    words, lines, line = str(text).split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if line and len(trial) * size * 0.0072 > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    t = Text("\n".join(lines), font=FONT, font_size=size, color=color, line_spacing=0.9)
    if t.width > max_width:
        t.scale(max_width / t.width)
    return t


def box(text, color=ACCENT, size=28, max_width=None, pad=0.28):
    """A rounded box with a label inside. The VGroup is [frame, text]."""
    t = label(text, size, TEXT, max_width)
    frame = RoundedRectangle(corner_radius=0.18, width=t.width + 2 * pad, height=t.height + 2 * pad, stroke_color=color, stroke_width=3,
                             fill_color=color, fill_opacity=0.12)
    t.move_to(frame)
    return VGroup(frame, t)


def chain(labels, colors=None, vertical=None):
    """Boxes joined by arrows, in order. Horizontal on a wide frame, vertical on a tall one (`vertical` forces it).
    Returns VGroup(boxes VGroup, arrows VGroup); use `play_chain`."""
    w, h = frame_size()
    vertical = (h > w) if vertical is None else vertical
    n = len(labels)
    colors = colors or [ACCENT] * n
    room = w * (1 - 2 * MARGIN)
    snake = (not vertical) and n >= 4              # a wide frame with 4+ steps: two rows (second one runs back), so the boxes and text stay big
    per_row = -(-n // 2) if snake else n
    each = (w * 0.78) if vertical else (room - (per_row - 1) * 0.9) / max(1, per_row)
    longest = max((len(str(t)) for t in labels), default=1)
    size = 30 if longest <= 18 and n <= 3 else 28 if snake and longest <= 30 else 26 if longest <= 30 else 22
    boxes = VGroup(*[box(t, colors[i % len(colors)], size=size, max_width=max(1.6, each - 0.6)) for i, t in enumerate(labels)])
    if snake:
        top = VGroup(*boxes[:per_row]).arrange(RIGHT, buff=0.9)
        bottom = VGroup(*boxes[per_row:][::-1]).arrange(RIGHT, buff=0.9)       # reversed: step per_row+1 sits under step per_row
        bottom.next_to(top, DOWN, buff=1.0)
        bottom.align_to(top, RIGHT)
        bottom.shift(RIGHT * (boxes[per_row - 1].get_center()[0] - boxes[per_row].get_center()[0]))     # a straight arrow between the rows
        arrows = VGroup()
        for i in range(n - 1):
            a, b = boxes[i], boxes[i + 1]
            if i < per_row - 1:
                start, end = a.get_edge_center(RIGHT), b.get_edge_center(LEFT)
            elif i == per_row - 1:
                start, end = a.get_edge_center(DOWN), b.get_edge_center(UP)
            else:
                start, end = a.get_edge_center(LEFT), b.get_edge_center(RIGHT)
            arrows.add(Arrow(start, end, buff=0.08, color=DIM, stroke_width=4, max_tip_length_to_length_ratio=0.25))
        group = fit(VGroup(boxes, arrows))
        group.parts = list(boxes)
        return group
    boxes.arrange(DOWN if vertical else RIGHT, buff=0.7)
    arrows = VGroup(*[Arrow(boxes[i].get_edge_center(DOWN if vertical else RIGHT), boxes[i + 1].get_edge_center(UP if vertical else LEFT), buff=0.08,
                            color=DIM, stroke_width=4, max_tip_length_to_length_ratio=0.25) for i in range(n - 1)])
    group = fit(VGroup(boxes, arrows))
    group.parts = list(boxes)
    return group


def play_chain(scene, chain_group, run_time=1.0, wait=0.4):
    """Show a chain one box at a time with its arrow."""
    boxes, arrows = chain_group[0], chain_group[1]
    _swap(scene, list(boxes) + list(arrows))
    for i, b in enumerate(boxes):
        anims = [FadeIn(b, shift=UP * 0.2)]
        if i > 0:
            anims.insert(0, GrowArrow(arrows[i - 1]))
        scene.play(*anims, run_time=run_time)
        scene.wait(wait)


def highlight_each(scene, mobjects, run_time=0.8, color=ACCENT):
    """Pulse each of `mobjects` in turn (a way to keep a diagram moving while the narrator talks about its parts)."""
    for m in (getattr(mobjects, "parts", None) or list(mobjects)):
        scene.play(Indicate(m, color=color, scale_factor=1.08), run_time=run_time)


def branch(root_text, child_texts, root_color=ACCENT, child_color=BLUE):
    """One root box on top and its children below, each joined by a line. Returns VGroup(root, children VGroup, lines VGroup)."""
    root = box(root_text, root_color, size=32)
    kids = VGroup(*[box(t, child_color, size=26, max_width=frame_size()[0] * 0.8 / max(1, len(child_texts))) for t in child_texts]).arrange(RIGHT, buff=0.5)
    VGroup(root, kids).arrange(DOWN, buff=1.1)
    lines = VGroup(*[Line(root.get_bottom(), k.get_top(), color=DIM, stroke_width=3) for k in kids])
    group = fit(VGroup(root, kids, lines))
    group.parts = [root] + list(kids)
    return group


def play_branch(scene, branch_group, run_time=0.9):
    root, kids, lines = branch_group
    _swap(scene, [root] + list(kids) + list(lines))
    scene.play(FadeIn(root, shift=DOWN * 0.2), run_time=run_time)
    scene.play(LaggedStart(*[Create(l) for l in lines], lag_ratio=0.25), LaggedStart(*[FadeIn(k, shift=DOWN * 0.2) for k in kids], lag_ratio=0.25),
               run_time=run_time * 1.6)


def cycle(labels, radius=None, color=ACCENT):
    """Labels on a ring with arrows between neighbours (a loop). Returns VGroup(nodes VGroup, arrows VGroup)."""
    w, h = frame_size()
    radius = radius or min(w, h) * 0.3
    n = len(labels)
    wide = w > h * 1.5                                    # a wide, short frame: the ring is an ellipse that uses the width, or the boxes touch
    rx, ry = (w * 0.30, h * 0.30) if wide else (radius * 1.25, radius)
    nodes = VGroup(*[box(t, color, size=24, max_width=(rx * 0.7 if wide else radius * 0.9)) for t in labels])
    for i, node in enumerate(nodes):
        angle = np.pi / 2 - 2 * np.pi * i / n
        node.move_to(np.array([np.cos(angle) * rx, np.sin(angle) * ry, 0]))
    def edge_arrow(a, b):
        """An arrow from the border of box a to the border of box b (not centre to centre, which runs through the labels)."""
        d = b.get_center() - a.get_center()
        norm = float(np.linalg.norm(d)) or 1.0
        unit = d / norm
        start = a[0].get_boundary_point(unit) + unit * 0.08
        end = b[0].get_boundary_point(-unit) - unit * 0.08
        return Arrow(start, end, buff=0, color=DIM, stroke_width=4, max_tip_length_to_length_ratio=0.25)
    arrows = VGroup(*[edge_arrow(nodes[i], nodes[(i + 1) % n]) for i in range(n)])
    group = fit(VGroup(nodes, arrows))
    group.parts = list(nodes)
    return group


def play_cycle(scene, cycle_group, run_time=0.7):
    nodes, arrows = cycle_group
    _swap(scene, list(nodes) + list(arrows))
    for i, node in enumerate(nodes):
        scene.play(FadeIn(node, scale=0.8), run_time=run_time)
        scene.play(GrowArrow(arrows[i]), run_time=run_time * 0.6)


def before_after(before_text, after_text, before_color=FAIL, after_color=ACCENT):
    """Two panels side by side (or stacked on a tall frame) with an arrow between: how something was, and how it ended up."""
    w, h = frame_size()
    a, b = box(before_text, before_color, size=30), box(after_text, after_color, size=30)
    VGroup(a, b).arrange(DOWN if h > w else RIGHT, buff=1.4)
    arrow = Arrow(a.get_edge_center(DOWN if h > w else RIGHT), b.get_edge_center(UP if h > w else LEFT), buff=0.1, color=DIM, stroke_width=5)
    group = fit(VGroup(a, b, arrow))
    group.parts = [a, b]
    return group


def play_before_after(scene, group, run_time=1.0):
    a, b, arrow = group
    _swap(scene, [a, b, arrow])
    scene.play(FadeIn(a, shift=RIGHT * 0.2), run_time=run_time)
    scene.play(GrowArrow(arrow), run_time=run_time * 0.6)
    scene.play(FadeIn(b, shift=RIGHT * 0.2), run_time=run_time)


def bar(caption, fraction, color=ACCENT, width=None):
    """A horizontal bar with a caption above it, filled to `fraction` (0 to 1). Returns VGroup(track, fill, caption); `play_bar` fills it."""
    width = width or frame_size()[0] * 0.6
    track = RoundedRectangle(corner_radius=0.15, width=width, height=0.5, stroke_color=DIM, stroke_width=3, fill_opacity=0)
    fill = RoundedRectangle(corner_radius=0.15, width=max(0.05, width * max(0.0, min(1.0, fraction))), height=0.5, stroke_width=0, fill_color=color, fill_opacity=0.9)
    fill.align_to(track, LEFT)
    cap = label(caption, 30, TEXT, width)
    cap.next_to(track, UP, buff=0.3)
    return fit(VGroup(track, fill, cap))


def play_bar(scene, bar_group, run_time=1.6):
    track, fill, cap = bar_group
    _swap(scene, [track, fill, cap])
    target = fill.copy()
    fill.stretch_to_fit_width(0.01)
    fill.align_to(track, LEFT)
    scene.play(FadeIn(track), FadeIn(cap), run_time=0.5)
    scene.play(Transform(fill, target), run_time=run_time)


def callout(text, target, color=ACCENT, direction=UP):
    """A small label with a line to `target` (a mobject already on screen), placed on the side of `direction`."""
    t = label(text, 24, color, frame_size()[0] * 0.3)
    t.next_to(target, direction, buff=0.6)
    line = Line(t.get_edge_center(-direction), target.get_edge_center(direction), color=color, stroke_width=2.5)
    return VGroup(t, line)


# A model often writes self.play_chain(group) instead of play_chain(self, group): both work.
for _name in ("play_chain", "play_branch", "play_cycle", "play_before_after", "play_bar", "highlight_each"):
    setattr(Scene, _name, globals()[_name])
