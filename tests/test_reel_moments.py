"""Quality of each highlights-reel moment (engine/highlight_quality.py: polish_reel and its steps). Offline, no AI."""
from engine import highlight_quality as q


def make_transcript(sentences, step=5.0):
    """One sentence every `step` seconds, 4 s long each: [(text)] -> a Whisper-like transcript with word times."""
    segs = []
    for i, text in enumerate(sentences):
        start = i * step
        words = text.split()
        per = 4.0 / len(words)
        segs.append({"start": start, "end": start + 4.0, "text": " " + text,
                     "words": [{"word": " " + w, "start": start + k * per, "end": start + (k + 1) * per} for k, w in enumerate(words)]})
    return {"language": "en", "segments": segs}


PLAIN = "The telescope measured the star again and the number was higher."


def moment(start, end, score=50):
    return {"start": float(start), "end": float(end), "final_score": score, "viral_score": score}


def spans_of(sentences):
    return q.sentence_spans(make_transcript(sentences))


def total(ms):
    return sum(m["end"] - m["start"] for m in ms)


def test_close_neighbours_become_one_moment():
    tr = make_transcript([PLAIN + f" Part {i}." for i in range(60)])
    out = q.polish_reel([moment(0, 40), moment(50, 90), moment(200, 240)], tr)       # 10 s apart, then a long way apart
    assert [(round(m["start"]), round(m["end"])) for m in out][-1][0] == 200
    assert len(out) == 2 and out[0]["end"] >= 90


def test_a_moment_that_opens_on_housekeeping_starts_on_the_next_real_sentence():
    sentences = ["Thank you very much.", "Thank you.", "So the thing is this."] + [PLAIN + f" Bit {i}." for i in range(40)]
    spans = spans_of(sentences)
    out = q.clean_reel_openings([moment(0, 60), moment(100, 160)], spans)
    assert out[0]["start"] > 0
    assert not q.bad_opener(q._first_sentence(out[0], spans)) or q.boilerplate_hits(q._first_sentence(out[0], spans)) == 0
    assert out[1]["start"] == 100


def test_a_moment_that_is_all_housekeeping_is_dropped_but_never_the_last_two():
    sentences = ["Please call station for a voice check."] * 12 + [PLAIN + f" Bit {i}." for i in range(30)]
    spans = spans_of(sentences)
    out = q.clean_reel_openings([moment(0, 30), moment(100, 140), moment(150, 190)], spans)
    assert [m["start"] for m in out] == [100.0, 150.0]
    two = q.clean_reel_openings([moment(0, 30), moment(100, 140)], spans)
    assert len(two) == 2


def test_a_too_long_reel_is_trimmed_on_sentence_ends_and_a_too_short_one_grows_on_them():
    tr = make_transcript([PLAIN + f" Bit {i}." for i in range(120)])
    spans = q.sentence_spans(tr)
    ends = [e for _, e, _ in spans]
    long_reel = [moment(0, 100), moment(200, 300), moment(400, 500)]            # 300 s for a 200 s target
    out = q.fit_reel_length(long_reel, spans, 200.0)
    assert 184 <= total(out) <= 216 + 1
    short_reel = [moment(0, 50), moment(200, 250), moment(400, 450)]            # 150 s for a 200 s target
    out2 = q.fit_reel_length(short_reel, spans, 200.0)
    assert total(out2) > 150 and total(out2) <= 216 + 1
    for m in [m for m in out + out2 if m["end"] not in (100.0, 300.0, 500.0, 50.0, 250.0, 450.0)]:      # an end that moved
        assert any(0 <= m["end"] - e <= 0.45 for e in ends)                      # still ends on a sentence end (plus the short tail)
    assert all(a["end"] <= b["start"] for a, b in zip(out2, out2[1:]))


def test_growing_never_runs_into_housekeeping_or_a_trailing_off_sentence():
    sentences = [PLAIN] * 12 + ["Thanks for watching, see you next time."] * 10 + [PLAIN] * 40
    spans = spans_of(sentences)
    out = q.fit_reel_length([moment(0, 60), moment(400, 440)], spans, 200.0)
    assert out[0]["end"] <= 61.0 and q.boilerplate_hits(" ".join(t for a, b, t in spans if a >= 60 and b <= out[0]["end"])) == 0


def test_a_moment_the_user_chose_is_left_alone():
    tr = make_transcript(["Thank you very much."] * 5 + [PLAIN] * 60)
    mine = dict(moment(0, 20), user_moment=True)
    out = q.polish_reel([mine, moment(150, 200)], tr, 400.0)
    assert out[0]["start"] == 0.0 and out[0]["end"] == 20.0


def test_polish_reel_with_no_transcript_text_returns_the_moments_unchanged():
    moments = [moment(0, 40), moment(100, 140)]
    assert q.polish_reel(moments, {"segments": []}, 100.0) == moments
