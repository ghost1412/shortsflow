"""Expressive narration for the case explainer through a local voice server (`--case narrator=voice_server`).

Optional: it is used only when the person asks for it AND a voice server answers on this PC. The server is the Chatterbox one of the Voice-over
card (`python -m engine.voice_server install`, then start), or any server that takes the same request: POST {"input", "exaggeration",
"sample_audio_b64"} and answers with WAV audio. The address is SHORTSFLOW_VOICE_SERVER_URL (default http://127.0.0.1:8080). Nothing leaves the
PC: the text and the voice sample go to the server on this machine.

Each section is spoken with its mood (the script's "mood": tense, excited, serious, warm, calm), sent as Chatterbox's emotion strength
("exaggeration"), in the presenter's voice when there is one (its Edge voice sample is the voice to copy). The server gives no word timings, so
the finished audio is timed with Whisper on the CPU (the GPU stays free for the voice) and the script's own words keep their spelling.
"""
import base64
import difflib
import json
import os
import re
import subprocess
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8080"
MOODS = {"calm": 0.35, "serious": 0.45, "warm": 0.55, "tense": 0.65, "excited": 0.8}
DEFAULT_MOOD = "warm"


def server_url():
    return (os.getenv("SHORTSFLOW_VOICE_SERVER_URL") or DEFAULT_URL).rstrip("/")


def available(url=None, timeout=3):
    """True when a voice server answers at `url`."""
    try:
        with urllib.request.urlopen(url or server_url(), timeout=timeout) as r:
            return r.status == 200 and bool(json.loads(r.read() or b"{}").get("ok", True))
    except Exception:
        return False


def mood_strength(mood, first=False):
    """The emotion strength for a section's mood; the first section (the hook) is never below 'tense'."""
    value = MOODS.get(str(mood or "").lower(), MOODS[DEFAULT_MOOD])
    return max(value, MOODS["tense"]) if first else value


def _norm(word):
    return re.sub(r"[^a-z0-9]", "", word.lower())


def align(script_text, heard):
    """[{word, start, end}] with the script's own words and the heard words' times. `heard` is Whisper's [{word, start, end}]. Matched words
    take their times; words in between are spread over the gap; words the recogniser missed at the ends are spread over the edges."""
    words = script_text.split()
    if not words:
        return []
    if not heard:
        return []
    if not sane(heard):                                   # unusable times: spread the words over the span by their length (a longer word takes longer)
        lo, hi = max(float(heard[0]["start"]), 0.0), float(heard[-1]["end"])
        weights = [max(len(_norm(w)), 1) for w in words]
        step, at, out = (hi - lo) / sum(weights), lo, []
        for w, n in zip(words, weights):
            out.append({"word": w, "start": round(at, 3), "end": round(at + step * n, 3)})
            at += step * n
        return out
    a, b = [_norm(w) for w in words], [_norm(h["word"]) for h in heard]
    times = [None] * len(words)
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            h = heard[block.b + k]
            times[block.a + k] = (float(h["start"]), float(h["end"]))
    start0, end0 = float(heard[0]["start"]), float(heard[-1]["end"])
    i = 0
    while i < len(words):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(words) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else start0
        hi = times[j][0] if j < len(words) else end0
        hi = max(hi, lo + 0.05 * (j - i))
        step = (hi - lo) / (j - i)
        for k in range(i, j):
            times[k] = (lo + step * (k - i), lo + step * (k - i + 1))
        i = j
    return [{"word": w, "start": round(t[0], 3), "end": round(max(t[1], t[0] + 0.04), 3)} for w, t in zip(words, times)]


_WHISPER = {}


