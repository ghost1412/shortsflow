import json
import os
import shutil
import subprocess

import pytest

from engine import case_mermaid as cm
from engine import case_render as cr
from engine import case_study as cs

FLOW = "flowchart LR\n    A[Crafted string sent] --> B{JNDI lookup on?}\n    B -- yes --> C[Contacts attacker LDAP]\n    C --> D[Malicious class loaded]"
SOURCE = "A crafted string is sent. The JNDI lookup contacts the attacker LDAP server and a malicious class is loaded and run."


def test_clean_takes_the_diagram_out_of_a_model_answer():
    assert cm.clean("Here you go:\n```mermaid\nflowchart TD\n A-->B\n```\nEnjoy") == "flowchart TD\n A-->B"
    assert cm.clean("Sure!\nsequenceDiagram\n A->>B: hi") == "sequenceDiagram\n A->>B: hi"
    assert cm.clean("no diagram at all") == "" and cm.clean(None) == ""


def test_orient_sets_the_direction_for_the_shape_and_leaves_other_types_alone():
    assert cm.orient(FLOW, True).splitlines()[0] == "flowchart TB" and cm.orient(FLOW.replace("LR", "TD"), False).splitlines()[0] == "flowchart LR"
    assert cm.orient("graph RL\n A-->B", True).startswith("graph TB")
    state = "stateDiagram-v2\n    direction LR\n    [*] --> A"
    assert "direction TB" in cm.orient(state, True) and "direction LR" in cm.orient(state, False)
    assert "direction TB" in cm.orient("stateDiagram-v2\n    [*] --> A", True)
    mind = "mindmap\n  root((X))\n    A"
    assert cm.orient(mind, True) == mind and cm.orient("sequenceDiagram\n A->>B: hi", True) == "sequenceDiagram\n A->>B: hi"


def test_grounding_holds_numbers_and_inner_names_to_the_sources_but_not_the_first_letter_of_a_label():
    assert cm.unsupported(FLOW, SOURCE) == []
    assert cm.unsupported(FLOW.replace("LDAP", "LDAP on port 389"), SOURCE) == ["389"]
    assert cm.unsupported("flowchart LR\n A[Server hit by Conti] --> B[Done]", SOURCE) == ["Conti"]


def test_check_reads_the_checker_output_and_never_blocks_on_a_missing_checker(tmp_path):
    ok = lambda cmd, data: (0, "OK flowchart-v2")
    bad = lambda cmd, data: (1, "ERROR Parse error on line 4: / Expecting 'SQE'")
    odd = lambda cmd, data: (1, "Cannot find package 'jsdom'")
    node = shutil.which("node") or "node"
    if not (os.path.isfile(cm.CHECKER) and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "mermaid"))):
        pytest.skip("the Remotion project is not installed")
    assert cm.check(FLOW, run=ok, node=node) == (True, "")
    assert cm.check(FLOW, run=bad, node=node) == (False, "Parse error on line 4: / Expecting 'SQE'")
    assert cm.check(FLOW, run=odd, node=node) == (True, "")                      # a checker that itself crashed does not block the video
    assert cm.check("  ", run=ok, node=node)[0] is False
    assert cm.check(FLOW, run=bad, node="") == (True, "")                         # no node: accepted unchecked (the renderer falls back)


def test_the_real_checker_when_node_and_mermaid_are_installed():
    node = shutil.which("node")
    if not (node and os.path.isfile(cm.CHECKER) and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "jsdom"))
            and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "mermaid"))):
        pytest.skip("node or the Remotion packages are missing")
    assert cm.check(FLOW) == (True, "")
    ok, reason = cm.check("flowchart LR\n A[One] --> \n B[Two")
    assert ok is False and "Parse error" in reason
    assert cm.check("sequenceDiagram\n A->>B: hi")[0] and cm.check("mindmap\n  root((X))\n    A")[0]
    assert cm.check("notadiagram\n A --> B")[0] is False


def _script_json(diagram):
    t = cs.load_template("case")
    rows = [{"id": s["id"], "narration": "A sentence about it.", "on_screen": ["Crafted string sent", "Malicious class loaded"], "scene": "diagram" if i == 1 else s["scene"],
             **({"diagram": diagram} if i == 1 else {})} for i, s in enumerate(t)]
    return t, json.dumps({"title": "T", "sections": rows})


