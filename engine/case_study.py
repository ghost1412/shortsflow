"""Case explainer, first half: a template of sections, the sources it may use, and a script written from those sources only.

A topic (an event, a failure, a product, a scam, a historic moment, anything that can be explained in sections) goes in with 1-3 source links or pasted notes. The template says
which questions the video answers, in order. The script writer fills one section per question from the sources and nothing else:
a number or a name that no source contains is cut out of the narration, and with no sources at all the script is marked unverified.
Pure functions; the model and the web fetch are passed in, so everything here runs (and is tested) offline.
"""
import json
import os
import re

MAX_COUNTERS = 4         # counter cards that fit a portrait frame above the caption
MAX_CHECKLIST = 3        # checklist rows that fit above the caption bar
SCENES = ("timeline", "flow", "counters", "checklist", "terminal", "quote", "equation", "compare", "chart", "animation", "diagram")
# the layouts the model may choose from by itself (terminal and formula only when a template asks for them: they suit few topics)
AUTO_LAYOUTS = ("timeline", "flow", "counters", "checklist", "quote", "compare", "chart", "diagram")
LAYOUT_HELP = {
    "timeline": "events in order of time; labels are short dated events",
    "flow": "the steps of one mechanism, one after another; labels are the steps",
    "diagram": "how things connect or happen when a plain row of steps is not enough: a process with branches, who talks to whom, states over time, how ideas relate; write Mermaid source in the section's \"diagram\" field (the on_screen labels are then only a fallback)",
    "counters": "two to four big numbers; labels are 'number and what it counts', like '300,000 computers'",
    "checklist": "actions or conclusions; labels are short imperative lines",
    "compare": "two things side by side (before and after, A and B); each label is 'left | right', and the FIRST label holds the two headings like 'Before | After'",
    "chart": "three to five quantities of the same kind compared by bar length; each label is 'Name: number' with the number exactly as the sources give it",
    "quote": "one key line that sums the section up; the first label is the line",
}

