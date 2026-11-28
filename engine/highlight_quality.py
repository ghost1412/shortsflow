"""Boundary snapping for highlight clips.

The LLM (or the heuristic fallback) picks a start and an end in seconds, usually from a coarse window of the transcript, so
clips often begin in the middle of a sentence ("...and that's why") or stop before the payoff. This module moves each edge
to a sentence boundary taken from the word-timed transcript, trims a leading filler sentence ("So, um, okay."), and keeps a
short tail after the last word so the clip does not end on a hard cut.

Pure functions, no I/O: they work on the transcript dict Whisper writes (segments with `words`), and degrade to segment
level when there are no word timestamps, and to "leave the clip alone" when there is nothing usable.
"""
import re

SENTENCE_END = re.compile(r"[.!?…。！？।]+[\"')\]」』]*$")
# a trailing dot that does NOT end a sentence
NOT_END = {"mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "u.s."}
FILLER_WORDS = {"so", "um", "uh", "er", "erm", "hmm", "well", "okay", "ok", "like", "and", "but", "yeah", "right", "alright",
                "now", "then", "anyway", "you", "know", "basically", "actually", "i", "mean"}
PAUSE_SPLIT = 0.9          # a silence this long between two words also separates sentences (Whisper often omits punctuation)
LONG_PAUSE = 2.5           # where the transcript IS punctuated, a shorter silence inside a sentence is only the speaker taking a breath
MAX_JOINED = 20.0          # ... but a "sentence" is not carried over a pause past this many seconds

DEFAULTS = {
    "max_shift": 6.0,      # move an edge by at most this many seconds when a boundary is that close
    "long_shift": 20.0,    # inside a long sentence with no boundary that close: up to this far, if the clip stays a short
    "tail": 0.4,           # seconds kept after the last word of the clip
    "min_len": 8.0,        # a snapped clip shorter than this is dropped back to the original
    "max_len": 59.9,       # shorts stay under a minute
    "leadin_max_words": 5,
    "target": None,        # the length the clip was asked for, in seconds: finishing a sentence may not run past 25% over it when the sentence before fits
    "skip_shift": 20.0,    # skip a weak opening sentence (mic check, "And ...") when the next sentence starts within this many seconds
}


def _words(transcript):
    """Flat [{word, start, end}] from the transcript; segment text stands in when a segment has no word timings."""
    out = []
    for seg in (transcript or {}).get("segments", []):
        words = seg.get("words") or []
        usable = [w for w in words if isinstance(w, dict) and "start" in w and "end" in w and str(w.get("word", "")).strip()]
        if usable:
            out.extend({"word": str(w["word"]).strip(), "start": float(w["start"]), "end": float(w["end"])} for w in usable)
        elif str(seg.get("text", "")).strip():
            out.append({"word": str(seg["text"]).strip(), "start": float(seg.get("start", 0)), "end": float(seg.get("end", 0)),
                        "segment": True})
    return out


def sentence_spans(transcript):
    """[(start, end, text)] sentences in order, from punctuation, long pauses and segment-level text."""
    spans, current = [], []

    def close():
        if current:
            spans.append((current[0]["start"], current[-1]["end"], " ".join(w["word"] for w in current)))
            current.clear()

    words = list(_words(transcript))
    ends = sum(1 for w in words if SENTENCE_END.search(w["word"]) and w["word"].lower() not in NOT_END)
    punctuated = not any(w.get("segment") for w in words) and ends >= 5 and ends * 40 >= len(words)      # about one sentence end in 40 words, and enough of them to tell
    prev_end = None
    for w in words:
        if current and prev_end is not None and w["start"] - prev_end >= PAUSE_SPLIT:
            breath = punctuated and w["start"] - prev_end < LONG_PAUSE and prev_end - current[0]["start"] < MAX_JOINED
            if not breath:                 # "... we make a bee line for the toilet, [pause] and then ..." is one sentence
                close()
        current.append(w)
        text = w["word"].lower()
        if w.get("segment"):               # a whole segment of text: split it on its own punctuation
            parts = [p for p in re.split(r"(?<=[.!?…])[\"')\]」』”’]*\s+|(?<=[。！？।])[\"')\]」』”’]*\s*", w["word"]) if p.strip()]
            if len(parts) > 1:
                current.pop()
                dur = max(0.01, w["end"] - w["start"])
                total = sum(len(p) for p in parts) or 1
                t = w["start"]
                for p in parts:
                    seg_end = t + dur * len(p) / total
                    spans.append((t, seg_end, p.strip()))
                    t = seg_end
                prev_end = w["end"]
                continue
        if SENTENCE_END.search(w["word"]) and text not in NOT_END:    # "3.14" does not end with a dot, "Dr." is listed
            close()
        prev_end = w["end"]
    close()
    return spans


MIC_CHECK = re.compile(r"\b(testing[,. ]+(one|1(2(3)?)?|testing)|one,? two,? three|can you hear me|check,? check|is this (thing )?on|sound check)\b", re.I)
# a sentence starting with one of these leans on the one before it (never a good first line)
DEPENDENT_OPENERS = {"and", "but", "or", "because", "which", "cause", "also", "then", "anyway", "uh", "um", "er", "erm"}
# filler only when followed by a comma or an ellipsis ("So, ...", "Well, ..."): "So I quit my job" is a real opening
SOFT_OPENERS = {"so", "well", "like", "yeah", "okay", "ok", "right", "now", "basically", "actually"}
WEAK_OPENERS = DEPENDENT_OPENERS | SOFT_OPENERS


DANGLING_ENDINGS = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "about", "that", "and", "or", "but", "so", "because", "as",
                    "is", "are", "was", "were", "from", "by", "this", "these", "those", "our", "your", "my", "their", "which", "who", "what",
                    "if", "when", "than", "into", "over", "its", "his", "her", "some", "any", "can", "will", "would", "could", "should"}


