"""Sentence-window candidates (engine/candidates.py): clips that start and end on sentences, ranked without an AI."""
from engine import candidates as c


def _spans(n=40, length=5.0, texts=None):
    return [(i * length, i * length + length - 0.2, (texts or {}).get(i, f"This is plain sentence number {i} of the talk.")) for i in range(n)]


def test_every_candidate_starts_and_ends_on_a_sentence_and_is_near_the_asked_length():
    spans = _spans()
    starts, ends = {s[0] for s in spans}, {s[1] for s in spans}
    cands = c.build_candidates(spans, 30.0, min_len=15.0)
    assert cands and all(x["start"] in starts and x["end"] in ends for x in cands)
    assert all(15.0 <= x["end"] - x["start"] <= 59.9 for x in cands)
    assert abs((cands[0]["end"] - cands[0]["start"]) - 30.0) <= 5.0


def test_a_clip_does_not_open_on_a_one_word_sentence():
    spans = _spans(texts={3: "Great.", 4: "..."})
    firsts = {x["first"] for x in c.build_candidates(spans, 30.0)}
    assert "Great." not in firsts and "..." not in firsts


def test_an_answer_starts_at_its_short_question():
    spans = _spans(texts={5: "Why did the battery last so long?"})
    assert c.answer_starts(spans) == {6}
    cands = c.build_candidates(spans, 30.0)
    answer = [x for x in cands if x["answer"]]
    assert len(answer) == 1 and answer[0]["start"] == spans[5][0] and answer[0]["first"].endswith("?")
    assert not any(x["start"] == spans[6][0] for x in cands)                 # the answer alone is not offered a second time
    long_question = _spans(texts={5: "Why?"})
    long_question[5] = (25.0, 33.0, "Why did it last?")                      # an 8 s question is not a lead-in
    assert c.answer_starts(long_question) == set()


def test_score_uses_the_covered_windows_the_opening_line_and_the_payoff():
    windows = [{"start": 0, "end": 30, "norm_score": 0.2, "norm_audio": 0.0}, {"start": 30, "end": 60, "norm_score": 0.8, "norm_audio": 0.4}]
    quiet = {"start": 0.0, "end": 30.0, "first": "x", "last": "It was fine.", "text": "x", "answer": False}
    loud = dict(quiet, start=30.0, end=60.0)
    assert c.score_candidate(loud, windows) > c.score_candidate(quiet, windows)
    assert c.score_candidate(dict(quiet, last="It lasted 9 days."), windows) == round(c.score_candidate(quiet, windows) + c.PAYOFF_BONUS, 4)
    assert c.score_candidate(dict(quiet, answer=True), windows) == round(c.score_candidate(quiet, windows) + c.ANSWER_BONUS, 4)
    assert c.score_candidate(quiet, windows, opening_rank=lambda t: -0.3) < c.score_candidate(quiet, windows)


def test_select_keeps_the_best_apart_and_never_overlaps():
    cands = [{"start": 0, "end": 30, "score": 1.0}, {"start": 20, "end": 50, "score": 0.9}, {"start": 40, "end": 70, "score": 0.8},
             {"start": 200, "end": 230, "score": 0.5}]
    assert [x["start"] for x in c.select(cands, 2)] == [0, 200]              # 40-70 is closer than 30 s to the best one
    assert [x["start"] for x in c.select(cands, 3)] == [0, 200, 40]          # near neighbours only when needed, never overlapping
    assert c.select(cands, 3) == c.select(list(reversed(cands)), 3)          # repeatable


def test_pick_returns_scored_highlights_best_first_and_nothing_for_an_empty_transcript():
    segs = [{"start": s, "end": e, "text": t} for s, e, t in _spans(60)]
    windows = [{"start": i * 45.0, "end": i * 45.0 + 45.0, "norm_score": 0.1 * (i % 7), "norm_audio": 0.0} for i in range(7)]
    picks = c.pick({"segments": segs}, windows, 3, 30.0)
    assert len(picks) == 3 and picks == sorted(picks, key=lambda h: -h["final_score"])
    assert all({"start", "end", "viral_score", "final_score", "reason"} <= set(h) for h in picks)
    assert c.pick({"segments": []}, windows, 3, 30.0) == []


def test_the_signal_picker_uses_sentence_windows_only_when_switched_on(monkeypatch):
    from engine import analysis
    segs = [{"start": s, "end": e, "text": t} for s, e, t in _spans(60)]
    windows = [{"start": i * 45.0, "end": i * 45.0 + 45.0, "text": "plain talk here", "norm_score": 0.1 * (i % 7), "norm_audio": 0.0} for i in range(7)]
    monkeypatch.delenv("SHORTSFLOW_SENTENCE_WINDOWS", raising=False)
    old = analysis.signal_picks([dict(w) for w in windows], "shorts", 2, 30.0, 15.0, transcript={"segments": segs})
    assert all("sentence window" not in h["reason"] for h in old)
    monkeypatch.setenv("SHORTSFLOW_SENTENCE_WINDOWS", "1")
    new = analysis.signal_picks([dict(w) for w in windows], "shorts", 2, 30.0, 15.0, transcript={"segments": segs})
    assert len(new) == 2 and all("sentence window" in h["reason"] for h in new)
