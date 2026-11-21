"""The options of the case explainer, in ONE place (the schema machinery is engine/mode_options.py).

The command line (`--case KEY=VALUE`, repeatable, and `--case_file FILE.json`), the browser tab and the tests all read this schema, so a new option
is one line in `OPTIONS`: it is parsed, validated, documented (`--case help`) and available to every caller.

    --case theme=neon --case formats=16:9 --case draft --case resume=sessions/case_123
    --case_file my_series.json            # {"theme": "editorial", "formats": "16:9", "background": "images"}
"""
import os

from engine.mode_options import Option, OptionError, OptionSet

THEMES = ("dark", "clean", "warm", "neon", "newsroom", "blueprint", "terminal", "editorial", "midnight")
TEMPLATES = ("case", "postmortem", "history", "explainer", "recipe", "news", "animation")
SHAPES = ("16:9", "9:16", "1:1", "4:5")
BACKGROUND_KINDS = ("footage", "images", "none")
TRANSITIONS = ("number", "fade", "slide", "zoom", "wipe", "cut")


def _formats(raw):
    shapes = [s.strip() for s in raw.split(",") if s.strip()]
    bad = [s for s in shapes if s not in SHAPES]
    if bad or not shapes:
        raise OptionError(f"'formats' takes shapes from: {', '.join(SHAPES)} (got '{raw}').")
    return ",".join(dict.fromkeys(shapes))


def _background(raw):
    if raw in BACKGROUND_KINDS or os.path.isfile(raw.strip('"')):
        return raw.strip('"')
    raise OptionError(f"'background' must be {', '.join(BACKGROUND_KINDS)}, or the path of an existing image or video file (got '{raw}').")


def _avatar(raw):
    from engine import avatars
    try:
        avatars.load(raw, os.getcwd())          # the pipeline runs in the workspace, where saved presenters live
    except ValueError as e:
        raise OptionError(str(e))
    return avatars.slug(raw) or "off"


OPTIONS = (
    Option("template", "text", "case", "the sections of the video: " + ", ".join(TEMPLATES) + ", or the path of a JSON file of {id, title, question, scene}"),
    Option("theme", "choice", "dark", "the whole look", THEMES),
    Option("formats", "text", "16:9,9:16", "video shapes to make, comma separated (" + ", ".join(SHAPES) + ")", check=_formats),
    Option("background", "text", "footage", "what is behind the scenes: footage (stock video), images (stock photos), none (the look's own background), "
           "or the path of your own image or video", check=_background),
    Option("narrator", "choice", "standard", "who speaks the narration: standard (ElevenLabs with credits, else the free Edge voice), or voice_server: the "
           "local voice server (Chatterbox, set up on the Voice-over card) if it is running, each section in its mood and in the presenter's voice; "
           "it uses the GPU while it speaks", ("standard", "voice_server")),
    Option("transition", "choice", "number", "how one section gives way to the next: number (a big section number and title), fade, slide, zoom, wipe "
           "or cut. Try another on an earlier run with resume=FOLDER draft (the script and voice are reused)", TRANSITIONS),
    Option("layouts", "choice", "auto", "who picks the layout of each section: auto (the model, from timeline, flow, counters, checklist, compare, chart, quote) or template (the template's own)", ("auto", "template")),
    Option("llm", "choice", "auto", "the text model: auto (cloud chain, then the model on this PC when the cloud is rate-limited or down), local (this PC only, nothing leaves it), cloud (no local fallback)", ("auto", "local", "cloud")),
    Option("avatar", "text", "off", "a drawn presenter in the corner who talks with the narration: off, a ready-made one (alex, maya, priya, sam, leo, nora, "
           "miso and luna the cats, biscuit the dog, bolt the robot) or one you saved in the app (presenters/NAME.json)", check=_avatar),
    Option("manim", "switch", True, "draw a Manim animation for the explaining sections (manim=off to skip: faster)"),
    Option("draft", "switch", False, "a small, fast render (half size, no new animations) to judge the look and pacing"),
    Option("plan_only", "switch", False, "write the script (script.json) and stop, so it can be edited"),
    Option("resume", "path", "", "redo the render of an earlier run's folder with its saved script, narration and animations"),
)
CASE = OptionSet("case", OPTIONS)

BY_KEY = CASE.by_key
describe, parse, from_args, to_pairs = CASE.describe, CASE.parse, CASE.from_args, CASE.to_pairs
