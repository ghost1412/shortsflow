"""ANIMATE mode: a topic in, one continuous animated explanation out.

    python main.py --mode ANIMATE --prompt "How a binary search halves the work" --sources https://example.com/article
    python main.py --mode ANIMATE --prompt "Why the sky is blue" --case theme=blueprint --case formats=16:9

The case explainer cuts a topic into sections with different scenes. This mode is the other style: ONE Manim animation that runs under the whole
narration and builds the idea up piece by piece (boxes, arrows, bars, loops, from the tested kit in engine/manim_kit.py), so it suits equations,
processes and diagrams. It is the case pipeline with the `animation` template, so everything else is the same: the script written from the
sources when you give some (`--sources`), the narrator, captions, music, the nine looks, 16:9 and 9:16, and the options `--case KEY=VALUE`
(`theme`, `formats`, `draft`, `resume`, `plan_only`, `background`, `manim`; `--case help` lists them). The old `--mode EXPLAINER` is unchanged.
"""
import json

MODE = "ANIMATE"     # the --mode value that reaches run() (see shortsflow/_main.py)


def _keys_in_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {str(k).strip().lower() for k in data} if isinstance(data, dict) else set()
    except (OSError, ValueError, TypeError):
        return set()


def defaults_for(pairs, case_file=None):
    """The `--case` pairs of an ANIMATE run: the user's own, with the animation template and no stock picture behind the animation added unless the
    user (on the command line or in the settings file) chose them."""
    pairs = [str(p) for p in (pairs or [])]
    given = {p.split("=", 1)[0].strip().lower() for p in pairs} | (_keys_in_file(case_file) if case_file else set())
    add = []
    if "template" not in given:
        add.append("template=animation")
    if "background" not in given:
        add.append("background=none")
    return add + pairs


def run(args, target_bitrate=None, target_preset=None):
    from engine.modes import case
    args.case = defaults_for(getattr(args, "case", None), getattr(args, "case_file", None))
    case.run(args, target_bitrate, target_preset)
