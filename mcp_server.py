#!/usr/bin/env python3
"""
ShortsFlow AI Studio - Model Context Protocol (MCP) Server
Allows AI Agents (Claude Desktop, Cursor, Antigravity, n8n, AutoGPT, etc.)
to trigger AI Shorts generation, clipping, and social metadata creation autonomously over stdio.
"""

import contextlib
import sys
import os
import json
import re
import subprocess
import threading
import time
import uuid
from typing import Dict, Any
from urllib.parse import urlparse

try:
    from engine import proc as _no_console
    _no_console.install()        # the runs this server starts open no console window (Windows)
except ImportError:              # the slim MCP image has no engine package
    pass

# Ensure stdout uses UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Active jobs tracking
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
# AI tools start this server from any working directory, so find main.py (and run it) relative to this file, not to the caller
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _server_version():
    """The ShortsFlow version (so the MCP handshake does not report a stale number)."""
    try:
        import re
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shortsflow", "__init__.py"), encoding="utf-8") as f:
            return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    except Exception:
        return "0.2.0"

CONTENT_MODES = ["FACTS", "EXPLAINER", "STORY", "WYR", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC",
                 "EMOJI_GUESS", "REDDIT", "TRIVIA", "QUOTE", "NEWS", "RIDDLE"]
CAPTION_STYLES = ["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR", "MARKER", "SOFT", "WORDCUT", "NEGATIVE",
                  "HANDWRITTEN", "SIMPLE", "TYPEWRITER", "AUTO", "RANDOM"]
TTS_PROVIDERS = ["auto", "edgetts", "elevenlabs", "voicestudio", "local", "kokoro"]
ASPECT_RATIOS = ["9:16", "16:9", "1:1", "4:5"]
SFX_PRESETS = ["auto", "whoosh", "pop", "riser", "boom", "none"]
VIBES = ["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"]
# The explainer, dub and publish tools. These mirror engine/case_options.py, the --target_lang help and engine/publish.py (a test pins them);
# they are copied here because the minimal container (Dockerfile.mcp) has no engine/ folder.
EXPLAINER_KINDS = ["case", "animate"]
EXPLAINER_TEMPLATES = ["case", "postmortem", "history", "explainer", "recipe", "news", "animation", "story"]
EXPLAINER_THEMES = ["dark", "clean", "warm", "neon", "newsroom", "blueprint", "terminal", "editorial", "midnight"]
DUB_LANGUAGES = ["es", "hi", "de", "fr", "ja", "pt", "zh", "it", "ru", "ko", "ar", "en", "tr", "nl", "pl", "uk", "id"]
VIDEO_SHAPES = ["all", "tall", "wide", "square"]
PUBLISH_PLATFORMS = ["tiktok", "instagram", "youtube", "facebook", "linkedin", "x", "threads", "pinterest", "youtube_direct"]
PRIVACY = ["private", "unlisted", "public"]

TOPIC_MODES = ["ARTICLE", "UGC", "BIBLE", "TRUE_CRIME"]          # engine/modes/generate.py refuses these without a topic
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".m4v")

_CAPTION_HELP = ("Animated caption look (needs use_remotion): HORMOZI = bold yellow single words, GLOW_BOX = words in boxes with a "
                 "pink highlight, BOUNCE = bouncy gold single words, MINIMAL = clean dark boxes, KARAOKE = colour sweep along the line, "
                 "NEON = glow, BAR = subtitle bar, MARKER = highlighter sweep, SOFT = words fading in, WORDCUT = words cut in, NEGATIVE = "
                 "muted keyword, HANDWRITTEN = script with an underline, SIMPLE = tall plain capitals, TYPEWRITER = typed letter by letter, "
                 "AUTO/RANDOM = pick for me.")


def _hints(title, read_only=False, destructive=False, repeatable=False, online=True):
    """MCP tool annotations: how an AI client may treat the tool (hints only, they enforce nothing)."""
    return {"title": title, "readOnlyHint": read_only, "destructiveHint": destructive, "idempotentHint": repeatable, "openWorldHint": online}


