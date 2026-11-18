"""The offline picker benchmark (scripts/picker_bench.py): transcript in, ranked moments and recall out; no video, no AI."""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("picker_bench", os.path.join(ROOT, "scripts", "picker_bench.py"))
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)


def _transcript(path, minutes=6):
    segs, t = [], 0.0
    for i in range(minutes * 12):
        text = f" Sentence number {i} explains why the battery lasted {i + 2} days longer than anyone expected."
        words = [{"word": " " + w, "start": round(t + j * 0.3, 2), "end": round(t + j * 0.3 + 0.25, 2)} for j, w in enumerate(text.split())]
        segs.append({"start": t, "end": round(t + 4.8, 2), "text": text, "words": words})
        t += 5.0
    path.write_text(json.dumps({"language": "en", "segments": segs}), encoding="utf-8")


def test_pick_is_repeatable_and_never_calls_the_ai(tmp_path, monkeypatch):
    from engine import script_gen
    monkeypatch.setattr(script_gen, "get_llm_response", lambda *a, **k: (_ for _ in ()).throw(AssertionError("AI was called")))
    t = tmp_path / "talk.json"
    _transcript(t)
    first, second = pb.pick(str(t)), pb.pick(str(t))
    assert first and [(h["start"], h["end"]) for h in first] == [(h["start"], h["end"]) for h in second]
    assert all(float(h["end"]) > float(h["start"]) for h in first)
    assert script_gen.get_llm_response.__name__ == "<lambda>"    # put back


def test_bench_scores_each_transcript_against_its_gold_file(tmp_path):
    tdir, gdir = tmp_path / "t", tmp_path / "g"
    tdir.mkdir(), gdir.mkdir()
    _transcript(tdir / "talk.json")
    best = pb.pick(str(tdir / "talk.json"))[0]
    (gdir / "talk.json").write_text(json.dumps({"video.webm": [[best["start"], best["end"]], [9000, 9030]]}), encoding="utf-8")
    rows = pb.bench(str(tdir), str(gdir))
    assert rows[0]["video"] == "talk" and rows[0]["recall"] == 0.5 and rows[0]["recall@8"] == 0.5
    assert pb.bench(str(tdir), str(gdir), suffix="_human")[0]["recall"] is None        # no such gold file: no score, no crash
    assert pb.mean_row(rows)["recall"] == 0.5


def test_the_committed_transcripts_have_a_gold_file_each():
    names = [os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "docs", "gold", "transcripts")) if f.endswith(".json")]
    assert names and all(os.path.isfile(os.path.join(ROOT, "docs", "gold", n + ".json")) for n in names)
