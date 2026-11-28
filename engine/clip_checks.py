"""What ShortsFlow itself notices about each finished clip, so a person knows which ones deserve a look and what to try.

Uses the checks of `engine.clip_quality` (data only: the transcript with word times and the clip's window; no model, no network) and turns each into
a plain sentence plus an exact edit that the editor / `python -m engine.rerender` accepts:

* opening   the clip opens on a connective, a filler or a pronoun that points at something said before it, or the first word comes late
* ending    the clip stops on a word that needs a continuation (the speaker was cut off)
* pauses    long stretches of silence are left in (only said when the run did not tighten)

A clip with nothing to say gets no note. A note is advice, never a change: the clip is left as it was made.
"""
import json
import os

PAUSE_NOTE_SECONDS = 3.0       # silence inside the clip (pauses of 0.7 s or more) that is worth a note
LATER_START_MAX = 6.0          # a suggested start must be within this many seconds of the current one
EARLIER_END_MAX = 8.0          # a suggested end must be within this many seconds before the current one
MIN_LEFT = 12.0                # a suggestion never leaves less than this much clip


def _segments(session_dir):
    try:
        with open(os.path.join(session_dir, "transcript.json"), encoding="utf-8") as f:
            return [s for s in json.load(f).get("segments", []) if isinstance(s, dict) and "start" in s and "end" in s]
    except (OSError, ValueError):
        return []


def _later_start(segments, start, end):
    """The start of the next sentence after `start`, within LATER_START_MAX seconds and leaving MIN_LEFT, else None."""
    from engine.clip_quality import sentence_edges
    starts, _ = sentence_edges(segments)
    nxt = [t for t in starts if start + 0.4 < t <= start + LATER_START_MAX and end - t >= MIN_LEFT]
    return round(min(nxt), 1) if nxt else None


def _earlier_end(segments, start, end):
    """The end of the last full sentence before `end`, within EARLIER_END_MAX seconds and leaving MIN_LEFT, else None."""
    from engine.clip_quality import sentence_edges
    _, ends = sentence_edges(segments)
    before = [t for t in ends if end - EARLIER_END_MAX <= t < end - 0.4 and t - start >= MIN_LEFT]
    return round(max(before), 1) if before else None


def notes_for_clip(segments, start, end, tightened=False):
    """[{"code", "text", "try"}] for one clip window (an empty list when nothing stands out)."""
    from engine import clip_quality as cq
    start, end = float(start), float(end)
    out = []
    words = cq._clip_words(segments, start, end)
    opening = " ".join(w for _, w in words[:5])
    if words and not cq.self_contained_opening(segments, start, end):
        out.append({"code": "opening", "text": f'It opens on "{opening}": the first word points at something said before the clip.'})
    elif not cq.hook_ok(segments, start, end):
        out.append({"code": "opening", "text": f'It opens on "{opening}", which does not stand on its own (a connective, a filler, a short line or a late first word).'})
    if out:
        later = _later_start(segments, start, end)
        out[-1]["try"] = (f"Start it at {later} s (--start {later} in the editor), or turn on --cold_open to lead with the strongest line." if later
                          else "Turn on --cold_open to lead with the strongest line, or move the start in the editor.")
    if not cq.clean_ending(segments, start, end):
        last = " ".join(w for _, w in words[-5:])
        note = {"code": "ending", "text": f'It stops on "{last}", which needs more words after it: the speaker is cut off.'}
        earlier = _earlier_end(segments, start, end)
        note["try"] = (f"End it at {earlier} s (--end {earlier} in the editor)." if earlier else "Move the end to a full stop in the editor.")
        out.append(note)
    pauses = cq.speech_gaps(segments, start, end, gap_min=0.7)
    if pauses >= PAUSE_NOTE_SECONDS and not tightened:
        out.append({"code": "pauses", "text": f"About {pauses:.0f} s of it is silence.", "try": "Run again with --tighten to cut the pauses."})
    return out


def notes_for_run(highlights, session_dir, tightened=False, reel=False):
    """One list of notes per highlight (all empty for a highlights video, which is one file made of many moments, or without a transcript)."""
    segments = [] if reel else _segments(session_dir)
    out = []
    for h in highlights:
        try:
            out.append(notes_for_clip(segments, h["start"], h["end"], tightened) if segments else [])
        except Exception as e:              # a note is a bonus: never fail a run for one
            print(f"[Warning] Could not check a clip: {' '.join(str(e).split())[:100]}")
            out.append([])
    return out


def as_line(notes):
    """The notes of one clip as the text of a report cell."""
    return " ".join(f"{n['text']} {('Try: ' + n['try']) if n.get('try') else ''}".strip() for n in notes)