TOOLS_DEFINITIONS = [
    {
        "name": "generate_short",
        "description": (
            "Create an original vertical (9:16) short video from an idea: an AI-written script, voice-over, stock footage, background "
            "music and captions, rendered on this computer. Use it to make a new short from a topic; use extract_clips to cut shorts "
            "out of an existing video, or create_explainer when the script must be based on given sources. "
            "Returns {job_id, status, message} at once and works in the background, usually for a few minutes; poll get_render_status "
            "with the job_id until 'completed' or 'failed'. The finished file is written to the ShortsFlow folder and named in the "
            "job's last log lines (this job has no 'outputs' list). Side effects: the topic goes to the configured AI "
            "text provider, search phrases to Pexels and the narration to the voice service, using the user's own keys; nothing is "
            "uploaded or posted."),
        "annotations": _hints("Generate a short from a topic"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string", "enum": CONTENT_MODES, "default": "FACTS",
                    "description": ("Content format. FACTS = a 'spot the lie' quiz of three claims; STORY / HORROR / TRUE_CRIME / BIBLE = "
                                    "narrated stories; EXPLAINER = a short Manim animation; WYR = 'would you rather'; TOP_5 = a ranked "
                                    "list; CHAT_STORY = a text-message story; REDDIT = a Reddit-style post; TRIVIA / RIDDLE / EMOJI_GUESS "
                                    "= quizzes; QUOTE = a quote; NEWS = a news recap; ARTICLE = an article retold; UGC = a product review. "
                                    "ARTICLE, UGC, BIBLE and TRUE_CRIME need 'prompt' or 'category'.")},
                "category": {
                    "type": "string",
                    "description": ("Topic area of the script, e.g. 'space mysteries', 'ancient Rome', 'psychology'. Left out, a random "
                                    "area that suits the mode is picked.")},
                "prompt": {
                    "type": "string",
                    "description": ("The exact topic or idea, e.g. 'Explain how black holes bend light'. When given it is the topic "
                                    "instead of 'category'.")},
                "script": {
                    "type": "string",
                    "description": "A finished script to narrate as written. When given, no AI script is generated."},
                "vibe": {"type": "string", "enum": VIBES, "default": "suspense", "description": "Mood of the background music."},
                "use_remotion": {
                    "type": "boolean", "default": True,
                    "description": "Render animated captions with the Remotion engine (needs Node.js). False uses simple captions."},
                "caption_style": {"type": "string", "enum": CAPTION_STYLES, "default": "HORMOZI", "description": _CAPTION_HELP},
                "tts_provider": {
                    "type": "string", "enum": TTS_PROVIDERS, "default": "auto",
                    "description": ("Voice-over engine. auto picks the best available; edgetts is free; kokoro and local run fully "
                                    "offline; elevenlabs and voicestudio need their own setup.")},
                "aspect_ratio": {"type": "string", "enum": ASPECT_RATIOS, "default": "9:16",
                                 "description": ("Output shape. Only 9:16 has an effect here: shorts made from an idea are always 9:16, "
                                                 "other values are accepted and ignored with a warning in the job log.")},
                "auto_ducking": {"type": "boolean", "default": True,
                                 "description": "Reserved: lower the music under the voice. Accepted but not implemented yet, so it changes nothing."},
                "sfx_preset": {"type": "string", "enum": SFX_PRESETS, "default": "auto",
                               "description": "Reserved: sound effects on transitions. Accepted but not implemented yet, so it changes nothing."},
            },
            "required": [],
        },
    },
    {
        "name": "extract_clips",
        "description": (
            "Cut the best moments out of a long video (a local file or a YouTube or other video link) into captioned vertical shorts "
            "of about 30 seconds each (never over 60): it transcribes the speech with Whisper, scores the moments, crops to 9:16 with "
            "face tracking and burns in captions. Use it when the user already has a video; use generate_short to make one from a "
            "topic, or dub_video to change its language. Returns {job_id, status, message} at once and works in the background, "
            "several minutes or more for a long video and slower without an NVIDIA GPU; poll get_render_status until 'completed' "
            "(its 'outputs' lists the clip paths) or 'failed'. Side effects: a linked video is downloaded; a local source is only "
            "read, never changed; clips are written under sessions/ in the ShortsFlow folder; nothing is uploaded or posted. Works "
            "without any API key; with an AI key the transcript goes to that provider for scoring and titles."),
        "annotations": _hints("Cut a long video into shorts"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_video": {"type": "string", "minLength": 1,
                                 "description": ("The video to clip: an http(s) link (YouTube and other sites) or the path of an existing local "
                                                 "file (absolute, or relative to the ShortsFlow folder). Required.")},
                "clip_count": {"type": "integer", "default": 3, "minimum": 1,
                               "description": "How many shorts to cut out, 1 or more. Fewer come back when the video has fewer good moments."},
                "smart_crop": {"type": "boolean", "default": True,
                               "description": "Follow the speaker's face when cropping the wide video to vertical."},
                "tighten": {"type": "boolean", "default": True,
                            "description": "Cut out silences and dead air inside each short."},
                "layout": {"type": "string", "enum": ["single", "split", "active", "fit"], "default": "single",
                           "description": ("Framing: single = face-tracked crop; split = two speakers stacked; active = cut to "
                                           "whoever is talking (stacked when unsure), best for podcasts and interviews; fit = the whole picture centred over a "
                                           "blurred copy of itself, nothing cropped off the sides (screen recordings, gameplay).")},
                "use_remotion": {"type": "boolean", "default": True,
                                 "description": "Animated captions (needs Node.js). False renders without animated captions."},
                "caption_style": {"type": "string", "enum": CAPTION_STYLES, "default": "HORMOZI", "description": _CAPTION_HELP},
                "language": {"type": "string", "default": "en",
                             "description": "Language spoken in the video as a code (en, hi, es, fr, ...), or 'auto' to detect it."},
                "auto_edit": {"type": "string", "enum": ["podcast", "hype", "educational", "vlog"],
                              "description": ("Edit like an editor: cuts, zooms, cutaways, teaser opening, colour and sound effects for this kind "
                                              "of video. Left out, no such edit is made.")},
                "edit_strength": {"type": "string", "enum": ["subtle", "medium", "hyped"], "default": "medium",
                                  "description": "Only with auto_edit: how much of the edit shows (subtle keeps it quiet, hyped uses everything)."},
            },
            "required": ["source_video"],
        },
    },
    {
        "name": "generate_social_package",
        "description": (
            "Write the post text for a short about a topic. Use it when the user needs a title, description and tags to paste; it makes no "
            "video and publishes nothing (publish_video does that, and already knows the text of videos made here). Returns the text "
            "directly, no job, usually within seconds (up to about a minute when the AI is slow): a JSON object with title, description and tags "
            "(a list) from the configured AI model. When the AI cannot be reached it is a generic template instead, and when the engine is not "
            "installed the keys are title, description, hashtags, tiktok_caption and reels_caption, so check the wording. Side effect: the "
            "topic is sent to the configured AI text provider."),
        "annotations": _hints("Write title, description and tags", read_only=True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "minLength": 1, "description": "What the video is about, e.g. 'Why the sky is blue'. Required."},
                "category": {"type": "string", "default": "general",
                             "description": "Broad category used for the wording and tags, e.g. 'science' or 'history'."},
                "mode": {"type": "string", "enum": CONTENT_MODES, "default": "FACTS",
                         "description": "Format of the video, which shapes the text (FACTS frames it as a 'two truths and a lie' quiz)."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "get_render_status",
        "description": (
            "Check a background job started by generate_short, extract_clips, create_explainer or dub_video. Use it after starting a "
            "job, every 20-30 seconds until the status is no longer 'processing'. Instant and read-only. Returns a JSON object: status "
            "('processing', 'completed', 'failed' or 'not_found'), progress (0 while running, 100 when completed; there are no "
            "steps between, so judge a running job by its logs), logs (the last 20 lines, live), error (the last log lines, when "
            "failed), and for extract_clips, create_explainer and dub_video 'outputs' (all finished video paths) with 'output' (the "
            "first one). Jobs are remembered only while this server runs: after a restart the answer is 'not_found', and "
            "list_videos still finds the files."),
        "annotations": _hints("Check a render job", read_only=True, repeatable=True, online=False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "minLength": 1,
                           "description": "The job_id returned by generate_short, extract_clips, create_explainer or dub_video. Required."},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "list_supported_modes",
        "description": (
            "List the values the other tools accept. Use it when unsure which value to pass. Instant, read-only, takes no input and needs no "
            "key. Returns a JSON object of lists: content_modes, caption_styles, tts_providers, aspect_ratios, sfx_presets, vibes, "
            "explainer_kinds, explainer_templates, explainer_themes, dub_languages and publish_platforms."),
        "annotations": _hints("List accepted options", read_only=True, repeatable=True, online=False),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_explainer",
        "description": (
            "Make a narrated explainer video from a topic and sources (a web page, PDF, arXiv paper, YouTube link, text, audio or video "
            "file): the script is written only from the sources, with narration, diagrams, Manim animation, stock footage, captions and "
            "music, in 16:9 and 9:16. kind 'animate' makes one continuous animation under the whole narration instead and needs no source. "
            "Use extract_clips to cut a video the user already has and generate_short for an idea with no sources. Returns {job_id, "
            "status, message} at once and works in the background, often 10 minutes or more (draft and a single shape are faster); "
            "poll get_render_status until 'completed' (its 'outputs' lists the video paths) or 'failed'. Side effects: the "
            "source text and topic go to the configured AI text provider, short footage search phrases to Pexels and the "
            "narration to ElevenLabs or Edge; files are written under sessions/ in the ShortsFlow folder; nothing is posted."),
        "annotations": _hints("Make an explainer video"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "minLength": 1, "description": "What the video explains, e.g. 'How binary search halves the work'. Required."},
                "sources": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 3,
                            "description": ("Up to 3 sources: web links, PDF or arXiv links, YouTube links, paths of existing files, or pasted notes. "
                                            "At least one is required for kind 'case'; optional for 'animate'.")},
                "kind": {"type": "string", "enum": EXPLAINER_KINDS, "default": "case",
                         "description": "case = a sectioned explainer; animate = one continuous animation (equations, processes, algorithms)."},
                "template": {"type": "string", "enum": EXPLAINER_TEMPLATES, "default": "case",
                             "description": ("The kind of story, only for kind 'case': case, postmortem (what went wrong), history, explainer, recipe, "
                                             "news, animation, or story (a rough preview: drawn characters over painted skies, for a narrated tale about people; 9:16 works best). Ignored for 'animate'.")},
                "theme": {"type": "string", "enum": EXPLAINER_THEMES, "default": "dark", "description": "The look (colours and type) of the whole video."},
                "formats": {"type": "string", "default": "16:9,9:16",
                            "description": "Video shapes to render, comma separated, from 16:9, 9:16, 1:1 and 4:5. One shape renders faster."},
                "draft": {"type": "boolean", "default": False,
                          "description": "True = a quick, small render to check the result before the full one."},
                "avatar": {"type": "string", "default": "off",
                           "description": ("A drawn presenter in the corner who talks with the narration: off, alex, maya, priya, sam, leo, nora (people), "
                                           "miso, luna (cats), biscuit (a dog), bolt (a robot), or the name of one saved in the ShortsFlow app.")},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "dub_video",
        "description": (
            "Translate a video's speech and re-voice it in another language: transcribe, translate sentence by sentence, speak with one "
            "synthetic voice, replace the original voice (music and effects are kept when the optional 'demucs' package is installed, else "
            "the original sound stays faintly under the new voice) and write translated subtitles. No voice cloning, no lip-sync. Use "
            "extract_clips instead to cut shorts without changing the language. Returns {job_id, status, message} at once and works in "
            "the background, from a few minutes to much longer for a long video; poll get_render_status until 'completed' (its 'outputs' "
            "lists the dubbed video) or 'failed'. Side effects: a linked video is downloaded; a local source is only read, never "
            "changed; the translated text goes to the voice service (Edge or ElevenLabs) and the transcript to the AI text provider; files "
            "are written under sessions/ in the ShortsFlow folder; nothing is posted."),
        "annotations": _hints("Dub a video into another language"),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_video": {"type": "string", "minLength": 1,
                                 "description": ("The video to dub, with English speech: an http(s) link or the path of an existing local file (absolute, or "
                                                 "relative to the ShortsFlow folder). Required.")},
                "target_lang": {"type": "string", "enum": DUB_LANGUAGES, "description": "The language to dub into, as a two-letter code. Required."},
                "dub_captions": {"type": "boolean", "default": False, "description": "Burn the translated subtitles into the dubbed video (re-encodes; the .srt file is always written)."},
                "dub_voice": {"type": "string", "enum": ["female", "male"], "default": "female", "description": "The voice for the target language."},
            },
            "required": ["source_video", "target_lang"],
        },
    },
    {
        "name": "list_videos",
        "description": (
            "List the finished videos this ShortsFlow install has made (clips, case explainers in each shape, dubs, recaps), newest first. "
            "Use it to find the path to give publish_video, or to see what a finished job produced (get_render_status only knows jobs of this "
            "server run). Read-only, usually a few seconds at most; sends nothing. Returns {count, videos: [{path, title, shape, label, published_to}]}, "
            "where label is a readable line with shape, length, size and date, and published_to lists the platforms already used. Only the sessions "
            "folder is searched; drafts and videos from generate_short saved outside it are not listed."),
        "annotations": _hints("List finished videos", read_only=True, repeatable=True, online=False),
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {"type": "string", "enum": VIDEO_SHAPES, "default": "all", "description": "Only videos of this shape: tall is 9:16, wide is 16:9, all is every shape."},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100, "description": "How many videos to return, 1 to 100."},
            },
            "required": [],
        },
    },
    {
        "name": "publish_video",
        "description": (
            "Publish one finished video (a path from list_videos) to YouTube, TikTok, Instagram and the other platforms, through the "
            "user's own Upload-Post account, or directly to their own YouTube channel (youtube_direct). By default it only previews: "
            "dry_run is true, nothing is sent and the reply shows what would go where. Set dry_run to false only when the user asked to "
            "post: the video and its text then leave this computer and go live on those accounts (youtube_direct starts private), which this "
            "server cannot undo. A video is never sent twice to the same platform. Answers when the work is done: a preview in seconds, an "
            "upload as long as the file takes; there is no job. Returns {dry_run, ok, sent, details}: sent is true only when every platform "
            "succeeded; with ok false (a tool error: missing key, already published, failed upload) read details, since some platforms may "
            "have received it. Only video files inside the sessions folder are accepted. Keys and the YouTube sign-in are set in the "
            "ShortsFlow app's Settings card."),
        "annotations": _hints("Publish a video (previews by default)", destructive=True),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "description": "Path of a finished video inside the ShortsFlow sessions folder, from list_videos. Required."},
                "platforms": {"type": "array", "items": {"type": "string", "enum": PUBLISH_PLATFORMS}, "minItems": 1,
                              "description": "Where to publish. youtube_direct goes straight to the user's own channel; the others go through Upload-Post. Required."},
                "title": {"type": "string", "description": "Title on the platform (cut to 200 characters). Empty or left out uses the video's own title."},
                "description": {"type": "string", "description": "Description text. Left out, Upload-Post platforms get the title as description and youtube_direct gets none."},
                "tags": {"type": "string", "description": "Tags separated by commas. Left out, the post has no tags."},
                "privacy": {"type": "string", "enum": PRIVACY, "default": "private",
                            "description": "Only for a youtube_direct upload: private, unlisted or public."},
                "dry_run": {"type": "boolean", "default": True,
                            "description": "True (the default) only previews and sends nothing. False really publishes; only the JSON value false does."},
            },
            "required": ["path", "platforms"],
        },
    },
]

