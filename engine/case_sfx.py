"""Small synthesised sound effects for the case explainer: a soft whoosh when a section starts and a quiet pop as each label appears.

Made with numpy, nothing downloaded and nothing licensed. `build_track` returns a stereo wav the length of the video that
`case_render.join_audio` mixes in under the narrator.
"""
import wave

import numpy as np

SR = 44100


def whoosh(seconds=0.9, seed=3):
    """A band of noise whose cut-off sweeps up and fades: float32 mono."""
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    # one-pole low-pass whose coefficient rises over the sound (a rising sweep)
    out = np.empty(n, dtype=np.float32)
    y = 0.0
    for i in range(n):
        a = 0.02 + 0.5 * (i / n)
        y += a * (noise[i] - y)
        out[i] = y
    env = np.sin(np.pi * np.linspace(0, 1, n, dtype=np.float32)) ** 2
    out *= env
    peak = float(np.max(np.abs(out))) or 1.0
    return out / peak


def pop(seconds=0.22, freq=740.0):
    """A short soft blip: a sine with a fast decay, float32 mono."""
    n = int(seconds * SR)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.sin(2 * np.pi * freq * t) * np.exp(-t * 22)
    out += 0.3 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 30)
    return (out / (float(np.max(np.abs(out))) or 1.0)).astype(np.float32)


def build_track(path, total_seconds, section_starts, label_times, whoosh_gain=0.5, pop_gain=0.28):
    """Write a wav with a whoosh at every section start and a pop at every label time (seconds from the start). Returns path."""
    total = int((total_seconds + 1) * SR)
    mix = np.zeros(total, dtype=np.float32)
    sweep, blip = whoosh() * whoosh_gain, pop() * pop_gain
    for t in section_starts:
        s = max(0, int((t - 0.35) * SR))          # the whoosh leads into the new section
        m = min(len(sweep), total - s)
        if m > 0:
            mix[s:s + m] += sweep[:m]
    for t in label_times:
        s = int(t * SR)
        m = min(len(blip), total - s)
        if s >= 0 and m > 0:
            mix[s:s + m] += blip[:m]
    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.95:
        mix *= 0.95 / peak
    pcm = (np.stack([mix, mix], axis=1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
