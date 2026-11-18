"""A light, calm background track made on the PC: soft pads and a gentle plucked pattern over a slow four-chord loop.

Nothing is downloaded and nothing is licensed: the notes are synthesised here, so the track is free to use in any video. It is meant
to sit under a narrator at a low volume. `ensure_track` writes it once (an mp3 in the cache folder) and reuses it.
"""
import os
import subprocess
import shutil
import wave

import numpy as np

SR = 44100
BPM = 72
# Cmaj7, Am7, Fmaj7, G6 as MIDI notes (pad voicing) and the notes the pluck pattern walks through
CHORDS = [([48, 55, 59, 64], [67, 71, 74, 79]), ([45, 52, 55, 60], [64, 67, 72, 76]),
          ([41, 48, 52, 57], [65, 69, 72, 76]), ([43, 50, 55, 59], [67, 71, 74, 79])]
PATTERN = [0, 1, 2, 1, 3, 2, 1, 2]       # eighth notes over the chord's pluck notes


def _hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def _envelope(n, attack, release):
    env = np.ones(n, dtype=np.float32)
    a, r = min(n, int(attack * SR)), min(n, int(release * SR))
    if a:
        env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    if r:
        env[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return env


def render(seconds=180.0, seed=7):
    """Stereo float32 array (n, 2) of the track, about -3 dB peak, ending with a fade."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / BPM
    bar = 4 * beat
    total = int(seconds * SR)
    left = np.zeros(total, dtype=np.float32)
    right = np.zeros(total, dtype=np.float32)
    t_bar = 0
    bars = int(seconds / bar) + 1
    for b in range(bars):
        pad, pluck = CHORDS[b % len(CHORDS)]
        start = int(b * bar * SR)
        if start >= total:
            break
        n = min(int((bar + 1.2) * SR), total - start)
        t = np.arange(n, dtype=np.float32) / SR
        env = _envelope(n, 1.1, 1.4)
        for note in pad:
            f = _hz(note)
            tone = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.003 * t) + 0.12 * np.sin(2 * np.pi * f * 3.01 * t)) * env
            tone *= 0.05
            left[start:start + n] += tone
            right[start:start + n] += tone
        for k in range(8):
            note = pluck[PATTERN[k] % len(pluck)] - (12 if (b + k) % 5 == 0 else 0)
            s = start + int(k * beat / 2 * SR)
            m = min(int(1.6 * SR), total - s)
            if m <= 0:
                continue
            tt = np.arange(m, dtype=np.float32) / SR
            f = _hz(note)
            tone = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2 * tt) + 0.15 * np.sin(2 * np.pi * f * 3 * tt)) * np.exp(-tt * 3.2)
            tone *= 0.07 * (0.8 + 0.2 * rng.random())
            pan = 0.35 + 0.3 * ((k % 4) / 3)
            left[s:s + m] += tone * (1 - pan)
            right[s:s + m] += tone * pan
        t_bar += 1
    out = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(out))) or 1.0
    out *= 0.7 / peak                                     # peak about -3 dB; the video lowers it under the voice
    fade = min(total, int(4 * SR))
    out[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return out


def write_mp3(path, seconds=180.0, seed=7, ffmpeg=None):
    """Render and encode to `path` (mp3). A soft echo and a low-pass are added by FFmpeg. Returns path."""
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if not ffmpeg:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wav = path + ".tmp.wav"
    pcm = (render(seconds, seed) * 32767).astype(np.int16)
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    try:
        res = subprocess.run([ffmpeg, "-y", "-i", wav, "-af", "lowpass=f=5200,aecho=0.8:0.6:80|190:0.35|0.22", "-c:a", "libmp3lame", "-b:a", "128k", path],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError("Encoding the music failed: " + (res.stderr or "")[-300:])
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    return path


def ensure_track(cache_dir=None, seconds=180.0):
    """The path of the light track, written on the first call."""
    cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".shortsflow", "music")
    path = os.path.join(cache_dir, f"light_ambient_{int(seconds)}.mp3")
    if not os.path.exists(path):
        write_mp3(path, seconds)
    return path
