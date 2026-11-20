import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import layout_stress as ls          # noqa: E402

from engine import case_study as cs  # noqa: E402


def test_the_stress_script_covers_every_scene_kind_the_case_video_draws_except_the_special_ones():
    scenes = {s["scene"] for s in ls.stress_script()["sections"]}
    assert scenes == {"timeline", "flow", "counters", "checklist", "compare", "chart", "quote"}
    assert scenes <= set(cs.SCENES)


def test_the_stress_script_is_a_valid_case_script_and_writes_to_a_folder(tmp_path):
    ls.main([str(tmp_path / "s")])
    script = json.loads((tmp_path / "s" / "script.json").read_text(encoding="utf-8"))
    assert script["hook"] and all(len(s["on_screen"]) >= 1 and s["narration"] for s in script["sections"])
    assert max(len(s["on_screen"]) for s in script["sections"]) > cs.MAX_COUNTERS         # worse than anything the script writer would allow
    text = cs.script_to_text(script)
    assert cs.script_from_text(text, script)["sections"][0]["scene"] == "timeline"
