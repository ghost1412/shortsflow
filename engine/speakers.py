"""Tell the speakers of a video apart by the pitch of their voice, for multi-speaker dubbing.

Deliberately light: numpy and FFmpeg only, everything runs on this PC. It is NOT full diarization: two speakers whose voices sit
at the same pitch end up as one. It separates a man from a woman, or a deep voice from a high one, which is what a dub needs to
give each of them a voice of their own.
"""
import subprocess

SAMPLE_RATE = 16000
MIN_GAP_SEMITONES = 4.0      # two voices closer than this are treated as the same speaker (one person's pitch moves 2-3 semitones)
MIN_LINES = 2                # with 6 or more lines a speaker needs at least this many, else it is an outlier (a shout, a misread pitch)
MALE_BELOW_HZ = 165.0        # a voice whose typical pitch is under this gets a male voice, else a female one
MAX_SPEAKERS = 4


def read_audio(path, ffmpeg=None):
    """The audio of `path` as float32 mono samples at 16 kHz (empty when there is none)."""
    import numpy as np
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    res = subprocess.run([ffmpeg, "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
                         capture_output=True)
    if res.returncode != 0 or not res.stdout:
        return np.zeros(0, dtype="float32")
    return np.frombuffer(res.stdout, dtype="<i2").astype("float32") / 32768.0


def median_pitch(samples, start, end, fmin=70.0, fmax=400.0, max_seconds=8.0):
    """Typical pitch (Hz) of the voiced part of samples[start:end] (seconds), None when nothing in it is clearly voiced."""
    import numpy as np
    end = min(end, start + max_seconds)
    chunk = samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
    frame, hop = int(0.04 * SAMPLE_RATE), int(0.02 * SAMPLE_RATE)
    lo, hi = int(SAMPLE_RATE / fmax), int(SAMPLE_RATE / fmin)
    if len(chunk) < frame:
        return None
    energy_floor = max(0.01, float(np.sqrt((chunk ** 2).mean())) * 0.6)
    window = np.hanning(frame)
    found = []
    for i in range(0, len(chunk) - frame, hop):
        piece = chunk[i:i + frame]
        if float(np.sqrt((piece ** 2).mean())) < energy_floor:
            continue
        piece = (piece - piece.mean()) * window
        spec = np.fft.rfft(piece, 2 * frame)
        ac = np.fft.irfft(spec * np.conj(spec))[:hi + 1]
        if ac[0] <= 0:
            continue
        lag = lo + int(np.argmax(ac[lo:hi + 1]))
        if ac[lag] / ac[0] >= 0.35:                       # clearly periodic = voiced
            found.append(SAMPLE_RATE / lag)
    return float(np.median(found)) if len(found) >= 3 else None


def _semitones(hz):
    import math
    return 12.0 * math.log2(hz / 100.0)


def _kmeans_1d(values, k, rounds=25):
    """(centroids ascending, label per value) for 1-D k-means seeded at evenly spaced quantiles."""
    order = sorted(values)
    cents = [order[min(len(order) - 1, int((j + 0.5) * len(order) / k))] for j in range(k)]
    labels = [0] * len(values)
    for _ in range(rounds):
        labels = [min(range(k), key=lambda c: abs(v - cents[c])) for v in values]
        new = []
        for c in range(k):
            mine = [v for v, lab in zip(values, labels) if lab == c]
            new.append(sum(mine) / len(mine) if mine else cents[c])
        if new == cents:
            break
        cents = new
    ranked = sorted(range(k), key=lambda c: cents[c])
    remap = {old: new for new, old in enumerate(ranked)}
    return [cents[c] for c in ranked], [remap[lab] for lab in labels]


def cluster_pitches(pitches, max_speakers=MAX_SPEAKERS):
    """pitches: Hz per line (None = unknown). Returns (speaker index per line, typical Hz per speaker); speaker 0 is the lowest voice.
    Lines of unknown pitch take the speaker of the line before them; with no pitch at all everything is speaker 0."""
    known = [(i, _semitones(p)) for i, p in enumerate(pitches) if p]
    if not known:
        return [0] * len(pitches), []
    values = [v for _, v in known]
    best_c, best_l = _kmeans_1d(values, 1)
    for k in range(2, max(1, min(max_speakers, len(values))) + 1):
        cents, labels = _kmeans_1d(values, k)
        gaps_ok = all(b - a >= MIN_GAP_SEMITONES for a, b in zip(cents, cents[1:]))
        need = MIN_LINES if len(labels) >= 6 else 1
        shares_ok = all(labels.count(c) >= need for c in range(k))
        if gaps_ok and shares_ok:
            best_c, best_l = cents, labels
    by_line = dict(zip((i for i, _ in known), best_l))
    out, last = [], 0
    for i in range(len(pitches)):
        last = by_line.get(i, last)
        out.append(last)
    hz = [100.0 * 2 ** (c / 12.0) for c in best_c]
    return out, hz


def label_segments(source_video, segments, max_speakers=MAX_SPEAKERS, samples=None):
    """Add a "speaker" number to every segment (0 = lowest voice). Returns (segments, typical Hz per speaker).
    Nothing is changed when only one voice is found (the dub then sounds exactly as before)."""
    samples = read_audio(source_video) if samples is None else samples
    pitches = [median_pitch(samples, s["start"], s["end"]) if len(samples) else None for s in segments]
    labels, hz = cluster_pitches(pitches, max_speakers)
    if len(hz) < 2:
        return segments, hz
    return [dict(s, speaker=lab) for s, lab in zip(segments, labels)], hz


# pitch shift (Hz) given to the 2nd, 3rd... speaker of the same gender so they do not sound alike
SAME_GENDER_SHIFT = (0, 9, -9, 18)


def voice_plan(hz, lang, voices=None):
    """One {voice, pitch_hz} per speaker: a male or female voice of the language by the speaker's pitch; a second speaker of the
    same gender keeps the voice but is shifted in pitch. `voices` = (female_table, male_table), defaults to engine.dubbing's."""
    if voices is None:
        from engine.dubbing import EDGE_VOICES, EDGE_VOICES_MALE
        voices = (EDGE_VOICES, EDGE_VOICES_MALE)
    female, male = voices
    seen = {"male": 0, "female": 0}
    plan = []
    for h in hz:
        gender = "male" if h < MALE_BELOW_HZ else "female"
        table = male if gender == "male" else female
        n = seen[gender]
        seen[gender] += 1
        plan.append({"voice": table.get(lang) or female.get(lang), "pitch_hz": SAME_GENDER_SHIFT[min(n, len(SAME_GENDER_SHIFT) - 1)],
                     "gender": gender})
    return plan
