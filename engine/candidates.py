"""Candidate moments for shorts picked without an AI: every candidate starts where a sentence starts and ends where one ends.

The signal picker used to rank fixed time windows (1.5x the asked length) and cut the best ones to length from the window start, so a
clip began wherever a window happened to begin and stopped mid-thought until snapping repaired it. Here every sentence start is a
possible clip start; the clip runs to the sentence end nearest the asked length; and a candidate is ranked by the signals of the windows
it covers plus how ITS first sentence opens (not the window's) and whether it lands on a payoff. Pure functions: no I/O, no AI.
"""
import re

ANSWER_BONUS = 0.15       # the clip opens with a short question and its answer
PAYOFF_BONUS = 0.10        # the last sentence holds a number, a contrast or a conclusion word
MIN_OPENING_WORDS = 4      # a clip does not start on a sentence shorter than this
QUESTION_MAX = 6.0         # a question longer than this is not used as a lead-in
QUESTION_GAP = 1.5         # the answer must follow the question within this many seconds
PAYOFF = re.compile(r"\d|\b(but|instead|actually|turns out|that's why|which is why|so that|the point is|in the end|finally|because)\b", re.I)


def answer_starts(spans):
    """Indexes of sentences that answer a short question asked just before them (the previous sentence ends with "?", is at most
    QUESTION_MAX seconds long and stops at most QUESTION_GAP seconds earlier). `spans` = [(start, end, text)] in order."""
    out = set()
    for i in range(1, len(spans)):
        q_start, q_end, q_text = spans[i - 1]
        if str(q_text).rstrip("\"')] ").endswith("?") and q_end - q_start <= QUESTION_MAX and spans[i][0] - q_end <= QUESTION_GAP \
                and not str(spans[i][2]).rstrip("\"')] ").endswith("?"):
            out.add(i)
    return out


def build_candidates(spans, target, min_len=15.0, max_len=59.9):
    """One candidate per sentence start: from that sentence to the sentence end nearest `target` seconds, never shorter than `min_len`
    or longer than `max_len` (a start with no such end is skipped). A sentence that answers a short question starts at the question.
    Returns [{"start", "end", "first", "last", "text", "answer"}] in time order; "first" / "last" are the opening and closing sentences."""
    target = float(target or 30.0)
    min_len = min(float(min_len), target)
    answers = answer_starts(spans)
    out, seen = [], set()
    for i in range(len(spans)):
        if i + 1 in answers:
            continue                                   # the question itself: it is used as the lead-in of its answer
        if len(re.findall(r"\w+", str(spans[i][2]))) < MIN_OPENING_WORDS:
            continue                                   # "Great.", "Thanks.", "...": nothing to open a clip on
        first = i - 1 if i in answers else i
        start = spans[first][0]
        best = None
        for j in range(i, len(spans)):
            length = spans[j][1] - start
            if length > max_len:
                break
            if length >= min_len and (best is None or abs(length - target) < abs(spans[best][1] - start - target)):
                best = j
        if best is None or (first, best) in seen:
            continue
        seen.add((first, best))
        out.append({"start": round(float(start), 2), "end": round(float(spans[best][1]), 2),
                    "first": str(spans[first][2]).strip(), "last": str(spans[best][2]).strip(),
                    "text": " ".join(str(s[2]).strip() for s in spans[first:best + 1]), "answer": i in answers})
    return out


def _covered(candidate, windows, key):
    """Mean of a window signal over the candidate, weighted by how long each window overlaps it (0 when nothing overlaps)."""
    total, weight = 0.0, 0.0
    for w in windows:
        overlap = min(candidate["end"], float(w["end"])) - max(candidate["start"], float(w["start"]))
        if overlap > 0:
            total += overlap * float(w.get(key, 0) or 0)
            weight += overlap
    return total / weight if weight else 0.0


def score_candidate(candidate, windows, opening_rank=None):
    """Rank value of a candidate (higher is better): the text, loudness and motion signals of the windows it covers, plus how its own
    first sentence opens (`opening_rank(text)`: hook cue minus filler / mic-check / housekeeping penalties), a bonus for a
    question-and-answer opening and one for a closing sentence that lands on something."""
    score = _covered(candidate, windows, "norm_score") + _covered(candidate, windows, "norm_audio") + _covered(candidate, windows, "norm_motion")
    if opening_rank is not None:
        score += opening_rank(candidate["first"]) + min(0.0, opening_rank(candidate["text"]))     # the whole clip's housekeeping talk counts against it
    if candidate.get("answer"):
        score += ANSWER_BONUS
    if PAYOFF.search(candidate.get("last", "")):
        score += PAYOFF_BONUS
    return round(score, 4)


def select(candidates, n, min_gap=30.0):
    """The best `n` candidates by "score" that do not overlap and sit at least `min_gap` seconds apart, so two clips are not one scene
    cut in half; only when that cannot fill `n` are near neighbours accepted (still never overlapping). Best first."""
    ranked = sorted(candidates, key=lambda c: (-c.get("score", 0.0), c["start"]))
    out = []
    for gap in (float(min_gap), 0.0):
        for c in ranked:
            if len(out) >= n:
                return out
            if all(c["end"] + gap <= o["start"] or c["start"] >= o["end"] + gap for o in out):
                out.append(c)
    return out


def pick(transcript, windows, n, target, min_len=15.0, opening_rank=None):
    """Sentence-window picks as highlights, best first: [{"start", "end", "viral_score", "final_score", "reason"}], [] when the
    transcript gives no usable sentences (the caller then falls back to the time windows)."""
    from engine.highlight_quality import sentence_spans
    spans = sentence_spans(transcript)
    candidates = build_candidates(spans, target, min_len=min_len)
    for c in candidates:
        c["score"] = score_candidate(c, windows, opening_rank)
    out = []
    for c in select(candidates, n):
        value = int(max(0.0, c["score"]) * 50)
        out.append({"start": c["start"], "end": c["end"], "viral_score": value, "final_score": value,
                    "reason": "High-Signal Moment (question and answer)" if c["answer"] else "High-Signal Moment (sentence window)"})
    return out