def trails_off(sentence):
    """True when a sentence stops on a word that needs a continuation ("... places that.", "... data about."): a speaker who
    trailed off (Whisper writes that as "..."). Such a line is a poor title and a poor place to end a clip."""
    words = re.findall(r"[A-Za-z']+", str(sentence or ""))
    return bool(words) and words[-1].lower() in DANGLING_ENDINGS


OPENING_CUES = {"nobody", "never", "why", "how", "stop", "secret", "mistake", "wrong", "truth", "imagine"}


BOILERPLATE = re.compile(
    r"\b(welcome (back )?to|thanks? (you )?(so much )?for (being|joining|coming|taking|watching|listening|having|making)"
    r"|thank you (so much |very much )?(all|everyone|for)|voice check|sound check|how do you hear|can you hear|that concludes"
    r"|are you ready for the event|good luck|godspeed|subscribe|follow (us|them|along)|(use|using) the hashtag|see you (next|soon)"
    r"|until next time|next episode|shameless plug|stay tuned|be right back|round of applause|please welcome|give it up"
    r"|(my|our) guests? (today|this)|coming up (next|after)|right after this"
    r"|thank you,? (very much|so much)(?=\W*$)|feel free to (contact|reach|email)"
    r"|(let me|let's|can we) (start|do) (that|it|this) (over|again)|take (that|it) again)\b", re.I)


def boilerplate_hits(text):
    """How many show-housekeeping phrases a stretch of speech holds (greetings, thanks, sign-offs, "follow us", "voice check"). A window full of them
    is the intro or outro, not a moment a viewer wants as a clip."""
    return len(BOILERPLATE.findall(str(text or "")))


def disfluency(text):
    """0..1: how much of a stretch of speech is stutter or halting fragments, not a thought: an immediately repeated word ("the, the, the",
    "of a, of a") or a Whisper "..." between pieces. A viewer hears it as someone searching for words, which is a poor clip however
    many keywords it holds. Needs at least 8 words (a short stretch says nothing)."""
    text = str(text or "")
    words = re.findall(r"[^\W\d_][\w']*", text.lower())
    if len(words) < 8:
        return 0.0
    repeats = sum(1 for a, b in zip(words, words[1:]) if a == b)
    repeats += sum(1 for a, b, c, d in zip(words, words[1:], words[2:], words[3:]) if (a, b) == (c, d) and a != b)      # "of a, of a"
    fragments = len(re.findall(r"\.\.\.|…", text))
    return min(1.0, (repeats + 0.5 * fragments) / (0.25 * len(words)))


