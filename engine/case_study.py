"""Case explainer, first half: a template of sections, the sources it may use, and a script written from those sources only.

A topic (an event, a failure, a product, a scam, a historic moment, anything that can be explained in sections) goes in with 1-3 source links or pasted notes. The template says
which questions the video answers, in order. The script writer fills one section per question from the sources and nothing else:
a number or a name that no source contains is cut out of the narration, and with no sources at all the script is marked unverified.
Pure functions; the model and the web fetch are passed in, so everything here runs (and is tested) offline.
"""
import json
import os
import re

SCENES = ("timeline", "flow", "counters", "checklist", "terminal", "quote")

PRESETS = {
    "case": [
        {"id": "what", "title": "What happened", "question": "What happened, when, to whom, in plain words?", "scene": "timeline"},
        {"id": "how", "title": "How it happened", "question": "How did it work, step by step, explained simply for a non-expert?", "scene": "flow"},
        {"id": "impact", "title": "The impact", "question": "What was the damage: people, money, data, time?", "scene": "counters"},
        {"id": "prevent", "title": "What could change", "question": "What could have gone differently, or what should happen next?", "scene": "checklist"},
    ],
    "postmortem": [
        {"id": "what", "title": "What broke", "question": "What failed and what did people see?", "scene": "timeline"},
        {"id": "why", "title": "Why it broke", "question": "What was the root cause, step by step?", "scene": "flow"},
        {"id": "impact", "title": "The cost", "question": "Who was affected, for how long, and what did it cost?", "scene": "counters"},
        {"id": "fix", "title": "What changed", "question": "What was fixed, and what should others do?", "scene": "checklist"},
    ],
    "history": [
        {"id": "context", "title": "The situation", "question": "What was the situation before it began?", "scene": "timeline"},
        {"id": "events", "title": "What happened", "question": "What happened, in order?", "scene": "flow"},
        {"id": "result", "title": "The result", "question": "What changed afterwards?", "scene": "counters"},
        {"id": "lesson", "title": "What we learn", "question": "What is the lesson?", "scene": "quote"},
    ],
    "explainer": [
        {"id": "what", "title": "What it is", "question": "What is it, in one clear idea?", "scene": "quote"},
        {"id": "how", "title": "How it works", "question": "How does it work, step by step?", "scene": "flow"},
        {"id": "why", "title": "Why it matters", "question": "Why does it matter, with real numbers if the sources have them?", "scene": "counters"},
        {"id": "do", "title": "What to do", "question": "What should the viewer do or remember?", "scene": "checklist"},
    ],
}


def load_template(spec="case"):
    """Sections of a template: a preset name, or the path of a JSON file holding a list of {id, title, question, scene?}.
    Raises ValueError for an unknown name or a file that is not a usable template."""
    if spec in PRESETS:
        return [dict(s) for s in PRESETS[spec]]
    if spec and os.path.isfile(str(spec)):
        try:
            with open(spec, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            raise ValueError(f"The template file could not be read: {e}")
        rows = data.get("sections") if isinstance(data, dict) else data
        out, seen = [], set()
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or not row.get("id") or not row.get("question"):
                raise ValueError("Every template section needs an id and a question.")
            sid = str(row["id"])
            if sid in seen:
                raise ValueError(f"Template section id '{sid}' is used twice.")
            seen.add(sid)
            scene = row.get("scene") if row.get("scene") in SCENES else "quote"
            out.append({"id": sid, "title": str(row.get("title") or sid), "question": str(row["question"]), "scene": scene})
        if not out:
            raise ValueError("The template has no sections.")
        return out
    raise ValueError(f"Unknown template '{spec}'. Presets: {', '.join(PRESETS)}; or give the path of a JSON file.")


MAX_SOURCE_CHARS = 6000
MAX_SOURCES = 3


def _plain(html):
    html = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(a, b)
    return " ".join(text.split())


def default_fetch(url, timeout=15):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; reader)"})
    r.raise_for_status()
    return r.text


