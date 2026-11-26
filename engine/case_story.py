"""The story look of the case explainer (`--case template=story`): who is on screen when, drawn by code.

One model call plans the whole script: the people in it (a spec each, see `engine/story_art.py`), and for every section the sky and ground of its backdrop and a list
of beats. A beat starts at a sentence and says who that sentence is about (a character bust rises in with a gold name plate), or shows a title card (no character),
or a big figure with its label. Everything the model says is checked: only known parts and colours, only characters it described, a figure only when the
narration says it. A person is saved in the library (`~/.shortsflow/characters`), so the same person looks the same in the next video.
The plan is saved with the run (`story_plan.json`) so a resumed run does not ask again.
"""
import hashlib
import json
import os
import re

from engine import story_art

MAX_CHARACTERS = 6
MAX_NAME = 26
MAX_ROLE = 42


def library_dir():
    return os.getenv("SHORTSFLOW_CHARACTERS") or os.path.join(os.path.expanduser("~"), ".shortsflow", "characters")


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:40]


def load_library(directory=None):
    """{name: spec} of the people drawn in earlier videos."""
    directory = directory or library_dir()
    out = {}
    try:
        for fn in sorted(os.listdir(directory)):
            if fn.endswith(".json"):
                with open(os.path.join(directory, fn), encoding="utf-8") as f:
                    row = json.load(f)
                if isinstance(row, dict) and row.get("name") and isinstance(row.get("spec"), dict):
                    out[str(row["name"])] = story_art.clean_spec(row["spec"])
    except (OSError, ValueError):
        pass
    return out


def save_character(name, spec, directory=None):
    directory = directory or library_dir()
    try:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, _slug(name) + ".json"), "w", encoding="utf-8") as f:
            json.dump({"name": name, "spec": spec}, f, indent=1)
    except OSError:
        pass


def sentences(text):
    """The sentences of a narration, in order."""
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+", str(text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def request(script, known):
    """The prompt that plans the story's pictures."""
    lines = []
    for si, sec in enumerate(script["sections"], 1):
        lines.append(f"Section {si} (id \"{sec['id'] if 'id' in sec else si}\", {sec.get('title', '')}):")
        for k, s in enumerate(sentences(sec.get("narration")), 1):
            lines.append(f"  {k}. {s}")
    known_line = ("People already drawn (use these exact names for them, do not redescribe them): " + ", ".join(sorted(known)) + ". ") if known else ""
    return (
        "You are the art director of a short animated story video. Plan its pictures from this narration.\n\n" + "\n".join(lines) + "\n\n"
        + known_line +
        "Describe each PERSON (or god or creature with a human shape) who is named in the narration, at most " + str(MAX_CHARACTERS) + ", as a bust. Use the look the story's tradition gives them. "
        "For each, choose only from these values: "
        f"skin: {', '.join(story_art.SKIN)}; headgear: {', '.join(story_art.HEADGEAR)}; headgear_colour, outfit_colour, trim_colour: {', '.join(story_art.COLOURS)}; "
        f"facial_hair: {', '.join(story_art.FACIAL_HAIR)}; outfit: {', '.join(story_art.OUTFITS)}; ornaments (a list): {', '.join(story_art.ORNAMENTS)}; "
        f"mood: {', '.join(story_art.MOODS)}; weapon: {', '.join(story_art.WEAPONS)}; age: {', '.join(story_art.AGES)}.\n"
        "For EACH section choose the backdrop: sky: " + ", ".join(story_art.SKIES) + " (the mood of the moment: sunset or dusk for calm or sad, fire or storm for battle and "
        "danger, rays for a solemn card, night for secrets, dawn for hope; day only for a peaceful, bright scene, and vary the sky between sections) and ground: " + ", ".join(story_art.GROUNDS) + ".\n"
        "Then list the beats of each section. A beat starts at a sentence number and says what is on screen from there until the next beat. It is ONE of two kinds. "
        "A CHARACTER beat: \"character\" is the person that sentence is about or who speaks in it, and their name is shown. A CARD beat: \"character\" is null, \"name\" is the "
        "card's title of at most 3 words, and \"emblem\" is the one object that shows it, from: " + ", ".join(story_art.EMBLEMS) + " (or empty when none fits). Use a card when the "
        "sentence is about a thing, a curse, a weapon or someone you did not describe. \"role\" is a short line under the name of at most 5 words (like \"Son of the Sun\"; empty is fine). "
        "A sentence that holds a number worth showing big may "
        "have \"big\" (the number exactly as the narration says it) and \"label\" (at most 4 words). Use a new beat when the person on screen should change, about every "
        "one or two sentences, and always a beat at sentence 1 of every section. Never invent facts: only what the narration says.\n\n"
        "Reply with raw JSON only:\n"
        "{\"characters\": {\"Name\": {\"skin\": \"...\", \"headgear\": \"...\", ...}}, \"sections\": [{\"sky\": \"...\", \"ground\": \"...\", \"beats\": "
        "[{\"sentence\": 1, \"character\": \"Name\" or null, \"name\": \"...\", \"role\": \"...\", \"emblem\": \"\", \"big\": \"\", \"label\": \"\"}]}]}")