_SCHEMAS = {t["name"]: t["inputSchema"] for t in TOOLS_DEFINITIONS}
# text that never becomes a main.py argument, so a leading '-' is harmless
_NOT_ON_THE_COMMAND_LINE = ("publish_video", "generate_social_package", "get_render_status", "list_videos")


def _flag_like(text):
    """Would main.py read this value as a flag? ("- a list item" is plain text to argparse; "--x" and "-x" are not.)"""
    text = text.strip()
    return text.startswith("-") and not text.startswith("- ")


def _is_link(text):
    """The same test the pipeline uses (engine.media_gen.is_url), plus a host must be there."""
    text = text.strip()
    if text.startswith("www."):
        return True
    try:
        return text.startswith(("http://", "https://")) and bool(urlparse(text).hostname)
    except ValueError:
        return False


def _file_exists(text):
    return os.path.isfile(os.path.join(ROOT_DIR, text.strip()))       # jobs run in ROOT_DIR, so a relative path means from there


def _looks_like_a_path(text):
    """A source that was meant as a file (pasted notes are allowed too, so only clear cases): an absolute path or one name with an extension."""
    text = text.strip()
    if "\n" in text or len(text) > 300:
        return False
    return os.path.isabs(text) or bool(re.match(r"^([A-Za-z]:[\\/]|\.{0,2}[\\/])", text)) or bool(
        re.search(r"\.(pdf|txt|md|html?|docx?|csv|json|mp3|wav|m4a|ogg|flac|mp4|mov|mkv|webm|avi|m4v)$", text, re.I))


