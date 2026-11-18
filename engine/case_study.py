"""Case explainer, first half: a template of sections, the sources it may use, and a script written from those sources only.

A topic (an event, a failure, a product, a scam, a historic moment, anything that can be explained in sections) goes in with 1-3 source links or pasted notes. The template says
which questions the video answers, in order. The script writer fills one section per question from the sources and nothing else:
a number or a name that no source contains is cut out of the narration, and with no sources at all the script is marked unverified.
Pure functions; the model and the web fetch are passed in, so everything here runs (and is tested) offline.
"""
import json
import os
import re

SCENES = ("timeline", "flow", "counters", "checklist", "terminal", "quote", "equation")

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


MAX_SOURCE_CHARS = 14000
MAX_SOURCES = 3


def _paragraphs(html):
    """The running text of a page: the content of its <p> elements when there are enough of them (menus, footers and cookie notices
    are not paragraphs), else None."""
    found = re.findall(r"(?is)<p(?:\s[^>]*)?>(.*?)</p>", html)
    text = " ".join(" ".join(re.sub(r"(?s)<[^>]+>", " ", p).split()) for p in found)
    return text if len(found) >= 3 and len(text) > 400 else None


def _plain(html):
    paragraphs = _paragraphs(html)
    if paragraphs:
        html = paragraphs
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


def default_fetch_raw(url, timeout=30):
    """The bytes of a link (a PDF)."""
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; reader)"})
    r.raise_for_status()
    return r.content


def gather_sources(items, fetch=None, fetch_raw=None, youtube=None, workdir=None, audio=None, transcribe=None, trim=None):
    """[{"id": "S1", "ref", "text"}] from up to three items: a web link (its paragraphs), a PDF link or file, a YouTube link (its captions), a
    caption file (.srt, .vtt), a text file, or pasted text. Items that cannot be read are skipped (the second return value lists them with the
    reason). A YouTube video without captions, and an audio or video file, are listened to by the speech model on this PC (minutes, first 40 minutes
    only). `fetch`, `fetch_raw`, `youtube`, `audio`, `transcribe`, `trim` replace the network and speech readers (tests)."""
    from engine import case_sources
    fetch = fetch or default_fetch
    fetch_raw = fetch_raw or default_fetch_raw
    sources, skipped = [], []
    for item in [str(i).strip() for i in (items or []) if str(i).strip()][:MAX_SOURCES + 5]:
        if len(sources) >= MAX_SOURCES:
            skipped.append((item[:60], f"only {MAX_SOURCES} sources are used"))
            continue
        try:
            if re.match(r"https?://\S+$", item):
                if case_sources.is_youtube(item):
                    import tempfile
                    folder = workdir or tempfile.mkdtemp(prefix="case_captions_")
                    try:
                        text = case_sources.youtube_text(item, folder, youtube)
                    except case_sources.NoCaptions:
                        print("[Log] This video has no captions: listening to its audio on this PC (this can take several minutes)...")
                        text = case_sources.transcribe_file(case_sources.youtube_audio(item, folder, audio), folder, transcribe=transcribe, trim=trim)
                elif case_sources.is_pdf_name(item):
                    text = case_sources.pdf_text(fetch_raw(item))
                else:
                    text = _plain(fetch(item))
                ref = item
            elif os.path.isfile(item) and case_sources.is_audio_or_video_file(item):
                import tempfile
                print(f"[Log] Listening to {os.path.basename(item)} on this PC (this can take several minutes)...")
                text, ref = case_sources.transcribe_file(item, workdir or tempfile.mkdtemp(prefix="case_listen_"), transcribe=transcribe, trim=trim), os.path.basename(item)
            elif os.path.isfile(item):
                text, ref = _plain(case_sources.read_file(item)), os.path.basename(item)
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
    parts += ["", "Every section needs several specific sentences with the real names, dates and figures from the sources, not a summary of a summary. "
              "Advice in the last section may be general, but must not add facts.", "", "One section per question, in this order:"]
    for s in template:
        parts.append(f"- id \"{s['id']}\" ({s['title']}): {s['question']}  Scene kind: {s['scene']}")
    parts += ["", "Return raw JSON only:",
              '{"title": "<plain title, no emoji>", "sections": [{"id": "<section id>", "narration": "<4-6 short spoken sentences, concrete: who, what, when, how many, in order>", '
              '"on_screen": ["<3-5 short labels, steps or figures shown on screen, never empty>"], "cites": ["S1"], '
              '"footage": ["<3 or 4 different searches for stock video, 2-4 plain words each, one per step of this section: things a camera can film, no brand, person or place names>"]}]}',
              'For a section whose scene kind is "equation", every on_screen item is one formula in LaTeX (for example "E = mc^2" or '
              '"\\\\frac{a}{b}"), built up step by step; it must come from the sources.']
    return "\n".join(parts)