def _parse(reply):
    from engine.script_gen import robust_json_parse
    try:
        data = robust_json_parse(reply)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _clip(text, n):
    return " ".join(str(text or "").split())[:n].strip()


def check_plan(reply, script, library=None):
    """(plan, problem): the plan with only usable parts. {"characters": {name: spec}, "sections": [{"sky", "ground", "beats": [{"sentence", "character", "name", "role",
    "big", "label"}]}]}, one entry of sections per section of the script. A section the model left out gets a calm default, so a plan is never refused for that alone."""
    data = _parse(reply) if isinstance(reply, str) else reply
    if not isinstance(data, dict):
        return None, "the answer was not a JSON object"
    library = library or {}
    chars = {}
    raw_chars = data.get("characters") if isinstance(data.get("characters"), dict) else {}
    for name, spec in list(raw_chars.items())[:MAX_CHARACTERS]:
        name = _clip(name, MAX_NAME)
        if name:
            chars[name] = library.get(name) or story_art.clean_spec(spec)
    raw_sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    out_sections = []
    for si, sec in enumerate(script["sections"]):
        row = raw_sections[si] if si < len(raw_sections) and isinstance(raw_sections[si], dict) else {}
        count = len(sentences(sec.get("narration")))
        narration = str(sec.get("narration") or "")
        said_numbers = {re.sub(r"\D", "", n) for n in re.findall(r"\d[\d,.]*", narration)}
        beats, seen = [], set()
        for b in row.get("beats") if isinstance(row.get("beats"), list) else []:
            if not isinstance(b, dict):
                continue
            try:
                k = int(b.get("sentence"))
            except (TypeError, ValueError):
                continue
            if not 1 <= k <= max(count, 1) or k in seen:
                continue
            seen.add(k)
            who = _clip(b.get("character"), MAX_NAME) if b.get("character") else ""
            who = who if who in chars else (next((n for n in chars if n.lower() == who.lower()), "") if who else "")
            big = _clip(b.get("big"), 8)
            if big and re.sub(r"\D", "", big) not in said_numbers:
                big = ""                                       # a figure only when the narration says it
            emblem = str(b.get("emblem") or "").strip().lower()
            name = _clip(b.get("name") or who, MAX_NAME)
            if who and name.lower() != who.lower():
                if name and not any(w in who.lower().split() for w in re.findall(r"[a-z]+", name.lower())):
                    who = ""                      # a title about someone or something else ("Abhimanyu" over Krishna's face): it is a card, not this face
                else:
                    name = who                    # "Krishna's Counsel" over Krishna: the plate under a face is that person's own name
            beat = {"sentence": k, "character": who or None, "name": name, "role": _clip(b.get("role"), MAX_ROLE),
                    "emblem": emblem if not who and not big and emblem in story_art.EMBLEMS else "",
                    "big": big, "label": _clip(b.get("label"), 30) if big else ""}
            if beat["character"] or beat["name"] or beat["big"]:
                beats.append(beat)
        beats.sort(key=lambda x: x["sentence"])
        if not beats or beats[0]["sentence"] != 1:
            first = next(iter(chars), None) if chars else None
            beats.insert(0, {"sentence": 1, "character": first, "name": first or _clip(sec.get("title"), MAX_NAME), "role": "", "emblem": "", "big": "", "label": ""})
        sky = str(row.get("sky") or "").strip().lower()
        ground = str(row.get("ground") or "").strip().lower()
        out_sections.append({"sky": sky if sky in story_art.SKIES else "sunset", "ground": ground if ground in story_art.GROUNDS else "none", "beats": beats})
    if not chars and not any(b["name"] for s in out_sections for b in s["beats"]):
        return None, "no character or card was planned"
    return {"characters": chars, "sections": out_sections}, ""