def _check_value(label, prop, value):
    """(value, error text or None) for one value against its schema: type, enum, range and length."""
    kind = prop.get("type")
    if kind == "boolean" and not isinstance(value, bool):
        return value, f"'{label}' must be true or false."
    if kind == "integer":
        if isinstance(value, str) and re.fullmatch(r"\s*-?\d{1,9}\s*", value):
            value = int(value)                                        # some clients send numbers as text
        elif isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int):
            return value, f"'{label}' must be a whole number."
        if value < prop.get("minimum", value):
            return value, f"'{label}' must be at least {prop['minimum']} (got {value})."
        if value > prop.get("maximum", value):
            return value, f"'{label}' must be at most {prop['maximum']} (got {value})."
    if kind == "string":
        if not isinstance(value, str):
            return value, f"'{label}' must be text."
        if "enum" in prop and value not in prop["enum"]:
            return value, f"'{label}' must be one of: {', '.join(prop['enum'])} (got '{value[:60]}')."
        if prop.get("minLength") and not value.strip():
            return value, f"'{label}' must not be empty."
    if kind == "array":
        if not isinstance(value, list):
            return value, f"'{label}' must be a list."
        if len(value) < prop.get("minItems", 0):
            return value, f"'{label}' needs at least {prop['minItems']} item(s)."
        if len(value) > prop.get("maxItems", len(value)):
            return value, f"'{label}' takes at most {prop['maxItems']} items."
        for item in value:
            problem = _check_value(label, prop.get("items", {}), item)[1]
            if problem:
                return value, problem
    return value, None