def has_hook_cue(text, words=25):
    """True when the FIRST SENTENCE (at most `words` words) holds a reason to keep watching: a question, a number, or a word that
    promises something (never, why, how, mistake, secret ...). A cheap text cue, not a judgement of how catchy the line is."""
    parts = str(text or "").strip().split()
    cut = next((i + 1 for i, w in enumerate(parts)
                if SENTENCE_END.search(w) and w.lower() not in NOT_END
                and not (w.lower() == "no." and i + 1 < len(parts) and parts[i + 1][:1].isdigit())), len(parts))     # "No. 5" is a number
    first_sentence = " ".join(parts[:cut])
    head = " ".join(first_sentence.split()[:words])
    if "?" in head or any(re.fullmatch(r"\d{1,3}%?|[$€£]\d[\d,.]*|\d[\d,.]*%", w.strip(",.!?\"'()")) for w in head.split()):
        return True
    return any(w.strip(",.!?\"'").lower() in OPENING_CUES for w in head.split())


NARROW_DANGLING = {"a", "an", "the", "and", "or", "but", "because"}      # words no complete sentence ends on


def trails_off_end(sentence):
    """True when a sentence that would END a clip stops where the speaker was cut off: Whisper's "..." after a word that needs a
    continuation (the broad DANGLING_ENDINGS list), or no "..." but a last word no complete sentence ends on (a, the, and, because ...).
    "Look at this." / "That is what I am most proud of." are complete sentences and are not flagged (the title rule is broader)."""
    text = str(sentence or "").strip()
    words = re.findall(r"[A-Za-z']+", text)
    if not words:
        return False
    last = words[-1].lower()
    if words[-1] == "A":                    # a letter ("Plan A.", "vitamin A."), not the article
        return False
    if text.rstrip("\"')]\u201d\u2019").endswith(("...", "\u2026")):
        return last in DANGLING_ENDINGS
    return last in NARROW_DANGLING


def weak_opening(text):
    """True when a sentence is a poor first line for a clip: a mic check at its start, a connective or filler sound first
    ("And ...", "Uh, ..."), or a soft filler followed by a comma ("So, ...", "Well, ..."). "So I quit my job" is not weak."""
    text = str(text or "").strip()
    m = re.match(r"([^\W\d_][\w']*)(\s*[,.…]|\s)", text)
    if not m:
        return False
    first = m.group(1).lower()
    head = " ".join(re.findall(r"[a-z0-9']+", text.lower())[:8])
    if MIC_CHECK.search(head):
        return True
    if first in DEPENDENT_OPENERS:
        return True
    return first in SOFT_OPENERS and m.group(2).strip() != ""


# opening words a clip can lose while the sentence stays whole
LEAD_ALWAYS = {"and", "but", "because", "uh", "um", "er", "erm"}                       # because: not "because of ..."
LEAD_WITH_COMMA = {"so", "well", "okay", "ok", "yeah", "right", "now", "like", "basically", "actually", "anyway"}   # "So I quit" stays
LEAD_PHRASES = (("in", "that", "sense"), ("i", "mean"), ("you", "know"), ("and", "so"))   # each only as a whole, before the sentence
MAX_LEAD_WORDS, MAX_LEAD_SECONDS = 6, 3.0
LEAD_MIN_REST = 4                                                                      # words left of the sentence after the cut


