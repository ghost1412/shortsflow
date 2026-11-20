"""Write a script that breaks every case-video layout on purpose, to check a layout change against content far worse than a real video's.

    python scripts/layout_stress.py sessions/stress_layout
    python main.py --mode CASE --case resume=sessions/stress_layout --case draft --case manim=off --case background=none --case formats=16:9,9:16

Every scene kind gets as many labels as the layouts allow, each one long enough to wrap onto three lines, and every section's narration is long
enough for two-line captions. Then look at the draft frames near the end of each section: nothing may touch the heading, the caption bar, or
another label. (Real scripts are held to far fewer and shorter labels; this is the worst case.)
"""
import json
import os
import sys

LONG = "A deliberately long label that wraps over two or even three lines"
NARRATION = ("This section exists to stress the layout with far more text than a normal section would ever carry on its screen. "
             "The narrator keeps talking so that every label has time to appear and every caption wraps onto two lines at the bottom. "
             "Antidisestablishmentarianism and other extraordinarily lengthy words make the caption box as wide as it can possibly get.")


def stress_sections():
    """[(id, title, scene, labels)] with the worst-case labels for every scene kind the case video draws."""
    return [
        ("tl", "Timeline stress", "timeline", [f"{2010 + i}: {LONG}" for i in range(6)]),
        ("fl", "Flow stress", "flow", [f"{i + 1}. {LONG}" for i in range(6)]),
        ("ct", "Counters stress", "counters", [f"{(i + 1) * 1234}% {LONG}" for i in range(6)]),
        ("ck", "Checklist stress", "checklist", [f"{LONG} number {i + 1}" for i in range(6)]),
        ("cp", "Compare stress", "compare", ["Before the change | After the change"] + [f"{LONG} {i + 1} | {LONG} {i + 1}" for i in range(4)]),
        ("ch", "Chart stress", "chart", [f"{LONG[:30]} {i + 1}: {(i + 1) * 17}" for i in range(5)]),
        ("qt", "Quote stress", "quote", ["A very long quote line that keeps going and going so that it wraps onto many lines on the screen and tests the quote layout properly"]),
    ]


def stress_script():
    return {"title": "Layout stress test with a rather long title that wraps", "hook": "Every scene gets far more text than it can comfortably hold",
            "verified": False, "sources": [], "dropped": [],
            "sections": [{"id": i, "title": t, "scene": sc, "narration": NARRATION, "on_screen": labels, "cites": [], "footage": []}
                         for i, t, sc, labels in stress_sections()]}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    folder = argv[0] if argv else os.path.join("sessions", "stress_layout")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "script.json"), "w", encoding="utf-8") as f:
        json.dump(stress_script(), f, indent=1, ensure_ascii=False)
    print(f"Wrote {os.path.join(folder, 'script.json')}. Render it with:\n"
          f"  python main.py --mode CASE --case resume={folder} --case draft --case manim=off --case background=none --case formats=16:9,9:16")


if __name__ == "__main__":
    main()