def check_arguments(tool_name, args):
    """(cleaned arguments, error text or None): checked against the tool's own inputSchema before anything starts. A null counts as left out."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return {}, "Tool arguments must be a JSON object."
    schema = _SCHEMAS.get(tool_name)
    if schema is None:
        return args, None                                             # handle_tool_call names the unknown tool
    args = {k: v for k, v in args.items() if v is not None}
    props = schema["properties"]
    for name in schema.get("required", []):
        if args.get(name) in (None, "", []):
            choices = props[name].get("enum") or props[name].get("items", {}).get("enum")
            return args, f"{tool_name} needs '{name}'" + (f", from: {', '.join(choices)}." if choices else f": {props[name]['description']}")
    for name in [n for n in args if n in props]:                      # unknown extras are ignored
        args[name], problem = _check_value(name, props[name], args[name])
        if problem:
            return args, f"{tool_name}: {problem}"
        texts = args[name] if isinstance(args[name], list) else [args[name]]
        if tool_name not in _NOT_ON_THE_COMMAND_LINE and any(isinstance(t, str) and _flag_like(t) for t in texts):
            return args, f"{tool_name}: '{name}' must not start with '-' (it would be read as a command-line flag)."
    if tool_name in ("extract_clips", "dub_video"):
        source = args["source_video"] = args["source_video"].strip()
        if not _is_link(source) and not _file_exists(source):
            return args, (f"{tool_name}: 'source_video' ('{source[:200]}') is not an http(s) link and no such file exists. Give a video link or the "
                          "path of an existing file.")
    if tool_name == "create_explainer":
        for source in args.get("sources", []):
            if not _is_link(source) and not _file_exists(source) and (_looks_like_a_path(source) or "://" in source.split()[0]):
                return args, f"create_explainer: no such file or http(s) link: '{source[:200]}'."
        if args.get("formats", "").strip():
            shapes = [s.strip() for s in args["formats"].split(",") if s.strip()]
            if not shapes or any(s not in ASPECT_RATIOS for s in shapes):
                return args, f"create_explainer: 'formats' takes shapes from: {', '.join(ASPECT_RATIOS)} (got '{args['formats'][:60]}')."
    if tool_name == "generate_short" and args.get("mode") in TOPIC_MODES and not args.get("prompt") and not args.get("script") and args.get("category", "").lower() in ("", "random"):
        return args, f"generate_short: mode {args['mode']} needs a topic: pass 'prompt' (or 'category') with the article, product, story or case."
    return args, None


def run_main_command(job_id: str, args_list: list):
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "processing", "progress": 0, "logs": [], "output": None}

    main_py = os.path.join(ROOT_DIR, "main.py")
    if not os.path.exists(main_py):
        # e.g. a minimal container that only serves tools/list: say so plainly instead of failing with a Python error
        with JOBS_LOCK:
            JOBS[job_id].update({"status": "failed", "error": "Rendering needs the full ShortsFlow checkout (main.py and its "
                                 "requirements). Clone https://github.com/ghost1412/shortsflow and run mcp_server.py from it."})
        return
    cmd = [sys.executable, main_py, "--video_id", job_id, "--skip_upload"] + args_list
    started = time.time()
    results_json = None
    mode = args_list[args_list.index("--mode") + 1] if "--mode" in args_list[:-1] else ""
    if "--source_video" in args_list and mode != "DUB" and "--output_json" not in args_list:
        # the clipping pipeline reports where the finished clips are; read that instead of guessing a file name
        results_json = os.path.join(ROOT_DIR, "sessions", f"mcp_{job_id}.json")
        os.makedirs(os.path.dirname(results_json), exist_ok=True)
        cmd += ["--output_json", results_json]
    print(f"[MCP Worker] Starting command: {' '.join(cmd)}", file=sys.stderr)

    try:
        process = subprocess.Popen(
            cmd,
            cwd=ROOT_DIR,
            stdin=subprocess.DEVNULL,         # our stdin carries the client's messages: a job (or its FFmpeg) must not read them
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        log_lines = []
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            cleaned = line.strip()
            log_lines.append(cleaned)
            with JOBS_LOCK:
                JOBS[job_id]["logs"] = log_lines[-20:]       # so get_render_status shows live output while the job runs
            print(f"[Job {job_id[:8]}] {cleaned}", file=sys.stderr)

        process.wait()

        with JOBS_LOCK:
            if process.returncode == 0:
                JOBS[job_id]["status"] = "completed"
                JOBS[job_id]["progress"] = 100
                JOBS[job_id]["logs"] = log_lines[-20:]
                JOBS[job_id]["output"] = None
                if results_json and os.path.exists(results_json):
                    try:
                        with open(results_json, "r", encoding="utf-8") as f:
                            clips = json.load(f).get("clips", [])
                        paths = [c.get("video_path") for c in clips if c.get("video_path")]
                        JOBS[job_id]["outputs"] = paths
                        JOBS[job_id]["output"] = paths[0] if paths else None
                    except (OSError, ValueError):
                        pass
                elif not results_json and mode in ("CASE", "ANIMATE", "DUB"):
                    paths = _videos_since(started)
                    if mode == "DUB":                        # not the source a dub downloads into the same folder
                        paths = [p for p in paths if "_dub_" in os.path.basename(p)]
                    JOBS[job_id]["outputs"] = paths
                    JOBS[job_id]["output"] = paths[0] if paths else None
            else:
                JOBS[job_id]["status"] = "failed"
                JOBS[job_id]["error"] = "\n".join(log_lines[-10:])
    except Exception as e:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)

def _text(obj, error=False):
    reply = {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, indent=2)}]}
    if error:
        reply["isError"] = True
    return reply


def _settings():
    """shortsflow.settings, or None in the minimal container (it only has shortsflow/__init__.py)."""
    try:
        if ROOT_DIR not in sys.path:
            sys.path.insert(0, ROOT_DIR)
        from shortsflow import settings
        return settings
    except Exception:
        return None


def _videos_since(since):
    """Paths of finished videos written after `since` (a time.time() value), newest first."""
    st = _settings()
    if st is None:
        return []
    try:
        return [v["path"] for v in st.list_videos(ROOT_DIR, limit=100, min_bytes=1000) if os.path.getmtime(v["path"]) >= since - 2]
    except Exception:
        return []


def _start_job(job_id, cli_args, message):
    with JOBS_LOCK:                            # known at once: a status call right after this one must not say not_found
        JOBS[job_id] = {"status": "processing", "progress": 0, "logs": [], "output": None}
    threading.Thread(target=run_main_command, args=(job_id, cli_args)).start()
    return _text({"job_id": job_id, "status": "processing", "message": message})


def _create_explainer(job_id, args):
    topic = str(args.get("topic", "")).strip()
    if not topic:
        return _text("create_explainer needs 'topic'.", True)
    kind = args.get("kind") if args.get("kind") in EXPLAINER_KINDS else "case"
    sources = [str(x).strip() for x in (args.get("sources") or []) if str(x).strip()][:3]
    if kind == "case" and not sources:
        return _text("create_explainer with kind 'case' needs at least one source (a link or file); the script is written only from them. "
                     "Use kind 'animate' for an animation from a topic alone.", True)
    cli = ["--mode", "ANIMATE" if kind == "animate" else "CASE", "--prompt", topic]
    for src in sources:
        cli += ["--sources", src]
    theme = args.get("theme") if args.get("theme") in EXPLAINER_THEMES else "dark"
    cli += ["--case", f"theme={theme}"]
    if kind == "case" and args.get("template") in EXPLAINER_TEMPLATES and args["template"] != "case":
        cli += ["--case", f"template={args['template']}"]
    formats = str(args.get("formats") or "").strip()
    if formats:
        cli += ["--case", f"formats={formats}"]
    if args.get("draft"):
        cli += ["--case", "draft"]
    avatar = re.sub(r"[^a-z0-9_-]", "", str(args.get("avatar") or "").lower())
    if avatar and avatar != "off":
        cli += ["--case", f"avatar={avatar}"]
    return _start_job(job_id, cli, f"Explainer video ({kind}) started for '{topic}'.")


def _dub_video(job_id, args):
    source = str(args.get("source_video", "")).strip()
    lang = args.get("target_lang")
    if not source or lang not in DUB_LANGUAGES:
        return _text("dub_video needs 'source_video' and a 'target_lang' from: " + ", ".join(DUB_LANGUAGES) + ".", True)
    cli = ["--mode", "DUB", "--source_video", source, "--target_lang", lang]
    if args.get("dub_captions"):
        cli.append("--dub_captions")
    if args.get("dub_voice") in ("female", "male"):
        cli += ["--dub_voice", args["dub_voice"]]
    return _start_job(job_id, cli, f"Dubbing {source} into {lang} started.")


def _list_videos(args):
    st = _settings()
    if st is None:
        return _text("Listing videos needs the full ShortsFlow checkout (shortsflow/settings.py). Run mcp_server.py from it.", True)
    shape = args.get("shape") if args.get("shape") in VIDEO_SHAPES else "all"
    try:
        limit = max(1, min(100, int(args.get("limit", 20))))
    except (TypeError, ValueError):
        limit = 20
    rows = []
    for v in st.list_videos(ROOT_DIR, shape=shape, limit=limit):
        rows.append({"path": v["path"], "title": v.get("title"), "shape": v.get("shape"), "label": v.get("label"),
                     "published_to": sorted(st.file_published_to(v["path"]))})
    return _text({"count": len(rows), "videos": rows})


def _publish_video(args):
    st = _settings()
    if st is None:
        return _text("Publishing needs the full ShortsFlow checkout (shortsflow/settings.py). Run mcp_server.py from it.", True)
    path = str(args.get("path", "")).strip()
    platforms = [p for p in dict.fromkeys(args.get("platforms") or []) if p in PUBLISH_PLATFORMS]
    if not path or not platforms:
        return _text("publish_video needs 'path' (from list_videos) and at least one of 'platforms': " + ", ".join(PUBLISH_PLATFORMS) + ".", True)
    norm = lambda q: os.path.normcase(os.path.realpath(q))       # realpath: a link inside sessions/ cannot lead outside it
    if not norm(path).startswith(norm(os.path.join(ROOT_DIR, "sessions")) + os.sep):
        return _text("That video is not inside the ShortsFlow sessions folder. Use a path from list_videos.", True)
    if not path.lower().endswith(VIDEO_EXTENSIONS):
        return _text("That is not a video file. Use a path from list_videos.", True)
    if not os.path.isfile(path):
        return _text("No such video file. Use a path from list_videos.", True)
    dry = args.get("dry_run", True) is not False        # only an explicit false really publishes
    ok, lines = st.publish_file(path, args.get("title", ""), args.get("description", ""), args.get("tags", ""), platforms,
                                privacy=args.get("privacy") if args.get("privacy") in PRIVACY else "private",
                                home=ROOT_DIR, dry_run=dry, env_path=os.path.join(ROOT_DIR, ".env"))
    return _text({"dry_run": dry, "ok": bool(ok), "sent": (not dry) and bool(ok), "details": lines}, error=not ok)


def handle_tool_call(tool_name: str, args: dict) -> dict:
    job_id = str(uuid.uuid4())[:8]
    args, problem = check_arguments(tool_name, args)
    if problem:
        return _text(problem, True)

    if tool_name == "generate_short":
        cli_args = [
            "--mode", args.get("mode", "FACTS"),
            "--vibe", args.get("vibe", "suspense"),
            "--caption_style", args.get("caption_style", "HORMOZI")
        ]

        if args.get("category"):
            cli_args.extend(["--category", args["category"]])
        if args.get("prompt"):
            cli_args.extend(["--prompt", args["prompt"]])
        if args.get("script"):
            cli_args.extend(["--script", args["script"]])
        if args.get("use_remotion", True):
            cli_args.append("--use_remotion")
        if args.get("tts_provider"):
            cli_args.extend(["--tts_provider", args["tts_provider"]])
        if args.get("aspect_ratio"):
            cli_args.extend(["--aspect_ratio", args["aspect_ratio"]])
        if args.get("auto_ducking", True):
            cli_args.append("--auto_ducking")
        if args.get("sfx_preset"):
            cli_args.extend(["--sfx_preset", args["sfx_preset"]])

        return _start_job(job_id, cli_args, f"Short video generation started for mode '{args.get('mode', 'FACTS')}'.")

    elif tool_name == "extract_clips":
        if not str(args.get("source_video", "")).strip():
            return {"isError": True, "content": [{"type": "text", "text": "extract_clips needs 'source_video' (a video URL or a file path)."}]}
        cli_args = [
            "--source_video", args["source_video"],
            "--extract_mode", "shorts",
            "--clip_count", str(args.get("clip_count", 3)),
            "--caption_style", args.get("caption_style", "HORMOZI")
        ]

        if args.get("smart_crop", True):
            cli_args.append("--smart_crop")
        if args.get("tighten", True):
            cli_args.append("--tighten")
        if args.get("use_remotion", True):
            cli_args.append("--use_remotion")
        if args.get("layout"):
            cli_args.extend(["--layout", args["layout"]])
        if args.get("language"):
            cli_args.extend(["--language", str(args["language"])])
        if args.get("auto_edit") in ("podcast", "hype", "educational", "vlog"):
            cli_args.extend(["--auto_edit", args["auto_edit"], "--edit_strength",
                             args.get("edit_strength") if args.get("edit_strength") in ("subtle", "medium", "hyped") else "medium"])

        return _start_job(job_id, cli_args, f"Viral clip extraction started for {args['source_video']}.")

    elif tool_name == "generate_social_package":
        topic = args.get("topic", "General Video")
        category = args.get("category", "general")
        mode = args.get("mode", "FACTS")

        try:
            from engine.social_gen import generate_viral_metadata
            metadata = generate_viral_metadata([{"fact": topic}], mode=mode, category=category)
        except Exception:
            metadata = {
                "title": f"Unbelievable {topic} Revealed! 💥 #Shorts",
                "description": f"Check out this amazing video on {topic}! Like & Subscribe for more daily videos.",
                "hashtags": ["#Shorts", "#Viral", f"#{category.replace(' ', '')}", "#FYP"],
                "tiktok_caption": f"You won't believe this about {topic}! 😱 #fyp #viral #trending",
                "reels_caption": f"Tag a friend who needs to see this! 👇 {topic} #reels #explore"
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(metadata, indent=2)
                }
            ]
        }

    elif tool_name == "create_explainer":
        return _create_explainer(job_id, args)

    elif tool_name == "dub_video":
        return _dub_video(job_id, args)

    elif tool_name == "list_videos":
        return _list_videos(args)

    elif tool_name == "publish_video":
        return _publish_video(args)

    elif tool_name == "get_render_status":
        req_id = args.get("job_id", "")
        with JOBS_LOCK:
            job_info = dict(JOBS.get(req_id, {"status": "not_found", "message": f"Job ID {req_id} not recognized."}))

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(job_info, indent=2)
                }
            ]
        }

    elif tool_name == "list_supported_modes":
        info = {
            "content_modes": CONTENT_MODES,
            "caption_styles": CAPTION_STYLES,
            "tts_providers": TTS_PROVIDERS,
            "aspect_ratios": ASPECT_RATIOS,
            "sfx_presets": SFX_PRESETS,
            "vibes": VIBES,
            "explainer_kinds": EXPLAINER_KINDS,
            "explainer_templates": EXPLAINER_TEMPLATES,
            "explainer_themes": EXPLAINER_THEMES,
            "dub_languages": DUB_LANGUAGES,
            "publish_platforms": PUBLISH_PLATFORMS,
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(info, indent=2)
                }
            ]
        }

    else:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]
        }

def main():
    """Reads JSON-RPC standard input line-by-line and writes responses to stdout."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")     # MCP messages are UTF-8; a Windows pipe defaults to the ANSI code page
    print("[MCP Server] ShortsFlow AI Studio MCP Server listening on stdio...", file=sys.stderr)

    while True:
        req_id = None
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue

            try:
                req = json.loads(line)
            except ValueError:
                print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: not valid JSON"}}), flush=True)
                continue
            if not isinstance(req, dict):
                print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request: expected one JSON object"}}), flush=True)
                continue
            req_id = req.get("id")
            method = req.get("method")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "ShortsFlow AI Studio MCP Server",
                            "version": _server_version()
                        }
                    }
                }
                print(json.dumps(resp), flush=True)

            elif method == "notifications/initialized":
                # Client acknowledging initialization
                pass

            elif method == "ping":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
                print(json.dumps(resp), flush=True)

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": TOOLS_DEFINITIONS
                    }
                }
                print(json.dumps(resp), flush=True)

            elif method == "tools/call":
                params = req.get("params")
                if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                    print(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "tools/call needs params: {name, arguments}"}}), flush=True)
                    continue
                tool_name = params["name"]

                # stdout carries only JSON-RPC: whatever the engine prints during a call goes to stderr
                with contextlib.redirect_stdout(sys.stderr):
                    try:
                        tool_result = handle_tool_call(tool_name, params.get("arguments"))
                    except Exception as e:           # a failing tool is a tool error the agent can read
                        tool_result = _text(f"{tool_name} failed: {e}", True)

                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_result
                }
                print(json.dumps(resp), flush=True)

            else:
                if req_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
                    print(json.dumps(resp), flush=True)

        except Exception as e:
            print(f"[MCP Error] Exception handling request: {e}", file=sys.stderr)
            if req_id is not None:   # answer anyway: a client that gets no reply waits forever
                print(json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {e}"}}), flush=True)

if __name__ == "__main__":
    main()