def lead_in_length(tokens):
    """How many of a sentence's first words are a lead-in that can be cut. `tokens` are its words with their punctuation."""
    bare = [re.sub(r"[^a-z']", "", str(w).lower()) for w in tokens]
    comma = [str(w).rstrip().endswith((",", "...", "\u2026")) for w in tokens]
    n = 0
    while n < len(bare):
        phrase = next((p for p in LEAD_PHRASES if tuple(bare[n:n + len(p)]) == p and comma[n + len(p) - 1]), None)
        if phrase:
            n += len(phrase)
        elif bare[n] in LEAD_ALWAYS and not (bare[n] == "because" and bare[n + 1:n + 2] == ["of"]):
            n += 1
        elif bare[n] in LEAD_WITH_COMMA and comma[n]:
            n += 1
        elif n and bare[n - 1] == "and" and bare[n] in ("so", "then"):     # "And so there ..." / "And then ..."
            n += 1
        else:
            break
    sentence = next((k + 1 for k, w in enumerate(tokens) if SENTENCE_END.search(str(w)) and str(w).lower() not in NOT_END
                     and not str(w).endswith(("...", "…"))), len(tokens))
    if n > MAX_LEAD_WORDS or sentence - n < LEAD_MIN_REST or any(str(w).rstrip().endswith((".", "?", "!")) for w in tokens[:n]):
        return 0
    return n


def _only_needs_trimming(sentence):
    """A weak first line that is fine once its lead-in words are gone (and is not a mic check or housekeeping talk)."""
    return bool(lead_in_length(str(sentence).split())) and not MIC_CHECK.search(sentence) and not boilerplate_hits(sentence)


def trim_lead_in(clip, words, min_len):
    """`clip` with its start moved past a leading "So, ..." / "And ..." / "Because ...", when the word timings allow it."""
    if clip.get("user_moment") or clip.get("lead_trim") or not clip.get("snapped"):
        return clip
    start, end = float(clip["start"]), float(clip["end"])
    i = next((k for k, w in enumerate(words) if w["start"] >= start - 0.05), None)
    if i is None or words[i].get("segment") or words[i]["start"] - start > 1.0:
        return clip
    if i and not SENTENCE_END.search(words[i - 1]["word"]) and words[i]["start"] - words[i - 1]["end"] < PAUSE_SPLIT:
        return clip                                        # not the start of a sentence
    n = lead_in_length([w["word"] for w in words[i:i + MAX_LEAD_WORDS + LEAD_MIN_REST]])
    if not n:
        return clip
    first = words[i + n]
    new_start = max(words[i + n - 1]["end"], first["start"] - 0.08)
    if first["start"] - start > MAX_LEAD_SECONDS or end - new_start < min_len:
        return clip
    return dict(clip, start=round(new_start, 2), lead_trim=round(new_start - start, 2))


def _is_leadin(text, max_words):
    words = re.findall(r"[a-z']+", text.lower())
    return 0 < len(words) <= max_words and all(w in FILLER_WORDS for w in words)


