"""A scorecard for the case explainer's own decisions: run the SCRIPT step (no narration, no render, a few model calls) on a fixed set of topics and score what
ShortsFlow chose, so a change to a prompt or a rule is judged on numbers across topics and not on one lucky or unlucky sample (the model varies from run to run).

    python scripts/case_scorecard.py                       # every topic, a table at the end
    python scripts/case_scorecard.py --topics rainbow,fridge --length short --llm local

What is scored (`score`, pure functions, tested offline): how many sections became picture scenes; how many of their labels are things you can draw (not ideas or
processes) and how many the narrator actually says (so the icons pop in on time); counter cards that hold a year or a raw exponent; whether the opening line is a
real line; sections that fell back to a plain checklist; sentences removed because the sources do not say them; the words, and about how many seconds they take.
"""
import json
import os
import re
import subprocess
import sys

TOPICS = {
    "rainbow": ("How a rainbow forms, explained simply", "https://en.wikipedia.org/wiki/Rainbow"),
    "fridge": ("How a refrigerator keeps food cold, explained simply", "https://en.wikipedia.org/wiki/Refrigerator"),
    "vaccine": ("How a vaccine trains your immune system to fight a virus", "https://en.wikipedia.org/wiki/Vaccine"),
    "phishing": ("How phishing attacks trick people, and how to spot them", "https://en.wikipedia.org/wiki/Phishing"),
    "sky": ("Why the sky is blue, explained simply", "https://en.wikipedia.org/wiki/Rayleigh_scattering"),
    "telescope": ("How the Event Horizon Telescope imaged a black hole", "https://en.wikipedia.org/wiki/Event_Horizon_Telescope"),
}

# words that make a label an idea or a process, not something you could point at in a drawing
ABSTRACT = {"process", "cycle", "transfer", "effect", "environment", "system", "concept", "method", "technique", "phenomenon", "principle", "theory", "reaction",
            "analysis", "efficiency", "dynamics", "mechanism", "relationship", "approach", "strategy", "model", "framework", "compression", "evolution", "interaction"}
WORDS_PER_SECOND = 2.6
MIN_WORDS = {"short": 20, "standard": 35, "long": 50}       # (the script step refills to the same numbers: case_study.MIN_NARRATION) a section with fewer spoken words than this is thin for its length setting


def _words(text):
    return re.findall(r"[A-Za-z][A-Za-z']+", str(text or "").lower())


def is_abstract(label):
    """True when a picture label is an idea or a process (it holds a word of ABSTRACT), is a sentence (more than four words) or holds a digit."""
    words = _words(label)
    return len(words) > 4 or bool(re.search(r"\d", str(label))) or any(w in ABSTRACT for w in words)


def is_spoken(label, narration):
    """True when the narration says a content word of the label (a plural counts as the same word): the icon can pop in as the narrator reaches it."""
    from engine import case_study
    return case_study.label_spoken(label, narration)               # the one definition, shared with the script step that repairs unspoken labels


def score(script, length="standard"):
    """The measurements of one script (see the module text). `length` is the length setting it was written for (it sets what counts as thin narration)."""
    from engine import case_study
    sections = script.get("sections", []) or []
    pictures = [s for s in sections if s.get("scene") == "illustration"]
    labels = [(l, s.get("narration", "")) for s in pictures for l in (s.get("on_screen") or [])]
    counter_labels = [l for s in sections if s.get("scene") == "counters" for l in (s.get("on_screen") or [])]
    bad_counters = sum(1 for label in counter_labels if case_study.bad_counter_label(label))
    hook = " ".join(str(script.get("hook") or "").split())
    words = sum(len(str(s.get("narration", "")).split()) for s in sections)
    return {
        "sections": len(sections),
        "picture_sections": len(pictures),
        "picture_labels": len(labels),
        "abstract_labels": sum(1 for l, _ in labels if is_abstract(l)),
        "spoken_labels": sum(1 for l, n in labels if is_spoken(l, n)),
        "bad_counter_labels": bad_counters,
        "hook_ok": bool(hook) and bool(case_study.check_hook(hook, None)[0]),
        "fallbacks": sum(1 for s in sections if s.get("scene") == "checklist" and s.get("id") != "do"),     # a checklist that is not the template's last section
        "empty_sections": sum(1 for s in sections if s.get("scene") != "animation" and not [l for l in (s.get("on_screen") or []) if str(l).strip()]),
        "thin_sections": sum(1 for s in sections if len(str(s.get("narration", "")).split()) < MIN_WORDS.get(length, MIN_WORDS["standard"])),
        "removed_sentences": len(script.get("dropped") or []),
        "verified": bool(script.get("verified")),
        "words": words,
        "seconds": round(words / WORDS_PER_SECOND),
    }


