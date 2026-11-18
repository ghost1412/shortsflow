"""The options of the case explainer, in ONE place.

The command line (`--case KEY=VALUE`, repeatable), the browser tab, a settings file and the tests all read this schema, so a new option is one
line in `OPTIONS` and nothing else: it is parsed, validated, documented (`--case help`) and available to every caller.

    --case theme=neon --case formats=16:9 --case draft --case resume=sessions/case_123
    --case_file my_series.json            # {"theme": "editorial", "formats": "16:9", "background": "images"}

A bare KEY means true for a switch (`draft`). Unknown keys and bad values are refused with the list of what is allowed.
"""
import json
import os
from dataclasses import dataclass

THEMES = ("dark", "clean", "warm", "neon", "newsroom", "blueprint", "terminal", "editorial", "midnight")
TEMPLATES = ("case", "postmortem", "history", "explainer")
SHAPES = ("16:9", "9:16", "1:1", "4:5")
BACKGROUND_KINDS = ("footage", "images", "none")


@dataclass(frozen=True)
class Option:
    key: str
    kind: str                     # "text", "choice", "switch", "path"
    default: object
    help: str
    choices: tuple = ()


OPTIONS = (
    Option("template", "text", "case", "the sections of the video: " + ", ".join(TEMPLATES) + ", or the path of a JSON file of {id, title, question, scene}"),
    Option("theme", "choice", "dark", "the whole look", THEMES),
    Option("formats", "text", "16:9,9:16", "video shapes to make, comma separated (" + ", ".join(SHAPES) + ")"),
    Option("background", "text", "footage", "what is behind the scenes: footage (stock video), images (stock photos), none (the look's own background), or the path of your own image or video"),
    Option("manim", "switch", True, "draw a Manim animation for the explaining sections (manim=off to skip: faster)"),
    Option("draft", "switch", False, "a small, fast render (half size, no new animations) to judge the look and pacing"),
    Option("plan_only", "switch", False, "write the script (script.json) and stop, so it can be edited"),
    Option("resume", "path", "", "redo the render of an earlier run's folder with its saved script, narration and animations"),
)
BY_KEY = {o.key: o for o in OPTIONS}
_TRUE, _FALSE = ("", "1", "true", "yes", "on"), ("0", "false", "no", "off")


class OptionError(ValueError):
    """A bad key or value: the message says what is allowed."""


def describe():
    """The options as plain help text (one line each)."""
    lines = ["CASE options (use --case KEY=VALUE, repeatable; a bare switch means on):"]
    for o in OPTIONS:
        shown = o.default if o.kind != "switch" else ("on" if o.default else "off")
        extra = f" [{' | '.join(o.choices)}]" if o.choices else ""
        lines.append(f"  {o.key:<11} {o.help}{extra} (default: {shown or '-'})")
    return "\n".join(lines)


def _value(option, raw):
    raw = str(raw).strip()
    if option.kind == "switch":
        low = raw.lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise OptionError(f"'{option.key}' is a switch: use {option.key}, {option.key}=on or {option.key}=off (got '{raw}').")
    if option.kind == "choice" and raw not in option.choices:
        raise OptionError(f"'{option.key}' must be one of: {', '.join(option.choices)} (got '{raw}').")
    if option.key == "formats":
        shapes = [s.strip() for s in raw.split(",") if s.strip()]
        bad = [s for s in shapes if s not in SHAPES]
        if bad or not shapes:
            raise OptionError(f"'formats' takes shapes from: {', '.join(SHAPES)} (got '{raw}').")
        return ",".join(dict.fromkeys(shapes))
    if option.key == "background" and raw not in BACKGROUND_KINDS and not os.path.isfile(raw.strip('"')):
        raise OptionError(f"'background' must be {', '.join(BACKGROUND_KINDS)}, or the path of an existing image or video file (got '{raw}').")
    return raw.strip('"') if option.kind == "path" else raw


def parse(pairs=None, file=None):
    """The options as a dict with every key set. `pairs` are "key=value" strings (later ones win); `file` is a JSON object read first.
    Raises OptionError for an unknown key or a bad value."""
    values = {o.key: o.default for o in OPTIONS}
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise OptionError(f"The settings file could not be read: {e}")
        if not isinstance(data, dict):
            raise OptionError("The settings file must hold one JSON object of option names and values.")
        pairs_from_file = [(k, "on" if v is True else "off" if v is False else v) for k, v in data.items()]
    else:
        pairs_from_file = []
    items = pairs_from_file + [tuple((str(p).split("=", 1) + [""])[:2]) for p in (pairs or [])]
    for key, raw in items:
        key = str(key).strip().lower()
        if key == "help":
            raise OptionError(describe())
        option = BY_KEY.get(key)
        if option is None:
            raise OptionError(f"Unknown CASE option '{key}'. Known: {', '.join(BY_KEY)}.")
        values[key] = _value(option, raw)
    return values


def from_args(args):
    """The options of a parsed command line (`--case` pairs and `--case_file`)."""
    return parse(getattr(args, "case", None), getattr(args, "case_file", None))


def to_pairs(values):
    """The `--case KEY=VALUE` strings that give `values` back (only what differs from the defaults), for building a command line."""
    out = []
    for o in OPTIONS:
        v = values.get(o.key, o.default)
        if v == o.default or v in (None, ""):
            continue
        out.append(o.key if (o.kind == "switch" and v is True) else f"{o.key}={'off' if v is False else v}")
    return out