def snap_clip(clip, spans, **opts):
    """A copy of `clip` ({start, end, ...}) with its edges moved to sentence boundaries; the original clip when nothing
    sensible can be done. Adds `orig_start` / `orig_end` / `snapped` to the copy."""
    o = {**DEFAULTS, **opts}
    if not spans or clip.get("user_moment"):          # moments the user chose by time are cut exactly as given
        return clip
    start, end = float(clip["start"]), float(clip["end"])
    starts = [s for s, _, _ in spans]
    ends = [e for _, e, _ in spans]

    # --- start: a sentence start, as close as possible (earlier = keeps the whole sentence, later = skips the lead-in)
    new_start = start
    inside = next((i for i, (s, e, _) in enumerate(spans) if s - 0.05 <= start < e), None)
    if clip.get("lead_trim"):
        pass                                               # already cut just past its lead-in: do not go back to the sentence start
    elif inside is not None and abs(starts[inside] - start) > 0.05:
        before = starts[inside]
        after = starts[inside + 1] if inside + 1 < len(spans) else None
        cands = [c for c in (before, after) if c is not None and abs(c - start) <= o["max_shift"] and c < end - o["min_len"]]
        if cands:
            new_start = min(cands, key=lambda c: abs(c - start))
        else:
            # a long sentence with no boundary close by: rather start at its beginning than mid-sentence
            far = [c for c in (before, after) if c is not None and abs(c - start) <= o["long_shift"] and c < end - o["min_len"]
                   and end - c <= o["max_len"]]
            if far:
                new_start = min(far, key=lambda c: abs(c - start))
    elif inside is None:
        # the start sits in a pause: begin with the sentence that follows it
        following = [c for c in starts if c > start]
        if following and following[0] - start <= o["max_shift"] and following[0] < end - o["min_len"]:
            new_start = following[0]
    # skip a filler sentence at the very start ("So, um, okay.")
    first = next((i for i, (s, _, _) in enumerate(spans) if abs(s - new_start) < 0.05), None)
    origin = new_start
    if first is not None and first + 1 < len(spans) and _is_leadin(spans[first][2], o["leadin_max_words"]):
        cand = starts[first + 1]
        if cand - new_start <= o["skip_shift"] and cand < end - o["min_len"]:
            new_start = cand
            first += 1
    # a sentence that cannot open a clip (mic check, or it leans on the one before: "And, and it just goes ...", "Uh, 79% ...")
    for _ in range(0 if clip.get("snapped") else 3):      # a clip already snapped is not skipped again (the skips would add up)
        if first is None or first + 1 >= len(spans) or not weak_opening(spans[first][2]):
            break
        cand = starts[first + 1]
        if cand - origin > o["skip_shift"] or cand >= end - o["min_len"] or end - cand < 0.6 * (end - start):
            break                                         # never give up more than 40% of the clip for a better first line
        new_start, first = cand, first + 1

    # --- end: after the sentence the clip stops in (finish the thought), else back to the last complete sentence
    new_end = end
    inside_e = next((i for i, (s, e, _) in enumerate(spans) if s < end <= e + 0.05), None)
    if clip.get("clause_end"):
        pass                                               # already placed at a comma or breath of a long sentence
    elif inside_e is not None and abs(ends[inside_e] - end) > 0.05:
        forward = ends[inside_e]
        back = ends[inside_e - 1] if inside_e > 0 else None
        cands = [c for c in (forward, back) if c is not None and abs(c - end) <= o["max_shift"] and c > new_start + o["min_len"]]
        if cands:
            # finish the thought (the payoff usually lands at the end of the sentence the clip stops in)
            new_end = forward if forward in cands else min(cands, key=lambda c: abs(c - end))
        else:
            far = [c for c in (forward, back) if c is not None and abs(c - end) <= o["long_shift"] and c > new_start + o["min_len"]
                   and c - new_start <= o["max_len"]]
            if far:
                new_end = forward if forward in far else back
        if (o["target"] and back is not None and new_end == forward and forward - new_start > 1.25 * o["target"]
                and back - new_start >= 0.75 * o["target"] and back > new_start + o["min_len"]):
            new_end = back                            # a long sentence would put the clip over its asked length: stop on the last sentence that fits
    elif inside_e is None:
        # the end sits in a pause: snap back to the sentence that just finished
        prev = [e for e in ends if e <= end + 0.05]
        if prev and end - prev[-1] <= o["max_shift"] and prev[-1] > new_start + o["min_len"]:
            new_end = prev[-1]

    # a last sentence that stops on a word needing a continuation ("... places that."): end on the sentence before it instead
    if not clip.get("snapped"):
        last = next((i for i, (_, e, _) in enumerate(spans) if abs(e - new_end) < 0.05), None)
        if (last is not None and last > 0 and trails_off_end(spans[last][2]) and ends[last - 1] > new_start + o["min_len"]
                and ends[last - 1] - new_start >= 0.7 * (new_end - new_start)):
            new_end = ends[last - 1]

    # --- a short tail so the clip does not stop dead on the last word, but never into the next sentence
    if not clip.get("clause_end"):
        nxt = [s for s in starts if s > new_end + 0.01]
        tail_end = new_end + o["tail"]
        if nxt:
            tail_end = min(tail_end, nxt[0] - 0.05)
        new_end = max(new_end, tail_end)

    # --- keep it a short: too long -> end at the last sentence that fits; too short -> leave the clip as it was
    if new_end - new_start > o["max_len"]:
        fit = [e for e in ends if new_start + o["min_len"] < e <= new_start + o["max_len"]]
        new_end = (fit[-1] + min(o["tail"], 0.2)) if fit else new_start + o["max_len"]
    if new_end - new_start < o["min_len"] and (end - start) >= o["min_len"]:
        return clip

    out = dict(clip)
    out.update({"start": round(new_start, 2), "end": round(new_end, 2), "snapped": True,
                "orig_start": clip.get("orig_start", round(start, 2)), "orig_end": clip.get("orig_end", round(end, 2))})   # keep the first pick across passes
    return out