def test_a_valid_grounded_diagram_is_kept_on_its_section():
    t, reply = _script_json(FLOW)
    src = [{"id": "S1", "ref": "x", "text": SOURCE}]
    script = cs.write_script("T", t, src, lambda p: reply, check_diagram=lambda c: (True, ""))
    sec = script["sections"][1]
    assert sec["scene"] == "diagram" and sec["diagram"].startswith("flowchart LR")


def test_a_broken_diagram_is_sent_back_once_and_then_fixed_or_replaced_by_a_flow():
    t, reply = _script_json("flowchart LR\n A --> \n B[x")
    src = [{"id": "S1", "ref": "x", "text": SOURCE}]
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return reply if len(asked) == 1 else "```mermaid\n" + FLOW + "\n```"

    def check(code):
        return (code == FLOW, "Parse error on line 2")
    script = cs.write_script("T", t, src, ask, check_diagram=check)
    assert script["sections"][1]["scene"] == "diagram" and script["sections"][1]["diagram"] == FLOW
    assert "Parse error on line 2" in asked[1] and "Fix this Mermaid diagram" in asked[1]

    asked.clear()
    stubborn = cs.write_script("T", t, src, lambda p: (asked.append(p) or reply), check_diagram=lambda c: (False, "still broken"))
    assert stubborn["sections"][1]["scene"] == "flow" and "diagram" not in stubborn["sections"][1]          # the plain row of steps takes over
    assert stubborn["sections"][1]["on_screen"]


def test_a_diagram_with_an_invented_number_is_not_used():
    t, reply = _script_json(FLOW.replace("LDAP", "LDAP port 389"))
    src = [{"id": "S1", "ref": "x", "text": SOURCE}]
    script = cs.write_script("T", t, src, lambda p: reply, check_diagram=lambda c: (True, ""))
    assert script["sections"][1]["scene"] == "flow"


def test_the_prompt_offers_the_diagram_layout_with_its_rules():
    prompt = cs.build_prompt("T", cs.load_template("case"), [])
    assert "diagram:" in prompt and "Mermaid" in prompt and "at most 6 nodes" in prompt and '"diagram"' in prompt
    assert "diagram" in cs.AUTO_LAYOUTS and "diagram" in cs.SCENES


def test_the_diagram_survives_the_review_text_and_is_editable():
    base = {"title": "T", "hook": "", "sources": [], "sections": [
        {"id": "a", "title": "A", "scene": "diagram", "narration": "n", "on_screen": ["One", "Two"], "footage": [], "diagram": FLOW}]}
    text = cs.script_to_text(base)
    assert "DIAGRAM:" in text and "flowchart LR" in text
    back = cs.script_from_text(text, base)
    assert back["sections"][0]["diagram"] == FLOW and back["sections"][0]["on_screen"] == ["One", "Two"]
    edited = cs.script_from_text(text.replace("Malicious class loaded", "Class runs"), base)
    assert "Class runs" in edited["sections"][0]["diagram"]


def test_build_props_hands_the_diagram_to_the_renderer_in_the_direction_of_the_shape():
    script = {"title": "T", "verified": False, "sources": [], "dropped": [], "sections": [
        {"id": "a", "title": "A", "scene": "diagram", "narration": "n", "on_screen": ["One"], "footage": [], "diagram": FLOW}]}
    wide = cr.build_props(script, [(2.0, 12.0)], [[]])
    tall = cr.build_props(script, [(2.0, 12.0)], [[]], portrait=True)
    assert wide["sections"][0]["diagram"].startswith("flowchart LR") and tall["sections"][0]["diagram"].startswith("flowchart TB")


