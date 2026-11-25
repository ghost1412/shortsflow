"""`--help` is grouped: every flag sits in exactly one titled group, none in a catch-all."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "shortsflow" / "_main.py"


_KEEP = []


def _parser():
    """The parser, built from the part of _main.py above `args = parse_args()` (importing it would run the pipeline)."""
    src = MAIN.read_text(encoding="utf-8")
    ns = {"__name__": "shortsflow_main_parser_only"}
    streams = sys.stdout, sys.stderr                     # the module re-wraps them for UTF-8 on Windows
    try:
        exec(compile(src.split("\nargs = parse_args()")[0], str(MAIN), "exec"), ns)
    finally:
        ns["_wrappers"] = sys.stdout, sys.stderr         # kept alive: a collected wrapper would close the real stream
        sys.stdout, sys.stderr = streams
    _KEEP.append(ns)
    return ns["build_parser"](), ns["FLAG_GROUPS"]


def test_every_flag_is_in_exactly_one_titled_group():
    parser, flag_groups = _parser()
    titles = {t for t, _d, _f in flag_groups}
    assert all(d for _t, d, _f in flag_groups), "each group needs a description"
    seen = {}
    for group in parser._action_groups:
        for action in group._group_actions:
            if not action.option_strings or action.help is argparse.SUPPRESS:
                continue
            key = action.option_strings[0]
            assert key not in seen, f"{key} is in two groups"
            seen[key] = group.title
    assert seen["--mode"] == "Source and mode"
    for key, title in seen.items():
        if key in ("-h",):
            continue
        assert title in titles, f"{key} is in '{title}', not one of the named groups (add it to FLAG_GROUPS)"
    listed = [f for _t, _d, flags in flag_groups for f in flags.split()]
    assert len(listed) == len(set(listed)), "a flag is listed in two groups"
    defined = {a.option_strings[0] for a in parser._actions if a.option_strings}
    assert set(listed) <= defined, f"listed but not defined: {set(listed) - defined}"


def test_help_runs_and_shows_every_group_title_and_examples():
    out = subprocess.run([sys.executable, str(ROOT / "main.py"), "--help"], capture_output=True, text=True,
                         encoding="utf-8", cwd=str(ROOT), timeout=120)
    assert out.returncode == 0, out.stderr
    _parser_obj, flag_groups = _parser()
    for title, _d, _f in flag_groups:
        assert title in out.stdout, title
    assert "examples:" in out.stdout and "--mode CASE" in out.stdout
    assert "Other options" not in out.stdout


def test_shortsflow_command_gives_the_same_grouped_help(monkeypatch, capsys):
    from shortsflow import cli
    monkeypatch.setattr(sys, "argv", ["shortsflow"])
    import runpy
    seen = {}
    monkeypatch.setattr(runpy, "run_module", lambda name, run_name=None: seen.update(name=name))
    cli.main(["run", "--help"])
    assert seen["name"] == "shortsflow._main" and sys.argv[1:] == ["--help"]


def test_main_runs_past_the_option_handling_for_a_real_invocation():
    """`main.py` must get past the code that runs after the parser is built (it once died with NameError there after the parser was split into build_parser())."""
    here = str(Path(__file__).resolve().parent.parent)
    done = subprocess.run([sys.executable, str(Path(here) / "main.py"), "--mode", "VOICEOVER", "--voiceover", "help"], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0 and "NameError" not in done.stderr and "voice" in done.stdout.lower()