CLAUSE_PAUSE = 0.35                       # a breath this long inside a sentence is a place a clip can stop
CLAUSE_BACK, CLAUSE_ON = 10.0, 6.0        # how far before / after the cut to look for one


def end_at_a_clause(clip, words, ends, min_len, max_len, tail=0.4):
    """For a clip that still stops part-way through a sentence (no sentence ends anywhere near: a speaker who runs on): stop after the
    nearest comma or breath instead of on whatever word the cut fell on. A clip that ends with a sentence is left alone."""
    if clip.get("user_moment") or not clip.get("snapped") or clip.get("clause_end"):
        return clip
    start, end = float(clip["start"]), float(clip["end"])
    inside = [w for w in words if w["start"] < end - 0.05]
    if not inside or inside[-1].get("segment") or any(inside[-1]["end"] - 0.05 <= e <= end + 0.05 for e in ends):
        return clip
    places = []
    for i, w in enumerate(words[:-1]):
        stop = w["end"]
        if not (start + min_len <= stop <= min(end + CLAUSE_ON, start + max_len - tail) and stop >= end - CLAUSE_BACK):
            continue
        comma = w["word"].rstrip("\"')]").endswith((",", ";", ":"))
        if not (comma or words[i + 1]["start"] - stop >= CLAUSE_PAUSE):
            continue
        bare = re.sub(r"[^a-z']", "", w["word"].lower())
        if bare in DANGLING_ENDINGS:                      # "... on the [breath]" is not a place to stop
            continue
        places.append((abs(stop - end) - (1.0 if comma else 0.0), stop, words[i + 1]["start"]))
    if not places:
        return clip
    _, stop, following = min(places)
    return dict(clip, end=round(max(stop, min(stop + tail, following - 0.05)), 2), clause_end=True)


def snap_highlights(highlights, transcript, **opts):
    """Snap every highlight; clips never overlap their neighbours afterwards (the earlier one is shortened)."""
    spans = sentence_spans(transcript)
    if not spans:
        return highlights
    o = {**DEFAULTS, **opts}
    words = _words(transcript)
    ends = [e for _, e, _ in spans]
    clips = [trim_lead_in(snap_clip(h, spans, **opts), words, o["min_len"]) for h in highlights]
    clips = [end_at_a_clause(c, words, ends, o["min_len"], o["max_len"], o["tail"]) for c in clips]
    return _resolve_overlaps(clips, spans, o)


