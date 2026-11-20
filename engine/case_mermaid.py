"""Mermaid diagrams for the case explainer: a section whose scene is `diagram` carries Mermaid source in its `diagram` field.

Mermaid is a general diagram language (flowcharts, sequence diagrams, state machines, mindmaps, timelines, pie charts, ER and class diagrams) that
models write well, and its own layout engine places everything, so a diagram cannot overlap itself whatever the model wrote. The Remotion
"CaseVideo" composition draws it in the colours of the chosen look, scales it to the room, and reveals it step by step.

This module is the Python half:
  clean(text)         the Mermaid source of a model's answer (code fences, stray prose around it removed)
  check(code)         (ok, reason) from Mermaid's own parser, run in Node (remotion-video/scripts/check_mermaid.mjs, needs no browser); the reason is
                      sent back to the model for one retry. When Node or the checker is missing the diagram is accepted unchecked: the renderer then
                      falls back to the section's plain scene if the drawing fails.
  orient(code, tall)  the flowchart / state diagram direction set for the video shape (left to right on a wide frame, top to bottom on a tall one)
  labels(code)        the visible texts of a diagram, to hold them to the same "only what the sources say" rule as every sentence
"""
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion-video")
CHECKER = os.path.join(REMOTION, "scripts", "check_mermaid.mjs")
TYPES = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "mindmap", "timeline", "pie", "classDiagram", "erDiagram",
         "journey", "gantt", "quadrantChart", "gitGraph", "xychart-beta", "sankey-beta", "block-beta")
MAX_CHARS = 1800
MAX_NODES = 6           # more than this and the type is too small to read on a phone


def clean(text):
    """The Mermaid source in a model's answer: the content of a ``` fence when there is one, else the text from the first line that starts a
    known diagram type. Returns '' when none is found."""
    text = str(text or "").strip()
    fence = re.search(r"```(?:mermaid)?[ \t]*\r?\n(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        if re.match(r"\s*(" + "|".join(re.escape(t) for t in TYPES) + r")\b", line):
            return "\n".join(lines[i:]).strip()[:MAX_CHARS]
    return ""


def check(code, run=None, node=None):
    """(ok, reason). `run(cmd, input)` returns (returncode, stdout) and replaces subprocess (tests). Accepts the diagram unchecked (True, "")
    when the checker cannot run."""
    node = shutil.which("node") if node is None else node
    if not code.strip():
        return False, "the diagram is empty"
    if not node or not os.path.isfile(CHECKER) or not os.path.isdir(os.path.join(REMOTION, "node_modules", "mermaid")):
        return True, ""
    if run is None:
        def run(cmd, data):
            res = subprocess.run(cmd, input=data, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=REMOTION, timeout=60)
            return res.returncode, (res.stdout or "").strip()
    try:
        code_, out = run([node, os.path.join("scripts", "check_mermaid.mjs")], code)
    except (OSError, subprocess.SubprocessError):
        return True, ""
    if out.startswith("OK"):
        parts = out.split()
        nodes = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if nodes > MAX_NODES:
            return False, f"it has {nodes} nodes: use at most {MAX_NODES} (merge steps, shorten labels), or the text is too small to read"
        return True, ""
    if out.startswith("ERROR"):
        return False, out[5:].strip()[:400]
    return True, ""             # anything else (jsdom missing, a crash of the checker itself): do not block the video on it


def orient(code, tall):
    """`code` with the flowchart / state diagram direction set for the video shape: TB on a tall frame, LR on a wide one. Other diagram types are
    returned unchanged."""
    want = "TB" if tall else "LR"
    code = re.sub(r"(?m)^(\s*(?:flowchart|graph))\s+(?:LR|RL|TB|TD|BT)\b", lambda m: f"{m.group(1)} {want}", code, count=1)
    if re.match(r"\s*stateDiagram", code):
        if re.search(r"(?m)^\s*direction\s+(?:LR|RL|TB|TD|BT)\b", code):
            code = re.sub(r"(?m)^(\s*)direction\s+(?:LR|RL|TB|TD|BT)\b", lambda m: f"{m.group(1)}direction {want}", code, count=1)
        else:
            code = re.sub(r"(?m)^(\s*stateDiagram(?:-v2)?)\s*$", lambda m: f"{m.group(1)}\n    direction {want}", code, count=1)
    return code


_SYNTAX = re.compile(r"-->|---|-\.->|==>|->>|-->>|--x|-x|\|[^|]*\||\[\*\]|[\[\](){}<>|;:\n]|%%.*")
_KEYWORDS = {"flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "mindmap", "timeline", "pie", "title", "participant", "actor", "as",
             "root", "direction", "subgraph", "end", "section", "note", "over", "left", "right", "of", "loop", "alt", "else", "opt", "par", "and", "rect",
             "LR", "RL", "TB", "TD", "BT", "showData", "classDef", "class", "state"}


def labels(code):
    """The visible texts of a diagram as a list of short phrases (the syntax and the keywords left out)."""
    out = []
    for piece in re.split(r"\s{2,}|\|", _SYNTAX.sub("  ", code)):
        words = [w for w in piece.split() if w not in _KEYWORDS]
        if words:
            out.append(" ".join(words))
    return out


def unsupported(code, source_text):
    """The numbers and the capitalised names inside a diagram that the sources never mention. The first letter of a label does not count as a name
    (labels start with a capital by habit); a number or a name in the middle of a label does."""
    from engine import case_study
    phrases = [p[:1].lower() + p[1:] for p in labels(code)]
    return case_study.unsupported(" ; ".join(phrases), source_text)