def gather_sources(items, fetch=None):
    """[{"id": "S1", "ref", "text"}] from up to three items: a link (fetched), the path of a text file, or pasted text.
    Items that cannot be read are skipped (the second return value lists them with the reason)."""
    fetch = fetch or default_fetch
    sources, skipped = [], []
    for item in [str(i).strip() for i in (items or []) if str(i).strip()][:MAX_SOURCES + 5]:
        if len(sources) >= MAX_SOURCES:
            skipped.append((item[:60], f"only {MAX_SOURCES} sources are used"))
            continue
        try:
            if re.match(r"https?://\S+$", item):
                text, ref = _plain(fetch(item)), item
            elif os.path.isfile(item):
                with open(item, encoding="utf-8", errors="replace") as f:
                    text, ref = _plain(f.read()), os.path.basename(item)
            else:
                text, ref = " ".join(item.split()), "pasted notes"
        except Exception as e:
            skipped.append((item[:60], str(e)[:100]))
            continue
        if len(text) < 40:
            skipped.append((item[:60], "almost no text"))
            continue
        sources.append({"id": f"S{len(sources) + 1}", "ref": ref, "text": text[:MAX_SOURCE_CHARS]})
    return sources, skipped


def build_prompt(topic, template, sources):
    parts = [f"Write an explainer video script about: {topic}", ""]
    if sources:
        parts.append("Use ONLY the facts in these sources. If a source does not say it, do not say it.")
        for s in sources:
            parts.append(f"[{s['id']}] ({s['ref']})\n{s['text']}")
    else:
        parts.append("No sources were given. Use only well-known facts you are certain about, and leave out numbers you are unsure of.")
    parts += ["", "One section per question, in this order:"]
    for s in template:
        parts.append(f"- id \"{s['id']}\" ({s['title']}): {s['question']}  Scene kind: {s['scene']}")
    parts += ["", "Return raw JSON only:",
              '{"title": "<plain title, no emoji>", "sections": [{"id": "<section id>", "narration": "<2-4 short spoken sentences>", '
              '"on_screen": ["<3-5 short labels or steps shown on screen>"], "cites": ["S1"]}]}']
    return "\n".join(parts)


_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_NAME = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-zA-Z0-9]{3,}\b")


def _digits(s):
    return re.sub(r"\D", "", s)


def unsupported(sentence, source_text):
    """The numbers and capitalised names in `sentence` that the sources never mention (case-insensitive; numbers compared by digits)."""
    low = source_text.lower()
    source_numbers = {_digits(n) for n in _NUMBER.findall(source_text)}
    out = []
    for n in _NUMBER.findall(sentence):
        if _digits(n) not in source_numbers:
            out.append(n)
    for name in _NAME.findall(sentence):
        if name.lower() not in low:
            out.append(name)
    return out


def clean_narration(text, source_text):
    """(narration, dropped): `text` without the sentences that hold something the sources do not."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(text or "")) if s.strip()]
    kept, dropped = [], []
    for s in sentences:
        bad = unsupported(s, source_text)
        (dropped if bad else kept).append((s, bad) if bad else s)
    return " ".join(kept), dropped


def write_script(topic, template, sources, ask):
    """The script: {"title", "verified", "sources": [{id, ref}], "sections": [{id, title, scene, narration, on_screen, cites}],
    "dropped": [{section, sentence, unsupported}]}. `ask(prompt)` returns the model's text. Raises ValueError when the answer holds no
    usable section. With sources, a sentence holding a number or name no source contains is dropped; without, nothing can be checked
    and "verified" is False."""
    reply = ask(build_prompt(topic, template, sources))
    try:
        match = re.search(r"\{.*\}", str(reply), re.S)
        data = json.loads(match.group(0)) if match else None
    except ValueError:
        data = None
    rows = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("The model's answer had no sections.")
    by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict)}
    source_text = " ".join(s["text"] for s in sources)
    sections, dropped = [], []
    for sec in template:
        row = by_id.get(sec["id"])
        if not row:
            continue
        narration = str(row.get("narration") or "").strip()
        if sources:
            narration, cut = clean_narration(narration, source_text)
            dropped += [{"section": sec["id"], "sentence": s, "unsupported": bad} for s, bad in cut]
        labels = [str(x).strip()[:80] for x in (row.get("on_screen") or []) if str(x).strip()][:6] if isinstance(row.get("on_screen"), list) else []
        if sources:
            labels = [x for x in labels if not unsupported(x, source_text)]
        if not narration:
            continue
        known = {s["id"] for s in sources}
        cites = [c for c in (row.get("cites") or []) if c in known] if isinstance(row.get("cites"), list) else []
        sections.append({"id": sec["id"], "title": sec["title"], "scene": sec["scene"], "narration": narration,
                         "on_screen": labels, "cites": cites})
    if not sections:
        raise ValueError("Nothing usable was left in the script" + (" after the unsupported claims were removed." if dropped else "."))
    return {"title": str(data.get("title") or topic).strip()[:120], "verified": bool(sources),
            "sources": [{"id": s["id"], "ref": s["ref"]} for s in sources], "sections": sections, "dropped": dropped}