def _score(c):
    try:
        return float(c.get("final_score", c.get("viral_score", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_overlaps(clips, spans, o):
    """No two clips overlap afterwards. Each overlap is settled at a sentence boundary when possible (the earlier clip ends
    after its last whole sentence, or the later one starts at its next sentence); a moment the user chose by time is never
    trimmed; a clip that would end up shorter than min_len is dropped instead of kept as a stub."""
    clips = [dict(c) for c in clips]
    for _ in range(4 * len(clips) + 4):
        clips.sort(key=lambda c: float(c["start"]))
        pair = next(((i, i + 1) for i in range(len(clips) - 1) if float(clips[i]["end"]) > float(clips[i + 1]["start"])), None)
        if pair is None:
            break
        A, B = clips[pair[0]], clips[pair[1]]
        a_start, a_end, b_start, b_end = float(A["start"]), float(A["end"]), float(B["start"]), float(B["end"])
        a_fixed, b_fixed = bool(A.get("user_moment")), bool(B.get("user_moment"))
        if a_fixed and b_fixed:
            break                                      # both chosen by the user: their choice wins
        done = [e for _, e, _ in spans if a_start + o["min_len"] <= e <= b_start - 0.05]
        nxt = [st for st, _, _ in spans if a_end <= st <= b_end - o["min_len"]]
        if not a_fixed and not b_fixed and _score(B) < _score(A):
            # the weaker clip gives way, not the better one that happens to be earlier; it restarts at a sentence start
            # or is dropped (never cut mid-sentence)
            if nxt:
                B["start"] = round(nxt[0], 2)
            else:
                clips.pop(pair[1])                     # trimming the better clip is worse than losing the weaker one
        elif not a_fixed and done:
            A["end"] = round(min(done[-1] + o["tail"], b_start - 0.01), 2)
        elif not b_fixed and nxt:
            B["start"] = round(nxt[0], 2)
        elif not a_fixed:
            if b_start - a_start >= o["min_len"]:
                A["end"] = round(b_start - 0.01, 2)
            else:
                clips.pop(pair[0])                    # what is left would be a stub: drop it
        else:
            if b_end - a_end >= o["min_len"]:
                B["start"] = round(a_end + 0.01, 2)
            else:
                clips.pop(pair[1])
    clips.sort(key=lambda c: float(c["start"]))
    return clips


def merge_close_moments(highlights, gap=3.0):
    """Highlights-reel moments that sit less than `gap` seconds apart become one continuous moment: a crossfade between two
    spots a second or two apart looks like a stutter, and the few seconds between them are usually part of the same scene.
    Moments the user chose by time are kept as given."""
    out = []
    for h in sorted(highlights, key=lambda x: float(x["start"])):
        if out and not h.get("user_moment") and not out[-1].get("user_moment") \
                and float(h["start"]) - float(out[-1]["end"]) < gap:
            prev = out[-1]
            out[-1] = dict(prev, end=max(float(prev["end"]), float(h["end"])),
                           viral_score=max(prev.get("viral_score", 0) or 0, h.get("viral_score", 0) or 0), merged=True)
        else:
            out.append(dict(h))
    return out


# ---------------------------------------------------------------- highlights reel: the quality of each moment

REEL_MERGE_GAP = 12.0      # moments of a reel closer than this become one (a crossfade between neighbours looks like a stutter)
REEL_MIN_MOMENT = 15.0     # a reel moment is never cut or skipped down below this


def bad_opener(text):
    """True when a sentence is a poor first line for a reel moment: housekeeping talk ("thank you very much", a voice check), a mic
    check, a connective / filler first word, or stutter."""
    text = str(text or "")
    return bool(weak_opening(text) or boilerplate_hits(text) or MIC_CHECK.search(text) or disfluency(text) > 0.35)


def clean_reel_openings(moments, spans, min_len=REEL_MIN_MOMENT, skip_shift=20.0):
    """Reel moments start on a real first line: leading housekeeping / stutter / filler sentences are skipped (at most 3, 20 s, and never
    below `min_len`); a moment that still opens on housekeeping is dropped when at least two others remain. Moments the user chose are kept."""
    out = []
    starts = [s for s, _, _ in spans]
    for m in moments:
        m = dict(m)
        if m.get("user_moment") or not spans:
            out.append(m)
            continue
        origin = float(m["start"]) - float(m.get("lead_trim") or 0.0)      # where the trimmed sentence begins
        i = next((k for k, (s, _, _) in enumerate(spans) if s >= origin - 0.05), None)
        for _ in range(3):
            if i is None or i + 1 >= len(spans) or not bad_opener(spans[i][2]) or _clean_once_trimmed(m, spans[i][2]):
                break
            cand = starts[i + 1]
            if cand - origin > skip_shift or float(m["end"]) - cand < min_len:
                break
            i += 1
            m["start"] = round(cand, 2)
            m.pop("lead_trim", None)
        out.append(m)
    keep = [m for m in out if m.get("user_moment") or not boilerplate_hits(_first_sentence(m, spans))]
    return keep if len(keep) >= 2 or len(out) < 2 else out


def _clean_once_trimmed(moment, sentence):
    return bool(moment.get("lead_trim")) and _only_needs_trimming(sentence) and disfluency(sentence) <= 0.35


def _first_sentence(m, spans):
    s = float(m["start"]) - float(m.get("lead_trim") or 0.0)
    return next((t for a, _, t in spans if a >= s - 0.05), "")


def _tail_end(end, starts, tail=0.4):
    nxt = [s for s in starts if s > end + 0.01]
    return round(min(end + tail, nxt[0] - 0.05) if nxt else end + tail, 2)


def fit_reel_length(moments, spans, target, tolerance=0.08, min_len=REEL_MIN_MOMENT, max_grow=25.0):
    """Bring a reel to within `tolerance` of `target` seconds by moving moment ENDS between sentences only: too long, the longest moment
    stops sooner (never below `min_len`); too short, the best moments run on by whole sentences (up to `max_grow` s each, never into the
    next moment, never into housekeeping talk). Every end stays on a sentence end."""
    ms = [dict(m) for m in sorted(moments, key=lambda x: float(x["start"]))]
    if not ms or not target or not spans:
        return ms
    ends = [e for _, e, _ in spans]
    texts = [t for _, _, t in spans]
    starts = [s for s, _, _ in spans]
    ceiling, floor = target * (1 + tolerance), target * (1 - tolerance)
    total = lambda: sum(float(m["end"]) - float(m["start"]) for m in ms)      # noqa: E731
    for _ in range(40):
        over = total() - ceiling
        if over <= 0:
            break
        movable = [m for m in ms if not m.get("user_moment")]
        if not movable:
            break
        m = max(movable, key=lambda x: float(x["end"]) - float(x["start"]))
        s, e = float(m["start"]), float(m["end"])
        cuts = [x for x, t in zip(ends, texts) if s + min_len <= x < e - 0.5 and not trails_off_end(t)]
        if not cuts:
            break
        enough = [x for x in cuts if e - x >= over]
        new = max(enough) if enough else min(cuts)
        m["end"] = _tail_end(new, starts)
        m["trimmed_to_fit"] = True
    grew = {}
    for _ in range(60):
        if total() >= floor:
            break
        progress = False
        for idx in sorted(range(len(ms)), key=lambda k: -_score(ms[k])):
            m = ms[idx]
            if m.get("user_moment") or grew.get(idx, 0.0) >= max_grow:
                continue
            e = float(m["end"])
            limit = float(ms[idx + 1]["start"]) - 1.0 if idx + 1 < len(ms) else float("inf")
            k = next((j for j, (a, _, _) in enumerate(spans) if a >= e - 0.5), None)
            if k is None or spans[k][1] > limit or boilerplate_hits(spans[k][2]) or trails_off_end(spans[k][2]):
                continue
            add = spans[k][1] - e
            if total() + add > ceiling or grew.get(idx, 0.0) + add > max_grow + 5.0:
                continue
            m["end"] = _tail_end(spans[k][1], starts)
            grew[idx] = grew.get(idx, 0.0) + add
            progress = True
            if total() >= floor:
                break
        if not progress:
            break
    return ms


def polish_reel(moments, transcript, target=None):
    """What a highlights reel's moments go through after the sentence snapping: neighbours a few seconds apart become one moment,
    each moment opens on a real first line, and the length lands within the target with every end still on a sentence end."""
    spans = sentence_spans(transcript)
    if not spans:
        return moments
    ms = merge_close_moments(moments, gap=REEL_MERGE_GAP)
    ms = clean_reel_openings(ms, spans)
    if target:
        ms = fit_reel_length(ms, spans, float(target))
    return sorted(ms, key=lambda h: float(h["start"]))