def _key(script, aspect):
    raw = "|".join([str(script.get("title", "")), *[str(s.get("narration", "")) for s in script["sections"]], aspect, "story-v2"])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def plan(script, ask, session_dir, aspect="9:16", library=None):
    """The checked plan for the whole script (asked once per run and saved), None when two tries do not give a usable one."""
    key = _key(script, "any")
    path = os.path.join(session_dir, "story_plan.json")
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("key") == key:
            return saved["plan"]
    except (OSError, ValueError, KeyError):
        pass
    library = load_library() if library is None else library
    prompt, problem = request(script, library), ""
    for _ in range(2):
        try:
            reply = ask(prompt + (f"\n\nYour last answer could not be used: {problem}. Answer again, following the format exactly." if problem else ""))
        except Exception as e:
            print(f"[Warning] The text model could not plan the story's pictures ({' '.join(str(e).split())[:100]}).")
            return None
        plan_, problem = check_plan(reply, script, library)
        if plan_:
            for name, spec in plan_["characters"].items():
                if name not in library:
                    save_character(name, spec)
            os.makedirs(session_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"key": key, "plan": plan_}, f, indent=1)
            return plan_
        print(f"[Log] The story plan was not usable: {problem}.")
    return None


SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def beat_times(narration, words, duration, beats):
    """[(from, to)] seconds for each beat: a beat starts when its sentence starts, found by counting words (the voice's words follow the narration's words one for
    one, give or take a few), and ends where the next one starts; the first starts at 0 and the last lasts to `duration`."""
    sents = sentences(narration)
    total = sum(len(s.split()) for s in sents) or 1
    starts, before = [], 0
    for s in sents:
        starts.append(before)
        before += len(s.split())
    out = []
    for i, b in enumerate(beats):
        if i == 0:
            t = 0.0
        else:
            idx = starts[min(b["sentence"], len(starts)) - 1] if starts else 0
            j = min(len(words) - 1, int(round(idx * len(words) / total))) if words else 0
            t = max(0.0, float(words[j]["start"]) - 0.1) if words else duration * idx / total
        out.append(t)
    out = [round(t, 2) for t in out]
    ends = out[1:] + [round(duration, 2)]
    return [(a, max(a + 0.5, b)) for a, b in zip(out, ends)]


def attach(script, session_dir, aspect, ask, words, timing):
    """[None | {"kind": "story", "backdrop": svg path, "beats": [{"from", "to", "character": svg path or None, "name", "role", "big", "label"}]}] per section; None for the
    sections that are not story scenes and for all of them when the plan cannot be made (then each shows its text as a quote)."""
    if not any(s.get("scene") == "story" for s in script["sections"]):
        return [None] * len(script["sections"])
    plan_ = plan(script, ask, session_dir, aspect) if ask is not None else None
    if not plan_:
        print("[Warning] No story pictures could be planned; the story sections show their text as quotes.")
        return [None] * len(script["sections"])
    w, h = SIZES.get(aspect, SIZES["9:16"])
    folder = os.path.join(session_dir, "story_art")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for name, spec in plan_["characters"].items():
        p = os.path.join(folder, f"char_{_slug(name)}.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write(story_art.character_svg(spec))
        paths[name] = p
    emblems = {}
    for kind in {b.get("emblem") for s in plan_["sections"] for b in s["beats"] if b.get("emblem")}:
        p = os.path.join(folder, f"emblem_{kind}.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write(story_art.emblem_svg(kind))
        emblems[kind] = p
    out = []
    for si, (sec, (start, end)) in enumerate(zip(script["sections"], timing)):
        if sec.get("scene") != "story":
            out.append(None)
            continue
        row = plan_["sections"][si]
        bd = os.path.join(folder, f"bd_{si + 1}_{row['sky']}_{row['ground']}_{w}x{h}.svg")
        with open(bd, "w", encoding="utf-8") as f:
            f.write(story_art.backdrop_svg(row["sky"], row["ground"], w, h, seed=si + 3))
        ws = words[si] if words and si < len(words) else []
        times = beat_times(sec.get("narration"), ws, end - start, row["beats"])
        beats = [{"from": a, "to": b, "character": paths.get(bt["character"]) if bt["character"] else None, "name": bt["name"], "role": bt["role"],
                  "emblem": emblems.get(bt.get("emblem")), "big": bt["big"], "label": bt["label"]} for bt, (a, b) in zip(row["beats"], times)]
        out.append({"kind": "story", "backdrop": bd, "beats": beats, "characters": sorted({bt["character"] for bt in row["beats"] if bt["character"]})})
    return out