def test_a_diagram_with_too_many_nodes_is_refused_with_the_reason_but_unknown_counts_pass():
    if not (os.path.isfile(cm.CHECKER) and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "mermaid"))):
        pytest.skip("the Remotion project is not installed")
    node = shutil.which("node") or "node"
    ok, why = cm.check(FLOW, run=lambda c, d: (0, "OK flowchart-v2 9"), node=node)
    assert ok is False and "9 nodes" in why and "at most 6" in why
    assert cm.check(FLOW, run=lambda c, d: (0, "OK flowchart-v2 6"), node=node) == (True, "")
    assert cm.check(FLOW, run=lambda c, d: (0, "OK pie 0"), node=node) == (True, "")
    assert cm.check(FLOW, run=lambda c, d: (0, "OK flowchart-v2"), node=node) == (True, "")     # an older checker line without a count


def test_the_real_checker_counts_nodes_when_it_can():
    node = shutil.which("node")
    if not (node and os.path.isfile(cm.CHECKER) and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "jsdom"))
            and os.path.isdir(os.path.join(cm.REMOTION, "node_modules", "mermaid"))):
        pytest.skip("node or the Remotion packages are missing")
    big = "flowchart LR\n" + "\n".join(f"    N{i} --> N{i + 1}" for i in range(8))
    ok, why = cm.check(big)
    assert ok is False and "nodes" in why


def test_a_section_whose_template_default_is_a_diagram_stays_a_diagram_when_the_model_says_flow():
    assert cs.pick_layout("diagram", "flow", "timeline") == "diagram"
    assert cs.pick_layout("diagram", "counters", "timeline") == "counters"                  # a clearly different choice is respected
    assert cs.pick_layout("flow", "flow", "timeline") == "flow" and cs.pick_layout("diagram", "flow", "timeline", layouts="template") == "diagram"


def test_when_the_model_picks_the_layout_but_writes_no_diagram_one_is_asked_for_from_the_narration():
    t = cs.load_template("case")
    rows = [{"id": s["id"], "narration": "A crafted string is sent. The lookup contacts the attacker server.", "on_screen": ["String sent", "Lookup"], "scene": s["scene"] if s["scene"] != "diagram" else "flow"}
            for s in t]                                                                   # the model answers "flow" for the diagram section and gives no code
    reply = json.dumps({"title": "T", "sections": rows})
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return reply if len(asked) == 1 else "```mermaid\n" + FLOW + "\n```"
    src = [{"id": "S1", "ref": "x", "text": SOURCE + " crafted string sent lookup attacker server"}]
    script = cs.write_script("T", t, src, ask, check_diagram=lambda c: (True, ""))
    how = [s for s in script["sections"] if s["id"] == "how"][0]
    assert how["scene"] == "diagram" and how["diagram"] == FLOW
    assert any("Draw ONE Mermaid diagram" in a and "crafted string is sent" in a for a in asked[1:])


def test_clean_unwraps_a_diagram_the_model_put_inside_json():
    wrapped = '{\n  "mermaid": "flowchart LR\\n    A[One] --> B[Two]\\n    B --> C[Three]"\n}'
    assert cm.clean(wrapped) == "flowchart LR\n    A[One] --> B[Two]\n    B --> C[Three]"
    nested = '{"title": "x", "diagram": {"code": "sequenceDiagram\\n A->>B: hi"}}'
    assert cm.clean(nested) == "sequenceDiagram\n A->>B: hi"
    assert cm.clean('"flowchart TD\\n A-->B"') == "flowchart TD\n A-->B"                 # a JSON string
    assert cm.clean('{"scene": "timeline", "title": "x"}') == ""                      # a scene name is not a diagram: a type word alone is refused
    assert cm.clean('{"note": "no diagram in here"}') == "" and cm.clean("[1, 2, 3]") == ""
    assert cm.clean("flowchart TD\n A-->B") == "flowchart TD\n A-->B"                  # plain text is unchanged


def test_a_failed_diagram_says_why_in_the_log(capsys):
    t = cs.load_template("case")
    rows = [{"id": s["id"], "narration": "A sentence.", "on_screen": ["a", "b"], "scene": s["scene"]} for s in t]
    reply = json.dumps({"title": "T", "sections": rows})
    cs.write_script("T", t, [], lambda p: reply, check_diagram=lambda c: (False, "nope"))
    out = capsys.readouterr().out
    assert "[Log] Diagram for" in out and "No usable diagram for" in out and "plain flow" in out