def passes(m):
    """The checks every script should meet: a picture scene, at most one idea-like picture label, at least half of the picture labels said by the narrator (so
    the icons pop in on time), no date or exponent on a counter card, a real hook, no section without labels and no thin narration. A checklist in the middle
    is not a failure by itself (a section with no readable figures is meant to become one); the "fallbacks" column only reports how many there are."""
    return bool(m["picture_sections"] >= 1 and m["abstract_labels"] <= 1 and m["spoken_labels"] * 2 >= m["picture_labels"] and m["bad_counter_labels"] == 0
                and m["hook_ok"] and m.get("empty_sections", 0) == 0 and m.get("thin_sections", 0) == 0)


def table(results):
    """A markdown table of {topic: metrics (or an error string)} with a closing line."""
    lines = ["| topic | written by | pictures | drawable labels | spoken labels | bad counters | hook | fallbacks | empty | thin | removed | seconds | result |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ok = 0
    for topic, m in results.items():
        if not isinstance(m, dict):
            lines.append(f"| {topic} | {m} |  |  |  |  |  |  |  |  |  |  | no script |")
            continue
        n = m["picture_labels"]
        drawable = f"{n - m['abstract_labels']}/{n}" if n else "-"
        spoken = f"{m['spoken_labels']}/{n}" if n else "-"
        good = passes(m)
        ok += good
        lines.append(f"| {topic} | {m.get('model', '?')} | {m['picture_sections']} | {drawable} | {spoken} | {m['bad_counter_labels']} | {'ok' if m['hook_ok'] else 'BAD'} | "
                     f"{m['fallbacks']} | {m.get('empty_sections', 0)} | {m.get('thin_sections', 0)} | {m['removed_sentences']} | {m['seconds']} | {'pass' if good else 'FAIL'} |")
    lines += ["", f"{ok} of {len(results)} topics pass every check."]
    local = [t for t, m in results.items() if isinstance(m, dict) and m.get("model") == "local fallback"]
    if local:
        lines.append(f"Written by the model on this PC (the cloud model did not answer): {', '.join(local)}. Judge the prompts on the others; rerun these when the cloud is back.")
    return "\n".join(lines)


def command(topic, out_dir, length="standard", llm="auto", python=None):
    """The command line of one script-only run for a topic key of TOPICS (the folder it writes is `out_dir`)."""
    prompt, url = TOPICS[topic]
    return [python or sys.executable, "main.py", "--mode", "CASE", "--prompt", prompt, "--sources", url, "--case", "template=explainer", "--case", "plan_only",
            "--case", f"length={length}", "--case", f"llm={llm}", "--case", "formats=16:9", "--case", "manim=off", "--session_dir", out_dir]


def run(topics, out_root, length="standard", llm="auto", runner=subprocess.run, log=print):
    """{topic: metrics} after one script-only run per topic (an error string when no script was written). `runner` replaces subprocess.run (tests)."""
    results = {}
    for topic in topics:
        folder = os.path.join(out_root, topic)
        os.makedirs(folder, exist_ok=True)
        log(f"[Log] Scorecard: {topic}...")
        try:
            done = runner(command(topic, folder, length, llm), capture_output=True, text=True, timeout=1800)
            said = f"{getattr(done, 'stdout', '') or ''} {getattr(done, 'stderr', '') or ''}"
            with open(os.path.join(folder, "script.json"), encoding="utf-8") as f:
                results[topic] = score(json.load(f), length)
            # the model that wrote it: when the cloud model fails the run says so and carries on with the one on this PC (thinner scripts)
            results[topic]["model"] = "local fallback" if llm == "local" or "using the model on this PC" in said or "Local LLM (" in said else "cloud"
        except Exception as e:
            results[topic] = f"no script ({' '.join(str(e).split())[:60]})"
    return results
