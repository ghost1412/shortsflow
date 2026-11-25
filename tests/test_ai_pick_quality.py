"""The AI-proposed clips are checked by the same opening / fragment rule as the no-AI picks (offline: no model, no network)."""
import json

from engine import analysis
from engine import highlight_rank as hr
from engine.highlight_quality import sentence_spans


def _t(sentences, gap=0.6, wd=0.3):
    t, segs = 0.0, []
    for text in sentences:
        words, s = [], t
        for w in text.split():
            words.append({"word": " " + w, "start": round(t, 2), "end": round(t + wd, 2)})
            t += wd + 0.02
        segs.append({"start": round(s, 2), "end": round(words[-1]["end"], 2), "text": text, "words": words})
        t += gap
    return {"segments": segs}


CLEAN = [f"Why does thing number {i} work the way it does in practice today?" for i in range(8)]
FRAGMENTS = ["...you can do... ...new... ...for example... ...the... ...the... ...also... ...so this is... ...from..."] * 8


def _write(tmp_path, sentences):
    tr = _t(sentences)
    path = tmp_path / "t.json"
    path.write_text(json.dumps(tr), encoding="utf-8")
    return tr, str(path)


def test_fragment_clip_is_set_aside_and_clean_one_kept(tmp_path):
    tr, _ = _write(tmp_path, CLEAN + FRAGMENTS)
    sp = sentence_spans(tr)
    clean = {"start": sp[0][0], "end": sp[6][1], "final_score": 70}
    frag = {"start": sp[9][0], "end": sp[15][1], "final_score": 80}
    kept, aside = analysis.split_unwatchable([clean, frag], tr)
    assert kept == [clean] and aside == [frag]


def test_user_moments_and_empty_text_are_never_set_aside(tmp_path):
    tr, _ = _write(tmp_path, CLEAN + FRAGMENTS)
    sp = sentence_spans(tr)
    mine = {"start": sp[9][0], "end": sp[15][1], "final_score": 80, "user_moment": True}
    nothing = {"start": 900.0, "end": 930.0, "final_score": 50}
    kept, aside = analysis.split_unwatchable([mine, nothing], tr)
    assert len(kept) == 2 and aside == []


def test_quality_adjustment_lowers_fragments_once_and_skips_signal_picks(tmp_path):
    tr, path = _write(tmp_path, CLEAN + FRAGMENTS)
    sp = sentence_spans(tr)
    frag = {"start": sp[9][0], "end": sp[15][1], "final_score": 80, "viral_score": 80}
    backfill = dict(frag, reason="Energy Peak (Backfill)")
    out = analysis.apply_clip_quality([frag, backfill], path)
    assert out[0]["final_score"] < 80 and out[0]["quality_adjusted"]
    assert out[1]["final_score"] == 80                           # already ranked by the rule
    again = analysis.apply_clip_quality(out, path)
    assert again[0]["final_score"] == out[0]["final_score"]      # adjusted once


def test_choose_from_pool_puts_the_clean_clip_before_the_better_scored_fragments(tmp_path):
    tr, path = _write(tmp_path, CLEAN + FRAGMENTS)
    sp = sentence_spans(tr)
    clean = {"start": sp[0][0], "end": sp[6][1], "final_score": 62, "viral_score": 62}
    frag = {"start": sp[9][0], "end": sp[15][1], "final_score": 80, "viral_score": 80}
    picks = analysis.choose_from_pool([frag, clean], path, 1, 15, snap=False)
    assert picks[0]["start"] == clean["start"]


def test_failure_to_read_the_transcript_leaves_the_clips_alone(tmp_path):
    clips = [{"start": 0.0, "end": 30.0, "final_score": 50}]
    assert analysis.apply_clip_quality(clips, str(tmp_path / "missing.json")) == clips


def test_rerank_extension_stays_within_25_percent_of_the_target():
    tr = _t([f"Sentence number {i} says something fairly interesting about topic {i}." for i in range(20)])
    sp = sentence_spans(tr)
    h = {"start": sp[2][0], "end": sp[5][1]}
    info = {"extend_end": 2, "trim_start": 0}
    _, wide = hr._adjust_edges(h, sp, info)
    length = sp[5][1] - sp[2][0]
    _, capped = hr._adjust_edges(h, sp, info, target=length)
    assert wide > h["end"]                                       # without a target the model's extension is taken
    assert capped - h["start"] <= 1.25 * length + 1e-6