PRESETS = {
    # one section that is a single continuous Manim animation over the whole narration (`--mode ANIMATE`)
    "animation": [
        {"id": "story", "title": "The idea, animated", "scene": "animation", "sentences": "10-14",
         "question": "Explain the idea as one continuous visual story, from the first step to the conclusion, building it up piece by piece; each sentence matches one thing that appears on screen."},
    ],
    "case": [
        {"id": "what", "title": "What happened", "question": "What happened, when, to whom, in plain words?", "scene": "timeline"},
        {"id": "how", "title": "How it happened", "question": "How did it work, step by step, explained simply for a non-expert?", "scene": "diagram"},
        {"id": "impact", "title": "The impact", "question": "What was the damage: people, money, data, time?", "scene": "counters"},
        {"id": "prevent", "title": "What could change", "question": "What could have gone differently, or what should happen next?", "scene": "checklist"},
    ],
    "postmortem": [
        {"id": "what", "title": "What broke", "question": "What failed and what did people see?", "scene": "timeline"},
        {"id": "why", "title": "Why it broke", "question": "What was the root cause, step by step?", "scene": "diagram"},
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
        {"id": "how", "title": "How it works", "question": "How does it work, step by step?", "scene": "diagram"},
        {"id": "why", "title": "Why it matters", "question": "Why does it matter, with real numbers if the sources have them?", "scene": "counters"},
        {"id": "do", "title": "What to do", "question": "What should the viewer do or remember?", "scene": "checklist"},
    ],
    # a recipe page: the dish, the steps in order, the quantities / temperatures / times, the tips
    "recipe": [
        {"id": "what", "title": "The dish", "question": "What is this dish, where is it from, and what does it taste like?", "scene": "quote"},
        {"id": "make", "title": "How to make it", "question": "What are the steps in order, with the real quantities, temperatures and times from the source?", "scene": "flow"},
        {"id": "numbers", "title": "The numbers", "question": "Which quantities, temperatures and times matter most (grams, degrees, minutes)? Use only figures the source gives, each with its unit.", "scene": "counters"},
        {"id": "tips", "title": "Tips for success", "question": "What should the cook do or avoid so it turns out well?", "scene": "checklist"},
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
            entry = {"id": sid, "title": str(row.get("title") or sid), "question": str(row["question"]), "scene": scene}
            if re.fullmatch(r"\d{1,2}(-\d{1,2})?", str(row.get("sentences") or "")):
                entry["sentences"] = str(row["sentences"])
            out.append(entry)
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
                    text = fetch(item)
                    if str(text).startswith("%PDF"):           # a PDF behind a link that does not end in .pdf
                        text = case_sources.pdf_text(fetch_raw(item))
                    else:
                        text = _plain(text)
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


def build_prompt(topic, template, sources, layouts="auto"):
    parts = [f"Write an explainer video script about: {topic}", ""]
    if sources:
        parts.append("Use ONLY the facts in these sources. If a source does not say it, do not say it.")
        for s in sources:
            parts.append(f"[{s['id']}] ({s['ref']})\n{s['text']}")
    else:
        parts.append("No sources were given. Use only well-known facts you are certain about, and leave out numbers you are unsure of.")
    parts += ["", "Every section needs several specific sentences with the real names, dates and figures from the sources, not a summary of a summary. "
              "A section about results, impact or why it matters states what the sources report was found, measured or changed (the outcomes), "
              "not how the work was set up; if the sources hold no such outcomes, say what they do claim. "
              "HOOK: the viewer decides in two seconds whether to keep watching. Give a top-level \"hook\": ONE line of 12 words or fewer, the most surprising or "
              "highest-stakes fact the sources report, or a sharp question they answer; no greeting, no \"in this video\", no clickbait the sources do not back. "
              "The first sentence of the first section's narration must also open with that kind of fact, not with background. "
              "When the work is a paper, name the institution or lab at most once and never read out a list of author names. "
              "Advice in the last section may be general, but must not add facts.", "", "One section per question, in this order:"]
    for s in template:
        parts.append(f"- id \"{s['id']}\" ({s['title']}): {s['question']}  " + (f"Default layout: {s['scene']}" if layouts == "auto" else f"Scene kind: {s['scene']}")
                     + (f"  Narration length: {s['sentences']} short sentences." if s.get("sentences") else ""))
    if layouts == "auto":
        parts += ["", "Pick the layout of each section yourself, from this list, whichever shows THAT section best, and do not use the same layout for two sections in a row:"]
        parts += [f"  {name}: {LAYOUT_HELP[name]}" for name in AUTO_LAYOUTS]
        parts.append("  (a section whose default layout is terminal, equation or animation keeps it)")
    parts += ["", "Return raw JSON only:",
              '{"title": "<plain title, no emoji>", "hook": "<12 words or fewer>", "sections": [{"id": "<section id>", "narration": "<4-6 short spoken sentences, concrete: who, what, when, how many, in order>", '
              '"scene": "<the layout you chose for this section>", '
              '"on_screen": ["<3-5 short labels, steps or figures shown on screen, never empty>"], "cites": ["S1"], '
              '"footage": ["<3 or 4 different searches for stock video, 2-4 plain words each, one per step of this section: things a camera can film, no brand, person or place names>"], "diagram": "<Mermaid source, only when the layout is diagram>"}]}',
              'For a section whose scene kind is "equation", every on_screen item is one formula in LaTeX (for example "E = mc^2" or '
              '"\\\\frac{a}{b}"), built up step by step; it must come from the sources.',
              'For a section whose layout is diagram, add the key "diagram" with Mermaid source: the first line names the type (flowchart LR, sequenceDiagram, '
              'stateDiagram-v2, mindmap, timeline or pie); at most 6 nodes; labels of 1 to 4 words; every number and name taken from the sources; no styling lines '
              '(classDef, style, linkStyle, init directives), no HTML. Mermaid places everything itself; a flowchart direction is changed to fit the video shape.',
              'For a section whose layout is animation, on_screen may be an empty list: the whole section is one animated picture, so write the narration '
              'as a walk through the idea in order, each sentence matching one thing that appears on screen.']
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


def pick_layout(default, chosen, previous, layouts="auto"):
    """The layout of a section: the template's `default`, or the model's `chosen` one when layouts are "auto", it is one the model may pick, and
    it is not the same as the section before (then the default is used, and failing that the choice is kept). A section whose default is
    terminal or equation keeps it."""
    if layouts != "auto" or default in ("terminal", "equation", "animation") or chosen not in AUTO_LAYOUTS:
        return default
    if default == "diagram" and chosen == "flow":      # a drawn diagram is the better way to show a process than a plain row of boxes
        return default
    if chosen == previous and default != previous:
        return default
    return chosen


_POWERS = {3: "thousand", 6: "million", 9: "billion", 12: "trillion"}


def spell_powers(label):
    """"3 x 10^9 cycles" (also "3 × 10^9", "3e9") as "3 billion cycles": a counter reads it like a number, not a formula."""
    def repl(m):
        word = _POWERS.get(int(m.group(2)))
        return f"{m.group(1)} {word}" if word else m.group(0)
    return re.sub(r"(\d+(?:\.\d+)?)\s*(?:[x×]|\\times)\s*10\s*\^\s*\{?(\d+)\}?", repl, str(label))


def fit_layout(scene, labels, previous=None):
    """Counters show big numbers: with fewer than two labels that start with a number (or hold a short figure) the cards would be long sentences
    crowding each other, so the section becomes a checklist (a timeline when the section before is one)."""
    if scene != "counters":
        return scene
    numbered = [x for x in labels if re.match(r"\s*[$€£]?\d", x)]
    if len(numbered) >= 2:
        return scene
    return "timeline" if previous == "checklist" else "checklist"


def _undouble(text):
    """Single quote marks where a model wrote two at the start or the end of a string (`[""Like this.""]`, `[""Like this."]`, `["Like this.""]`)."""
    text = re.sub(r'(\[\s*|(?m:^\s*)|,\s*)""(?=[^",\]\s])', lambda m: m.group(1) + '"', text)
    return re.sub(r'(?<=[^",\[\s])""(?=\s*(?:[\],]|$))', '"', text, flags=re.M)


def parse_reply(reply):
    """The JSON object in a model's answer, or None. A small model often doubles the quote marks around a quoted line
    (`[""Like this?""]`), which is not valid JSON: such a line is repaired once before giving up."""
    match = re.search(r"\{.*\}", str(reply), re.S)
    if not match:
        return None
    text = match.group(0)
    for candidate in (text, _undouble(text)):
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def resolve_diagram(raw, source_text, ask, title, check=None):
    """The Mermaid source for a diagram section, or '' when none can be made: the model's text is cleaned, held to the sources (a number or name in
    a label that no source holds), and parsed by Mermaid; a problem is sent back to the model once. `check(code)` returns (ok, reason)."""
    from engine import case_mermaid
    check = check or case_mermaid.check
    code = case_mermaid.clean(raw)
    for attempt in (1, 2):
        problem = ""
        if not code:
            problem = "there is no Mermaid source (start with a line such as flowchart LR)"
        else:
            bad = case_mermaid.unsupported(code, source_text) if source_text else []
            if bad:
                problem = "these numbers or names are not in the sources, so remove them: " + ", ".join(bad[:4])
            else:
                ok, reason = check(code)
                if ok:
                    return code
                problem = "Mermaid could not read it: " + reason
        if attempt == 2:
            break
        try:
            code = case_mermaid.clean(ask("Fix this Mermaid diagram for the section '" + str(title) + "'. Problem: " + problem
                                          + "\n\nDiagram:\n" + str(raw or "")[:1500] + "\n\nReturn ONLY the corrected Mermaid source, no explanation, no code fence."))
        except Exception:
            return ""
    return ""


def diagram_for(section, topic, ask, source_text=None, check=None):
    """Mermaid source for an existing section (its narration and labels in, a diagram out), or '' when none can be made valid and grounded. Used to turn a
    section into a diagram after the script is written."""
    labels = "; ".join(str(x) for x in section.get("on_screen") or [])
    nl = "\n"
    reply = ask("Draw ONE Mermaid diagram that explains this part of an explainer video about: " + str(topic) + nl + nl + "Section: " + str(section.get("title", ""))
                + nl + "What the narrator says over it: " + str(section.get("narration", "")) + nl + "Key labels: " + labels
                + nl + nl + "Rules: the first line names the type (flowchart LR, sequenceDiagram, stateDiagram-v2, mindmap or timeline); at most 6 nodes; labels of 1 to 4 words; "
                "every number and name taken from the narration above; no styling lines (classDef, style, linkStyle, init directives), no HTML. "
                "Return ONLY the Mermaid source, no explanation, no code fence.")
    return resolve_diagram(reply, source_text, ask, section.get("title", ""), check)


def write_script(topic, template, sources, ask, layouts="auto", check_diagram=None):
    """The script: {"title", "verified", "sources": [{id, ref}], "sections": [{id, title, scene, narration, on_screen, cites}],
    "dropped": [{section, sentence, unsupported}]}. `ask(prompt)` returns the model's text. Raises ValueError when the answer holds no
    usable section. With sources, a sentence holding a number or name no source contains is dropped; without, nothing can be checked
    and "verified" is False."""
    reply = ask(build_prompt(topic, template, sources, layouts))
    data = parse_reply(reply)
    rows = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("The model's answer had no sections.")
    by_id = {str(r.get("id")): r for r in rows if isinstance(r, dict)}
    source_text = " ".join(s["text"] for s in sources)
    sections, dropped = [], []
    previous = None
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
        labels = [spell_powers(x) for x in labels]
        if not narration:
            continue
        known = {s["id"] for s in sources}
        cites = [c for c in (row.get("cites") or []) if c in known] if isinstance(row.get("cites"), list) else []
        raw_footage = row.get("footage")
        raw_footage = raw_footage if isinstance(raw_footage, list) else [raw_footage]
        footage = [p for p in (" ".join(re.findall(r"[A-Za-z0-9]+", str(x or "")))[:60] for x in raw_footage) if p][:4]
        scene = pick_layout(sec["scene"], row.get("scene"), previous, layouts)
        if layouts == "auto":
            scene = fit_layout(scene, labels, previous)
        diagram = ""
        if scene == "diagram":
            grounding = source_text if sources else None
            if row.get("diagram"):
                diagram = resolve_diagram(row.get("diagram"), grounding, ask, sec["title"], check_diagram)
            if not diagram:                        # the model picked the layout but wrote no usable diagram: ask for one from the section's own text
                diagram = diagram_for({"title": sec["title"], "narration": narration, "on_screen": labels}, topic, ask, grounding, check_diagram)
            if not diagram:
                scene = "flow"                     # the diagram could not be made valid and grounded: the plain row of steps shows the labels
        previous = scene
        if scene == "counters":
            labels = labels[:MAX_COUNTERS]
        if scene == "checklist":
            labels = labels[:MAX_CHECKLIST]       # more rows run into the caption bar
        sections.append({"id": sec["id"], "title": sec["title"], "scene": scene, "narration": narration,
                         "on_screen": labels, "cites": cites, "footage": footage})
        if diagram:
            sections[-1]["diagram"] = diagram
    if not sections:
        raise ValueError("Nothing usable was left in the script" + (" after the unsupported claims were removed." if dropped else "."))
    hook = " ".join(str(data.get("hook") or "").split())[:110]
    if hook and sources and unsupported(hook, source_text):        # a hook is held to the same rule as every sentence: nothing the sources do not say
        hook = ""
    return {"title": str(data.get("title") or topic).strip()[:120], "hook": hook, "verified": bool(sources),
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
    lines = [f"TITLE: {script.get('title', '')}", f"HOOK: {script.get('hook', '')}", ""]
    for n, sec in enumerate(script["sections"], start=1):
        footage = sec.get("footage") or []
        footage = [footage] if isinstance(footage, str) else footage
        lines += [f"== {n}. {sec.get('title', '')} [{sec.get('scene', 'quote')}]", f"FOOTAGE: {'; '.join(footage)}", "NARRATION:",
                  str(sec.get("narration", "")).strip(), "LABELS:"]
        lines += [f"- {x}" for x in sec.get("on_screen") or []]
        if sec.get("diagram"):
            lines += ["DIAGRAM:", str(sec["diagram"]).strip()]
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
    hook = re.search(r"(?m)^HOOK:[ \t]*(.*)$", head)
    out["hook"] = (" ".join(hook.group(1).split()) if hook else str(base.get("hook", "")))[:110]
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
        diagram = re.search(r"(?ms)^DIAGRAM:[ \t]*\n(.*)\Z", rest)
        if diagram:
            from engine import case_mermaid
            code = case_mermaid.clean(diagram.group(1))
            if code:
                sec["diagram"] = code
            rest = rest[:diagram.start()]
        labels = re.search(r"(?ms)^LABELS:[ \t]*\n?(.*)\Z", rest)
        sec["on_screen"] = [x.strip()[:80] for x in re.findall(r"(?m)^\s*-\s*(.+)$", labels.group(1) if labels else "") if x.strip()][:6]
        sections.append(sec)
    if not sections:
        raise ValueError("The script has no sections left.")
    out["sections"] = sections
    out["edited"] = True
    return out
