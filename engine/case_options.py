"""The options of the case explainer, in ONE place (the schema machinery is engine/mode_options.py).

The command line (`--case KEY=VALUE`, repeatable, and `--case_file FILE.json`), the browser tab and the tests all read this schema, so a new option
is one line in `OPTIONS`: it is parsed, validated, documented (`--case help`) and available to every caller.

    --case theme=neon --case formats=16:9 --case draft --case resume=sessions/case_123
    --case_file my_series.json            # {"theme": "editorial", "formats": "16:9", "background": "images"}
"""
import os

from engine.mode_options import Option, OptionError, OptionSet

THEMES = ("dark", "clean", "warm", "neon", "newsroom", "blueprint", "terminal", "editorial", "midnight")
TEMPLATES = ("case", "postmortem", "history", "explainer", "recipe", "news", "animation", "story")
SHAPES = ("16:9", "9:16", "1:1", "4:5")
BACKGROUND_KINDS = ("footage", "images", "cartoon", "none")
CARTOON_SOURCES = ("auto", "local", "cloud", "drawn")
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


def _cartoon(raw):
    """auto, off, or an ordered list of ways (local, cloud, drawn): a way left out is never used."""
    raw = raw.strip().lower()
    if raw in ("auto", "off"):
        return raw
    ways = [w.strip() for w in raw.split(",") if w.strip()]
    if not ways or any(w not in CARTOON_SOURCES[1:] for w in ways):
        raise OptionError(f"'cartoon' must be auto, off, or ways in the order to try, comma separated, from: {', '.join(CARTOON_SOURCES[1:])} (got '{raw}').")
    return ",".join(dict.fromkeys(ways))


def _voice_sample(raw):
    path = os.path.expanduser(raw.strip().strip('"'))
    if path and not os.path.isfile(path):
        raise OptionError(f"'voice_sample' must be an existing recording (.wav or .mp3, 10-30 seconds of one voice); not found: {path}")
    return path


def _avatar(raw):
    from engine import avatars
    try:
        avatars.load(raw, os.getcwd())          # the pipeline runs in the workspace, where saved presenters live
    except ValueError as e:
        raise OptionError(str(e))
    return avatars.slug(raw) or "off"


OPTIONS = (
    Option("template", "text", "case", "the sections of the video: " + ", ".join(TEMPLATES) + " (story is a preview, still rough), or the path of a JSON file of {id, title, question, scene}"),
    Option("theme", "choice", "dark", "the whole look", THEMES),
    Option("formats", "text", "16:9,9:16", "video shapes to make, comma separated (" + ", ".join(SHAPES) + ")", check=_formats),
    Option("background", "text", "footage", "what is behind the scenes: footage (stock video), images (stock photos), cartoon (an illustration per beat, see cartoon=), none (the look's own background), "
           "or the path of your own image or video", check=_background),
    Option("cartoon", "text", "auto", "with background=cartoon, who draws the pictures: auto (the picture add-on on this PC if installed, else Gemini or "
           "Hugging Face with your keys, else the text model drawing simple SVG scenes), one or more of local (the add-on: private), cloud (only the beat's "
           "two-to-four word phrase is sent) and drawn (SVG by the text model: no download, no GPU) in the order to try, e.g. local,drawn to never use the "
           "cloud, or off for no pictures (the look's own background)", check=_cartoon),
    Option("narrator", "choice", "standard", "who speaks the narration: standard (ElevenLabs with credits, else the free Edge voice), or voice_server: the "
           "local voice server (Chatterbox, installed on the Voice-over card; started for the narration and stopped after it), each section in its mood and in the presenter's voice; "
           "it uses the GPU while it speaks; or gemini: a storyteller who acts the story, online (the narration text goes to Google with your "
           "GEMINI_API_KEY; a preview with a small free quota; if it cannot finish, the whole video uses the standard voice)", ("standard", "voice_server", "gemini")),
    Option("gemini_voice", "text", "Algieba", "with narrator=gemini: the storyteller's voice, Algieba (a grandfather, the default) or Sulafat (a grandmother); other Google prebuilt voice names work too"),
    Option("voice_sample", "path", "", "with narrator=voice_server: a recording of the voice to copy instead of the presenter's (yours, or someone "
           "who agreed; .wav or .mp3, 10-30 seconds of clean speech). It stays on this PC", check=_voice_sample),
    Option("transition", "choice", "number", "how one section gives way to the next: number (a big section number and title), fade, slide, zoom, wipe "
           "or cut. Try another on an earlier run with resume=FOLDER draft (the script and voice are reused)", TRANSITIONS),
    Option("layouts", "choice", "auto", "who picks the layout of each section: auto (the model, from timeline, flow, counters, checklist, compare, chart, quote) or template (the template's own)", ("auto", "template")),
    Option("llm", "choice", "auto", "the text model: auto (cloud chain, then the model on this PC when the cloud is rate-limited or down), local (this PC only, nothing leaves it), cloud (no local fallback)", ("auto", "local", "cloud")),
    Option("avatar", "text", "off", "a drawn presenter in the corner who talks with the narration: off, a ready-made one (alex, maya, priya, sam, leo, nora, "
           "miso and luna the cats, biscuit the dog, bolt the robot) or one you saved in the app (presenters/NAME.json)", check=_avatar),
    Option("length", "choice", "standard", "how long the video runs: short (2-3 spoken sentences per section, about 45 seconds), standard (4-6, about 80 seconds) "
           "or long (6-8, about 110 seconds)", ("short", "standard", "long")),
    Option("manim", "switch", True, "draw a Manim animation for the explaining sections (manim=off to skip: faster)"),
    Option("draft", "switch", False, "a small, fast render (half size, no new animations) to judge the look and pacing"),
    Option("plan_only", "switch", False, "write the script (script.json) and stop, so it can be edited"),
    Option("resume", "path", "", "redo the render of an earlier run's folder with its saved script, narration and animations"),
)
CASE = OptionSet("case", OPTIONS)

BY_KEY = CASE.by_key
describe, parse, from_args, to_pairs = CASE.describe, CASE.parse, CASE.from_args, CASE.to_pairs
