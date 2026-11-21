"""Voice-over: a script in, an audio file in YOUR voice out (`--mode VOICEOVER`).

The voice is cloned from a sample of your own voice by a local OpenAI-compatible TTS server (VoiceStudio, F5-TTS, XTTS, ... see
`engine.voice_gen.generate_voice_voicestudio`). Nothing leaves this PC unless VOICE_STUDIO_URL points at another machine. There is no
fallback to a stock voice: the point is your voice, so a missing sample or server is an error that says what to do.

Tone: each preset sends hints the server may use (`instructions`, `emotion`, `exaggeration`, `speed`) and ALSO changes the speed of the
finished audio here, so a preset always has a small, certain effect; how far the server follows the rest depends on the server.
Only clone your own voice, or the voice of someone who agreed to it.
"""
import os
import re
import subprocess

from engine.mode_options import Option, OptionError, OptionSet

MODE = "VOICEOVER"

# tone -> what to ask the server for, and the speed (1.0 = as spoken) applied to the finished audio
TONES = {
    "neutral": {"speed": 1.0, "exaggeration": 0.5, "instructions": ""},
    "warm": {"speed": 0.97, "exaggeration": 0.6, "instructions": "Speak in a warm, friendly, reassuring tone."},
    "excited": {"speed": 1.08, "exaggeration": 0.8, "instructions": "Speak in an excited, energetic, upbeat tone."},
    "calm": {"speed": 0.93, "exaggeration": 0.3, "instructions": "Speak in a calm, soft, relaxed tone."},
    "serious": {"speed": 0.95, "exaggeration": 0.4, "instructions": "Speak in a serious, steady, authoritative tone."},
    "dramatic": {"speed": 0.9, "exaggeration": 0.9, "instructions": "Speak in an intense, dramatic, trailer-voice tone with pauses."},
    "sad": {"speed": 0.88, "exaggeration": 0.5, "instructions": "Speak in a sad, quiet, heavy tone."},
}
CHUNK_CHARS = 280      # a local model reads short passages better than a whole page


def _check_sample(raw):
    path = os.path.expanduser(raw.strip().strip('"'))
    if not path:
        raise OptionError("'sample' is the path of a recording of the voice to copy (.wav or .mp3, 10-30 seconds of clean speech).")
    return path


OPTIONS = OptionSet("voiceover", [
    Option("sample", "path", "", "recording of your voice to copy (.wav or .mp3, 10-30 s of clean speech, one speaker)", check=_check_sample),
    Option("tone", "choice", "neutral", "how it is read", tuple(TONES)),
    Option("format", "choice", "mp3", "the audio file type", ("mp3", "wav")),
    Option("out", "path", "", "where to save it (default: the session folder)"),
    Option("server", "text", "", "address of the local voice server (default: VOICE_STUDIO_URL, else http://localhost:8080)"),
])


def split_script(text, limit=CHUNK_CHARS):
    """The script as passages of at most `limit` characters, cut at sentence ends (a longer sentence is cut at a comma or a space)."""
    out = []
    for para in re.split(r"\n\s*\n", str(text or "")):
        para = " ".join(para.split())
        if not para:
            continue
        cur = ""
        for sentence in re.findall(r"[^.!?।。]+[.!?।。]*\s*", para):
            sentence = sentence.strip()
            while len(sentence) > limit:
                cut = max(sentence.rfind(",", 0, limit), sentence.rfind(" ", 0, limit))
                cut = cut if cut > 0 else limit
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(sentence[:cut + 1].strip())
                sentence = sentence[cut + 1:].strip()
            if cur and len(cur) + 1 + len(sentence) > limit:
                out.append(cur)
                cur = ""
            cur = f"{cur} {sentence}".strip()
        if cur:
            out.append(cur)
    return out


def _synth_chunk(text, path, sample, tone, server):
    from engine.voice_gen import generate_voice_voicestudio
    t = TONES[tone]
    extra = {"speed": t["speed"], "exaggeration": t["exaggeration"], "emotion": tone, "style": tone}
    if t["instructions"]:
        extra["instructions"] = t["instructions"]
    generate_voice_voicestudio(text, output_audio=path, output_subs=path + ".subs.json", clone_voice=sample,
                               voice_studio_url=server or None, extra=extra)
    return path


def _join(ffmpeg, parts, out_path, speed, workdir):
    listing = os.path.join(workdir, "voiceover_parts.txt")
    with open(listing, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '" + os.path.abspath(p).replace("\\", "/").replace("'", "'\\''") + "'\n")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing]
    if abs(speed - 1.0) > 0.005:
        cmd += ["-filter:a", f"atempo={speed:.3f}"]
    cmd += [out_path] if out_path.endswith(".wav") else ["-b:a", "192k", out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("FFmpeg could not join the voice passages: " + (res.stderr or "")[-400:])
    return out_path


def make_voiceover(script, session_dir, sample, tone="neutral", fmt="mp3", out=None, server=None, synth=None, join=None):
    """Read `script` in the voice of `sample`. Returns {"audio", "passages", "tone"}. `synth(text, path)` and `join(parts, out, speed)`
    can be replaced (tests). Raises ValueError for input problems and RuntimeError when the server fails."""
    if tone not in TONES:
        raise ValueError(f"Unknown tone '{tone}'. Use one of: {', '.join(TONES)}.")
    passages = split_script(script)
    if not passages:
        raise ValueError("The script is empty: give --script with the text to read (or the path of a .txt file).")
    if not sample or not os.path.exists(sample):
        raise ValueError("A recording of your voice is needed: --voiceover sample=my_voice.wav (a clean 10-30 second recording).")
    os.makedirs(session_dir, exist_ok=True)
    out_path = out or os.path.join(session_dir, f"voiceover.{fmt}")
    parts_dir = os.path.join(session_dir, "voiceover_parts")
    os.makedirs(parts_dir, exist_ok=True)
    synth = synth or (lambda text, path: _synth_chunk(text, path, sample, tone, server))
    parts = []
    for i, text in enumerate(passages):
        path = os.path.join(parts_dir, f"part_{i:03d}.mp3")
        try:
            synth(text, path)
        except Exception as e:
            raise RuntimeError(
                f"The voice server could not read passage {i + 1} of {len(passages)} ({e}). Start your local voice server "
                "(VoiceStudio, F5-TTS, XTTS...) and set VOICE_STUDIO_URL, or pass server=http://localhost:PORT.") from e
        if not os.path.exists(path) or os.path.getsize(path) < 200:
            raise RuntimeError(f"The voice server returned no audio for passage {i + 1} of {len(passages)}.")
        parts.append(path)
    speed = TONES[tone]["speed"]
    if join:
        join(parts, out_path, speed)
    else:
        import imageio_ffmpeg
        _join(imageio_ffmpeg.get_ffmpeg_exe(), parts, out_path, speed, session_dir)
    return {"audio": out_path, "passages": len(passages), "tone": tone}
