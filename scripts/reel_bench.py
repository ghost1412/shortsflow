"""Offline highlights-reel benchmark: the quality of each moment of the reel (mode "long") built from a transcript alone.

    python scripts/reel_bench.py                  # no AI, all docs/gold/transcripts, target 240 s
    python scripts/reel_bench.py --ai             # let the AI (whatever keys the machine has) pick; falls back by itself
    python scripts/reel_bench.py --target 180

Per reel: moments, total seconds, how many start / end on a sentence, weak openings, trailing-off ends, moments under 15 s,
jarring jumps (two moments that are close neighbours in the video, cut apart), whether the first moment opens strongly, and
where in the video the reel starts. No video, no render, no network unless --ai.
"""
import argparse
import contextlib
import glob
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


LEGACY = False


def reel(transcript_path, target=240.0, ai=False, min_duration=15):
    """The reel's moments (story order) as process_source_video builds them, without a video."""
    os.environ["SHORTSFLOW_NO_FEEDBACK"] = "1"
    from engine import analysis, script_gen
    original = script_gen.get_llm_response
    if not ai:
        def no_ai(*a, **k):
            raise RuntimeError("no AI in the reel benchmark")
        script_gen.get_llm_response = no_ai
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            hl = analysis.identify_highlights(transcript_path, video_path=None, clip_count=5, mode="long", target_duration=target,
                                              min_duration=min_duration)
            with open(transcript_path, encoding="utf-8") as f:
                transcript = json.load(f)
            hl = _legacy_finish(hl, transcript) if LEGACY else analysis.finish_reel(hl, transcript, target)
    finally:
        script_gen.get_llm_response = original
    return hl, transcript


def _legacy_finish(hl, transcript):
    from engine.highlight_quality import snap_highlights, merge_close_moments
    hl = snap_highlights(hl, transcript, min_len=8.0, max_len=180.0)
    return sorted(merge_close_moments(hl), key=lambda h: float(h["start"]))


def measure(moments, transcript, gap=20.0):
    from engine import highlight_quality as q
    spans = q.sentence_spans(transcript)
    starts = [s for s, _, _ in spans]
    ends = [e for _, e, _ in spans]
    total_video = max(ends) if ends else 1.0
    ms = sorted(moments, key=lambda h: float(h["start"]))
    r = {"moments": len(ms), "seconds": round(sum(h["end"] - h["start"] for h in ms)), "start_ok": 0, "end_ok": 0, "weak_open": 0, "bad_open": 0,
         "boiler": 0, "trails": 0, "short": 0, "jumps": 0}
    for h in ms:
        s, e = float(h["start"]), float(h["end"])
        r["start_ok"] += any(abs(s - x) < 0.3 for x in starts)
        r["end_ok"] += any(0 <= x - e < 0.6 or 0 <= e - x < 0.6 for x in ends)
        txt = [t for a, b, t in spans if a >= s - 0.05 and b <= e + 0.05]
        if txt and q.weak_opening(txt[0]):
            r["weak_open"] += 1
        r["bad_open"] += bool(txt) and q.bad_opener(txt[0]) if hasattr(q, "bad_opener") else bool(txt) and (
            q.weak_opening(txt[0]) or q.boilerplate_hits(txt[0]) > 0 or q.disfluency(txt[0]) > 0.35)
        if txt and q.trails_off_end(txt[-1]):
            r["trails"] += 1
        r["short"] += (e - s) < 15
    r["jumps"] = sum(1 for a, b in zip(ms, ms[1:]) if 0 < float(b["start"]) - float(a["end"]) < gap)
    if ms:
        first = ms[0]
        t = [x for a, b, x in spans if a >= float(first["start"]) - 0.05 and b <= float(first["end"]) + 0.05]
        r["open_hook"] = bool(t) and q.has_hook_cue(t[0]) and not q.weak_opening(t[0]) and not q.boilerplate_hits(" ".join(t[:2]))
        r["first_at_pct"] = round(100 * float(first["start"]) / total_video)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, "docs", "gold", "transcripts"))
    ap.add_argument("--target", type=float, default=240.0)
    ap.add_argument("--ai", action="store_true")
    ap.add_argument("--legacy", action="store_true", help="the old finish (snap + merge at 3 s only), to compare")
    a = ap.parse_args()
    global LEGACY
    LEGACY = a.legacy
    for path in sorted(glob.glob(os.path.join(a.dir, "*.json"))):
        hl, tr = reel(path, a.target, a.ai)
        print(os.path.basename(path)[:-5].ljust(16), json.dumps(measure(hl, tr)))


if __name__ == "__main__":
    main()
