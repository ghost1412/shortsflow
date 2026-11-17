"""Offline picker benchmark: which moments does the picker choose from a transcript alone, and how many gold moments does it find?

    python scripts/picker_bench.py                       # all transcripts in docs/gold/transcripts against docs/gold/<name>.json
    python scripts/picker_bench.py --suffix _human       # against docs/gold/<name>_human.json (moments a person picked)
    python scripts/picker_bench.py --k 5 8 --clips 5 --target 30

No video, no AI, no network: it runs in seconds, so a change to the picking rules can be measured before every commit. Because there is
no video, the loudness and motion signals are not used; the Clip Benchmark workflow (.github/workflows/clip_benchmark.yml) stays the
full measure. The AI is switched off inside this process, whatever keys the machine has.
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


def pick(transcript_path, clips=5, target=30.0, min_duration=15.0, quiet=True):
    """The ranked candidate pool (best first) the no-AI picker builds from one transcript, as process_source_video does for shorts."""
    os.environ["SHORTSFLOW_NO_FEEDBACK"] = "1"          # this machine's like / dislike history must not move the numbers
    from engine import analysis, script_gen
    original = script_gen.get_llm_response
    script_gen.get_llm_response = lambda *a, **k: None   # no AI: the signal picker answers
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out if quiet else sys.stdout), contextlib.redirect_stderr(out if quiet else sys.stderr):
            pool = analysis.identify_highlights(transcript_path, video_path=None, clip_count=min(10, clips * 2), mode="shorts",
                                                target_duration=target, min_duration=min_duration)
            with open(transcript_path, encoding="utf-8") as f:
                pool = analysis.llm_score_highlights(pool, json.load(f))
            ranked = analysis.choose_from_pool(pool, transcript_path, len(pool), min_duration)      # snapped, too-short ones dropped
    finally:
        script_gen.get_llm_response = original
    return sorted(ranked, key=lambda h: float(h.get("final_score", h.get("viral_score", 0)) or 0), reverse=True)


def bench(transcripts_dir, gold_dir, suffix="", ks=(5, 8), clips=5, target=30.0):
    """One row per transcript: {"video", "pool", "recall", "precision", "recall@k"...} (the scores are None without a gold file)."""
    from engine import clip_quality
    rows = []
    for path in sorted(glob.glob(os.path.join(transcripts_dir, "*.json"))):
        name = os.path.splitext(os.path.basename(path))[0]
        gold_path = os.path.join(gold_dir, f"{name}{suffix}.json")
        gold = None
        if os.path.isfile(gold_path):
            with open(gold_path, encoding="utf-8") as f:
                gold = next(iter(json.load(f).values()), None)        # one video per gold file
        ranked = pick(path, clips=clips, target=target)
        row = {"video": name, "pool": len(ranked)}
        row.update(clip_quality.gold_scores(ranked[:clips], gold))
        for k in ks:
            row[f"recall@{k}"] = clip_quality.recall_at(ranked, gold, k)
        rows.append(row)
    return rows


def mean_row(rows):
    out = {"video": "MEAN", "pool": ""}
    for key in [k for k in rows[0] if k not in ("video", "pool")]:
        vals = [r[key] for r in rows if r.get(key) is not None]
        out[key] = round(sum(vals) / len(vals), 3) if vals else None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transcripts", default=os.path.join(ROOT, "docs", "gold", "transcripts"))
    ap.add_argument("--gold", default=os.path.join(ROOT, "docs", "gold"), help="folder with <name><suffix>.json gold files")
    ap.add_argument("--suffix", default="", help='gold file suffix, e.g. "_human"')
    ap.add_argument("--k", type=int, nargs="+", default=[5, 8])
    ap.add_argument("--clips", type=int, default=5)
    ap.add_argument("--target", type=float, default=30.0)
    ap.add_argument("--json", help="also write the rows here")
    a = ap.parse_args(argv)
    rows = bench(a.transcripts, a.gold, a.suffix, tuple(a.k), a.clips, a.target)
    if not rows:
        print(f"No transcripts in {a.transcripts}")
        return 1
    rows.append(mean_row(rows))
    cols = list(rows[0])
    cells = [[("-" if r.get(c) is None else str(r.get(c))) for c in cols] for r in rows]
    widths = [max(len(c), *(len(x[i]) for x in cells)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for line in cells:
        print("  ".join(x.ljust(w) for x, w in zip(line, widths)))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
