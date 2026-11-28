"""Thumbs up / down on clips, and the one thing ShortsFlow learns from it: which clip LENGTH you tend to like.

Each rating is appended to a small local file (`feedback.json` in the ShortsFlow cache folder, never uploaded anywhere):
    {"title": ..., "duration": 38.5, "score": 77, "liked": true, "time": "2026-11-04T12:00:00"}

Once at least `MIN_RATINGS` clips have been rated, and the liked clips differ in length from the disliked ones by a clear margin, the
preferred length is the average of the liked clips. Candidate clips are then nudged by at most +/- `MAX_NUDGE` points on the 0-100
scale: closer to the preferred length is a little better. That is deliberately small: it breaks ties between similar clips and never
overrules a clearly better one. `SHORTSFLOW_NO_FEEDBACK=1` switches the nudge off.
"""
import json
import os
import time

# What was wrong with a clip you gave a thumbs down: the label in the app, and what to try when it keeps being the reason.
REASONS = {
    "opening": ("The opening is weak", "Several clips were marked for a weak opening: try --cold_open (starts on the strongest line), or move the start in the editor."),
    "person": ("The wrong person is shown", "Several clips showed the wrong person: try --layout split (both people stacked) or --layout fit (the whole picture)."),
    "cut": ("It is cut at the wrong place", "Several clips were cut at the wrong place: check the end in the editor (move it to a full stop); a clip can also be rendered again with a new start and end."),
    "captions": ("The captions", "Several clips were marked for their captions: try another style (--caption_style MINIMAL or GLOW_BOX) or another place (--caption_position)."),
    "boring": ("Not an interesting moment", "Several clips were marked as not interesting: ask for more clips and keep the best (--clip_count), and say what the video is about (--user_context)."),
    "title": ("The title or description", "Several clips were marked for their title: say what the video is about (--user_context) and pick one of the other title ideas."),
}
MIN_REASON_COUNT = 3      # a reason has to come up this many times ...
MIN_REASON_SHARE = 0.4    # ... and in this share of the clips that were given a reason, before it becomes advice

MIN_RATINGS = 8
MIN_PER_SIDE = 3          # liked AND disliked clips needed before a preference means anything
MIN_DIFFERENCE = 3.0      # seconds between the liked and disliked average lengths
MAX_NUDGE = 5.0


def feedback_path():
    base = os.environ.get("SHORTSFLOW_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "shortsflow")
    return os.path.join(base, "feedback.json")


def load(path=None):
    try:
        with open(path or feedback_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if isinstance(e, dict) and "duration" in e and "liked" in e] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def record(title, duration, score, liked, path=None, reason=None):
    """Append one rating (a thumbs-down may say what was wrong: a key of REASONS); returns the number of ratings stored (0 when the file could not be written)."""
    path = path or feedback_path()
    entries = load(path)
    entries.append({"title": str(title or "")[:120], "duration": round(float(duration or 0), 1),
                    "score": None if score is None else round(float(score), 1), "liked": bool(liked),
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    **({"reason": reason} if reason in REASONS and not liked else {})})
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries[-500:], f, indent=1)
        os.replace(tmp, path)
    except OSError:
        return 0
    return len(entries)


def preferred_duration(entries):
    """Average length (s) of the liked clips when the ratings show a clear preference, else None."""
    liked = [float(e["duration"]) for e in entries if e.get("liked") and float(e["duration"]) > 0]
    disliked = [float(e["duration"]) for e in entries if not e.get("liked") and float(e["duration"]) > 0]
    if len(liked) + len(disliked) < MIN_RATINGS or len(liked) < MIN_PER_SIDE or len(disliked) < MIN_PER_SIDE:
        return None
    mean_liked, mean_disliked = sum(liked) / len(liked), sum(disliked) / len(disliked)
    if abs(mean_liked - mean_disliked) < MIN_DIFFERENCE:
        return None
    return round(mean_liked, 1)


def nudge(duration, preferred):
    """Score points (-MAX_NUDGE..+MAX_NUDGE) for a clip of `duration` seconds given the preferred length."""
    if not preferred or not duration:
        return 0.0
    distance = abs(float(duration) - float(preferred)) / max(8.0, float(preferred) * 0.4)    # 0 = exactly the preferred length
    return round(MAX_NUDGE * (1.0 - 2.0 * min(1.0, distance)), 2)


def apply_preferences(highlights, entries=None):
    """The highlights with `final_score` / `viral_score` nudged toward the preferred length (copies; unchanged when there is no
    clear preference yet, or when SHORTSFLOW_NO_FEEDBACK=1)."""
    if os.environ.get("SHORTSFLOW_NO_FEEDBACK") == "1" or not highlights:
        return highlights
    pref = preferred_duration(entries if entries is not None else load())
    if pref is None:
        return highlights
    out = []
    for h in highlights:
        bump = nudge(float(h["end"]) - float(h["start"]), pref)
        h = dict(h)
        if bump:
            base = float(h.get("final_score", h.get("viral_score", 50)) or 50)
            h["final_score"] = round(base + bump, 1)
            h["feedback_nudge"] = bump
        out.append(h)
    return out


def advice(entries=None):
    """Plain advice from the reasons given with thumbs-downs ('' until one reason is clearly the usual one)."""
    entries = load() if entries is None else entries
    reasons = [e["reason"] for e in entries if not e.get("liked") and e.get("reason") in REASONS]
    if len(reasons) < MIN_REASON_COUNT:
        return ""
    top = max(REASONS, key=reasons.count)
    if reasons.count(top) < MIN_REASON_COUNT or reasons.count(top) < MIN_REASON_SHARE * len(reasons):
        return ""
    return REASONS[top][1]


def summary(entries=None):
    """One plain line about what has been learned, for the review screen."""
    entries = load() if entries is None else entries
    n = len(entries)
    if not n:
        return "No ratings yet."
    pref = preferred_duration(entries)
    liked = sum(1 for e in entries if e.get("liked"))
    base = f"{n} rating{'s' if n != 1 else ''} saved ({liked} liked)."
    tip = advice(entries)
    if pref:
        return base + f" You tend to like clips of about {pref:.0f} s; those are now ranked slightly higher." + (f" {tip}" if tip else "")
    return base + f" Rate at least {MIN_RATINGS} clips (with both thumbs) to personalise the picks." + (f" {tip}" if tip else "")
