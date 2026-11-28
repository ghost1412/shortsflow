"""A storyteller narrator for the case explainer through Gemini's speech models (`--case narrator=gemini`).

Online and optional: it is used only when chosen. The narration text and the instructions on how to tell it are sent to Google with your
GEMINI_API_KEY; nothing else is. The models are previews with a small free quota. Each section is one request. The model gives no word
timings, so the finished audio is timed with Whisper on this PC, like the voice server's (engine/expressive_voice.py). If any section
cannot be spoken, the whole narration is made again with the standard voice, so a video never changes voice part-way.
"""
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import wave

from engine import expressive_voice

MODELS = ("gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts")
DEFAULT_VOICE = "Algieba"
MAX_WAIT = 75                 # a "try again in N seconds" up to this is waited out (the free limit is a few requests a minute)
TRIES = 4

DIRECTION = (
    "You are an animated grandfather, a master storyteller, telling this story to children sitting around you. Never sound like reading.\n"
    "- Lively and intimate, with rising curiosity; lean on the surprising words and vary your pace and pitch.\n"
    "- When a character speaks, change your voice to be that character, with the feeling of that moment.\n"
    "- Pause briefly before a surprise or a clever answer, then let it land.\n"
    "- This part should feel {mood}.\n"
    "Speak only the text below, exactly as written, in its own language:\n\n")
FEELING = {"tense": "tense and suspenseful", "excited": "excited", "serious": "serious and hushed", "warm": "warm and happy", "calm": "calm and inviting"}


def available():
    return bool(os.getenv("GEMINI_API_KEY"))


def _wait_asked(body):
    """Seconds the service asks to wait, or None when waiting cannot help (the day's quota)."""
    if re.search(r"per ?day", body, re.I):
        return None
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    return float(m.group(1)) if m else None


def _post(model, payload):
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", json.dumps(payload).encode(),
                                 {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY", "")})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return 200, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def audio_for(text, mood, voice, post=None, sleep=time.sleep):
    """24 kHz mono 16-bit samples of `text` told as a story. Raises RuntimeError when no model gives them."""
    payload = {"contents": [{"parts": [{"text": DIRECTION.format(mood=FEELING.get(str(mood or "").lower(), "warm and curious")) + text}]}],
               "generationConfig": {"responseModalities": ["AUDIO"],
                                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice or DEFAULT_VOICE}}}}}
    why = "no model answered"
    for model in MODELS:
        for _ in range(TRIES):
            try:
                status, body = (post or _post)(model, payload)
            except Exception as e:
                why = f"{model} could not be reached ({type(e).__name__})"
                break
            if status == 200:
                try:
                    pcm = base64.b64decode(json.loads(body)["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
                except (KeyError, IndexError, TypeError, ValueError):
                    why = f"{model} sent no audio"
                    continue                                        # now and then an answer has no sound: ask again
                if len(pcm) > 2000:
                    return pcm
                why = f"{model} sent no audio"
                continue
            why = f"{model}: HTTP {status}"
            wait = _wait_asked(body) if status == 429 else (5.0 if status in (500, 503) else None)
            if wait is None or wait > MAX_WAIT:
                break
            print(f"[Log] The storyteller voice asks to wait {wait:.0f} s.")
            sleep(wait + 1)
    raise RuntimeError(why)


def speak(text, out_audio, out_subs, sample=None, mood=None, first=False, voice=DEFAULT_VOICE, post=None, listen=None):
    """Speak one section: writes out_audio (mp3) and out_subs (the words with their times). Returns (audio, subs)."""
    pcm = audio_for(text, mood, voice, post=post)
    raw = out_audio + ".wav"
    with wave.open(raw, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-b:a", "160k", out_audio], check=True)
    try:
        os.remove(raw)
    except OSError:
        pass
    words = expressive_voice.timed(text, out_audio, listen or expressive_voice.hear)
    with open(out_subs, "w", encoding="utf-8") as f:
        json.dump(words, f)
    return out_audio, out_subs