_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_NAME = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-zA-Z0-9]{3,}\b")


_ORDINAL = re.compile(r"\b(?:step|stage|phase|part|point|number|no\.?)\s*\d+\b[:.)-]?|^\s*\d+[.)]\s", re.I)


def _digits(s):
    return re.sub(r"\D", "", s)


def unsupported(sentence, source_text):
    """The numbers and capitalised names in `sentence` that the sources never mention (case-insensitive; numbers compared by digits)."""
    low = source_text.lower()
    source_numbers = {_digits(n) for n in _NUMBER.findall(source_text)}
    sentence = _ORDINAL.sub(" ", sentence)         # "Step 2:" numbers the steps of a diagram; it is not a claim about the world
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
        raw_footage = row.get("footage")
        raw_footage = raw_footage if isinstance(raw_footage, list) else [raw_footage]
        footage = [p for p in (" ".join(re.findall(r"[A-Za-z0-9]+", str(x or "")))[:60] for x in raw_footage) if p][:4]
        sections.append({"id": sec["id"], "title": sec["title"], "scene": sec["scene"], "narration": narration,
                         "on_screen": labels, "cites": cites, "footage": footage})
    if not sections:
        raise ValueError("Nothing usable was left in the script" + (" after the unsupported claims were removed." if dropped else "."))
    return {"title": str(data.get("title") or topic).strip()[:120], "verified": bool(sources),
            "sources": [{"id": s["id"], "ref": s["ref"]} for s in sources], "sections": sections, "dropped": dropped}


def script_to_text(script):
    """The script as plain text a person can edit (the review step): a TITLE line, then one block per section.

        TITLE: ...
        == 1. What happened [timeline]
        FOOTAGE: server room; computer screen
        NARRATION:
        The spoken text, as many lines as needed.
        LABELS:
        - first thing shown on screen
        - second thing
    """
    lines = [f"TITLE: {script.get('title', '')}", ""]
    for n, sec in enumerate(script["sections"], start=1):
        footage = sec.get("footage") or []
        footage = [footage] if isinstance(footage, str) else footage
        lines += [f"== {n}. {sec.get('title', '')} [{sec.get('scene', 'quote')}]", f"FOOTAGE: {'; '.join(footage)}", "NARRATION:",
                  str(sec.get("narration", "")).strip(), "LABELS:"]
        lines += [f"- {x}" for x in sec.get("on_screen") or []]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def script_from_text(text, base):
    """The script after a person's edits: `base` with the title, and each block's heading, scene, footage phrases, narration and labels taken
    from `text`. A block is matched to its section by its number; a section whose block was deleted is dropped, and sources, citations and
    the verified flag are kept. Raises ValueError when nothing usable is left or a block has no narration."""
    blocks = re.split(r"(?m)^==\s*", str(text or ""))
    head, blocks = blocks[0], blocks[1:]
    title = re.search(r"(?m)^TITLE:\s*(.+)$", head)
    out = dict(base)
    out["title"] = (title.group(1).strip() if title else str(base.get("title", "")))[:120]
    sections = []
    for block in blocks:
        first, _, rest = block.partition("\n")
        m = re.match(r"(\d+)\.\s*(.*?)\s*(?:\[(\w+)\])?\s*$", first.strip())
        if not m or not (1 <= int(m.group(1)) <= len(base["sections"])):
            raise ValueError(f"A section heading must look like '== 2. Title [scene]' with a number from 1 to {len(base['sections'])}: '{first.strip()[:40]}'.")
        sec = dict(base["sections"][int(m.group(1)) - 1])
        if m.group(2):
            sec["title"] = m.group(2)
        if m.group(3) in SCENES:
            sec["scene"] = m.group(3)
        footage = re.search(r"(?m)^FOOTAGE:[ \t]*(.*)$", rest)
        if footage:
            sec["footage"] = [p.strip() for p in footage.group(1).split(";") if p.strip()][:4]
        narration = re.search(r"(?ms)^NARRATION:[ \t]*\n?(.*?)(?=^LABELS:|\Z)", rest)
        sec["narration"] = " ".join((narration.group(1) if narration else "").split())
        if not sec["narration"]:
            raise ValueError(f"Section {m.group(1)} ('{sec.get('title', '')}') has no narration.")
        labels = re.search(r"(?ms)^LABELS:[ \t]*\n?(.*)\Z", rest)
        sec["on_screen"] = [x.strip()[:80] for x in re.findall(r"(?m)^\s*-\s*(.+)$", labels.group(1) if labels else "") if x.strip()][:6]
        sections.append(sec)
    if not sections:
        raise ValueError("The script has no sections left.")
    out["sections"] = sections
    out["edited"] = True
    return out