def sane(heard):
    """Whether Whisper's word times look like speech: no word lasts over two seconds and the typical word lasts at least a tenth of one. Whisper has been seen to give
    the first words of a section eleven seconds each and then squeeze the rest into 0.05 s each, so the mouth and the captions went out of step."""
    if not heard:
        return False
    d = sorted(float(h["end"]) - float(h["start"]) for h in heard)
    return d[-1] <= 2.0 and d[len(d) // 2] >= 0.1


def covers(heard, text):
    """Whether Whisper's words cover the script: it heard most of the words and the first one comes at the start. With the script as a hint Whisper has been seen to skip
    the first twelve seconds of a section and hear only a third of its words, which left the captions and the presenter with nothing to follow for that time."""
    return bool(heard) and len(heard) >= 0.7 * len(text.split()) and float(heard[0]["start"]) <= 1.5 and sane(heard)


def hear(audio, text):
    """Whisper's word timings for `audio` (CPU, the 'base' model, the script as a hint). When the words do not cover the script (see `covers`) it listens again
    without the hint, which the matching of heard words to script words does not need."""
    import whisper
    if "m" not in _WHISPER:
        _WHISPER["m"] = whisper.load_model(os.getenv("SHORTSFLOW_ALIGN_MODEL", "base"), device="cpu")

    def listen(**kw):
        result = _WHISPER["m"].transcribe(audio, language="en", word_timestamps=True, fp16=False, **kw)
        return [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]} for seg in result.get("segments", []) for w in seg.get("words", [])]
    heard = listen(initial_prompt=text[:800])
    if covers(heard, text):
        return heard
    again = listen()
    return again if covers(again, text) or not sane(heard) else heard


def speak(text, out_audio, out_subs, sample=None, mood=None, first=False, url=None, post=None, listen=None):
    """Speak one section through the voice server: writes out_audio (mp3) and out_subs (the words with their times). Returns (audio, subs).
    Raises RuntimeError when the server fails. `post(url, body) -> wav bytes` and `listen(audio, text) -> heard words` replace the network
    and Whisper (tests)."""
    body = {"input": text, "exaggeration": mood_strength(mood, first)}
    if sample and os.path.isfile(sample):
        with open(sample, "rb") as f:
            body["sample_audio_b64"] = base64.b64encode(f.read()).decode()
    try:
        if post:
            wav = post(url or server_url(), body)
        else:
            req = urllib.request.Request(url or server_url(), json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                wav = r.read()
    except Exception as e:
        raise RuntimeError(f"the voice server did not answer ({str(e)[:120]})")
    if not wav or len(wav) < 1000:
        raise RuntimeError("the voice server sent no audio")
    raw = out_audio + ".wav"
    with open(raw, "wb") as f:
        f.write(wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-b:a", "160k", out_audio], check=True)
    try:
        os.remove(raw)
    except OSError:
        pass
    words = align(text, (listen or hear)(out_audio, text))
    with open(out_subs, "w", encoding="utf-8") as f:
        json.dump(words, f)
    return out_audio, out_subs


def sample_for(edge_voice, folder):
    """A WAV of the Edge voice saying the sample line, as the voice for the server to copy (None when it cannot be made)."""
    from engine import avatars
    try:
        mp3, _ = avatars.voice_sample(edge_voice, folder)
    except RuntimeError:
        return None
    wav = mp3[:-4] + ".wav"
    if not os.path.isfile(wav):
        if subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "24000", wav]).returncode != 0:
            return None
    return wav


def own_sample(path, folder):
    """A person's own recording as the voice to copy: the first 30 seconds, one channel, 24 kHz WAV (kept in `folder`). Raises RuntimeError
    when it cannot be read or is shorter than 5 seconds."""
    import hashlib
    os.makedirs(folder, exist_ok=True)
    with open(path, "rb") as f:
        key = hashlib.sha1(f.read()).hexdigest()[:12]
    wav = os.path.join(folder, f"own_{key}.wav")
    if not os.path.isfile(wav):
        if subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-t", "30", "-ac", "1", "-ar", "24000", wav]).returncode != 0:
            raise RuntimeError(f"the recording could not be read: {path}")
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav],
                                   capture_output=True, text=True).stdout or 0)
    if seconds < 5:
        raise RuntimeError(f"the recording is {seconds:.0f} seconds; give 10-30 seconds of clean speech")
    return wav
