"""The story look of the case explainer (`--case template=story`): who is on screen when, drawn by code.

One model call plans the whole script: the people in it (a spec each, see `engine/story_art.py`), and for every section the sky and ground of its backdrop and a list
of beats. A beat starts at a sentence and says who that sentence is about (a character bust rises in with a gold name plate), or shows a title card (no character),
or a big figure with its label. Everything the model says is checked: only known parts and colours, only characters it described, a figure only when the
narration says it. A person is saved in the library (`~/.shortsflow/characters`), so the same person looks the same in the next video.
The plan is saved with the run (`story_plan.json`) so a resumed run does not ask again.
"""
import copy
import hashlib
import json
import os
import re
import unicodedata

from engine import story_art, story_objects

MAX_CHARACTERS = 6
MAX_NAME = 40
MAX_ROLE = 42


def library_dir():
    return os.getenv("SHORTSFLOW_CHARACTERS") or os.path.join(os.path.expanduser("~"), ".shortsflow", "characters")


def _slug(name):
    """A file name for a person: the letters and digits of ANY alphabet (a Hindi vowel sign counts), so two names never share one file.
    (Only a-z used to be kept: every Hindi name became "" and one person's face was drawn for another.)"""
    kept = "".join(c if unicodedata.category(c)[0] in "LMN" else "_" for c in str(name).lower())
    slug = re.sub(r"_+", "_", kept).strip("_")[:40].strip("_")
    return slug or "person_" + hashlib.sha1(str(name).encode("utf-8")).hexdigest()[:10]


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
    from engine.case_study import split_sentences
    return split_sentences(text)


# a saved "name" that is only a role or a family word belongs to the story it was made for: the next story's grandmother or king is somebody else
ROLE_WORDS = frozenset("grandmother grandfather mother father mom dad sister brother son daughter wife husband girl boy child baby man woman king queen prince princess "
                       "lord lady master maiden knight soldier guard warrior hunter woodcutter shepherd giant monster demon witch wizard hero villain stranger narrator "
                       "wolf fox hare tortoise dragon snake lion bear".split())


def clearly_named(name, text):
    """Does the narration name THIS saved person? Only a proper name counts, written as saved. A title that starts with an article ("The Prince") or a bare
    role ("Grandmother") belongs to the story it was made for: "the prince of Ayodhya" is somebody else. One word the story also writes in lower case is
    an ordinary word."""
    if re.match(r"(?i)(the|a|an)\s", name) or not name[:1].isupper() or name.lower() in ROLE_WORDS:
        return False
    if len(name.split()) == 1 and re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", text):
        return False
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text) is not None


# words in a person's NAME that settle how they are drawn ("Old Woman" is not a bearded man, whatever the plan says)
WOMAN_NAMES = frozenset("woman lady mother stepmother grandmother godmother mom queen princess empress goddess witch sister wife daughter maiden aunt widow bride girl mrs miss".split())
CHILD_NAMES = frozenset("girl boy child baby".split())
GROUP_CHILDREN = r"(?:children|kids|little ones)"


def facts_from(name, text):
    """What a person's name and the narration say outright about how they look: {"figure": "child" | "woman", "age": ..., "girl": bool}.
    Only plain statements count ("Hansel and Gretel are the young children of ...", "a little girl called Mira", "his sister Ana")."""
    words = set(re.findall(r"[a-z]+", name.lower()))
    facts = {}
    if words & CHILD_NAMES:
        facts.update(figure="child", age="young", girl="girl" in words)
    elif words & WOMAN_NAMES:
        facts.update(figure="woman")
    if words & {"old", "elderly", "grandmother", "grandfather"}:
        facts["age"] = "old"
    n = rf"(?<!\w){re.escape(name)}(?!\w)"
    other = r"[A-Z][\w'-]+"
    small = r"(?:(?:two|the|a|an|young|little|small|poor|twin)\s+)*"
    child = (rf"{n}(?:\s+and\s+{other})?\s+(?:is|are|was|were)\s+{small}(?:{GROUP_CHILDREN}|child|boy|girl)\b",
             rf"\b{other}\s+and\s+{n}\s+(?:are|were)\s+{small}{GROUP_CHILDREN}\b",
             rf"\b(?:little|young|small)\s+(?:boy|girl|child)\s*(?:,|named|called)\s*{n}",
             rf"{n},\s+(?:a|the)\s+(?:little|young|small)\s+(?:boy|girl|child)\b",
             rf"\b{GROUP_CHILDREN},\s+(?:{other}\s+and\s+{n}|{n}\s+and\s+{other})")
    if any(re.search(p, text) for p in child):
        facts.update(figure="child", age="young")
    if re.search(rf"\b(?:girl|sister|daughter)\s*(?:,|named|called)?\s*{n}|{n},\s+(?:(?:a|the|his|her)\s+)?(?:(?:little|young|small)\s+)?(?:girl|sister)\b", text):
        facts["girl"] = True
        if facts.get("figure") != "child":
            facts["figure"] = "woman"
    return facts


def apply_facts(spec, facts):
    """`spec` changed to agree with `facts`."""
    if spec.get("species", "human") != "human" or not facts:
        return spec
    out = dict(spec)
    if facts.get("figure"):
        out["figure"] = facts["figure"]
        if out["figure"] != "man":
            out["facial_hair"] = "none"
        if out["hair"] == "short" and (out["figure"] == "woman" or facts.get("girl")):
            out["hair"] = "long"
    if facts.get("age"):
        out["age"] = facts["age"]
        if out["age"] == "old":
            out["hair_colour"] = "white"
    return out


LOOK_KEYS = ("species", "figure", "age", "skin", "hair", "hair_colour", "headgear", "facial_hair", "outfit", "outfit_colour", "coat_colour")
SPARE_COLOURS = ("blue", "green", "saffron", "teal", "purple", "brown", "red", "maroon")


SNAKY = re.compile(r"\b(snakes?|serpents?|medusa|gorgons?)\b", re.I)


def no_stray_snakes(name, spec, narration):
    """Snakes for hair only when the story speaks of them (a small model gave them to a witch)."""
    if spec.get("hair") == "snakes" and not SNAKY.search(f"{name} {narration}"):
        return dict(spec, hair="long")
    return spec


def tell_apart(chars, fixed=()):
    """Two people drawn exactly alike look like one person twice: give the later one another outfit colour (and hair, for a person).
    `fixed` names (saved looks) are never changed."""
    seen, out = [], {}
    for name, spec in chars.items():
        spec = dict(spec)
        if name not in fixed:
            for colour in SPARE_COLOURS:
                if not any(all(spec.get(k) == s.get(k) for k in LOOK_KEYS) for s in seen):
                    break
                spec["outfit_colour"] = colour
                if spec.get("species", "human") == "human" and spec.get("age") != "old":
                    spec["hair_colour"] = "brown" if spec.get("hair_colour") == "black" else "black"
        seen.append(spec)
        out[name] = spec
    return out


def named_here(known, script):
    """The saved people this story names. Only they are mentioned to the model and carried over: given the whole library, it took it for the cast and drew
    none of the story's own people."""
    text = ". ".join([str(script.get("title", "")), *[str(s.get("narration", "")) for s in script["sections"]]])
    return {name: spec for name, spec in (known or {}).items() if clearly_named(name, text)}


def request(script, known):
    """The prompt that plans the story's pictures."""
    lines = []
    for si, sec in enumerate(script["sections"], 1):
        lines.append(f"Section {si} (id \"{sec['id'] if 'id' in sec else si}\", {sec.get('title', '')}):")
        for k, s in enumerate(sentences(sec.get("narration")), 1):
            lines.append(f"  {k}. {s}")
    known = named_here(known if isinstance(known, dict) else {k: None for k in known or []}, script)
    known_line = ("People of this story who are already drawn (use these exact names for them, do not redescribe them): " + ", ".join(sorted(known)) + ". ") if known else ""
    return (
        "You are the art director of a short animated story video. Plan its pictures from this narration.\n\n" + "\n".join(lines) + "\n\n"
        + known_line +
        "Describe each person, god, ANIMAL or creature who acts in the narration, at most " + str(MAX_CHARACTERS) + ", as a bust. Use the look the story's tradition gives them. "
        "species: human for a person or god; for an animal (or a being with an animal's head, who may also wear clothes) the nearest of " + ", ".join(story_art.SPECIES[1:]) + ". Never draw an animal as a human. "
        f"An animal also takes coat_colour ({', '.join(story_art.story_beasts.COATS)}) and outfit \"none\" unless it wears clothes in the story. A monster takes what makes it one: "
        "hair \"snakes\", and among ornaments horns, fangs, glowing_eyes, spread_wings. "
        "For each, choose only from these values: "
        f"figure: {', '.join(story_art.FIGURES)}; hair: {', '.join(story_art.HAIR)}; hair_colour: {', '.join(story_art.HAIR_COLOURS)}; "
        f"marking, only when the person is known for one (stripe = a painted or tattooed band down over one eye, paint = lines on the cheeks, scar = a healed cut): {', '.join(story_art.MARKINGS)}; marking_colour: {', '.join(story_art.COLOURS)}; "
        f"skin: {', '.join(story_art.SKIN)}; headgear: {', '.join(story_art.HEADGEAR)}; headgear_colour, outfit_colour, trim_colour: {', '.join(story_art.COLOURS)}; "
        f"facial_hair: {', '.join(story_art.FACIAL_HAIR)}; outfit: {', '.join(story_art.OUTFITS)}; ornaments (a list): {', '.join(story_art.ORNAMENTS)}; "
        f"mood: {', '.join(story_art.MOODS)}; weapon: {', '.join(story_art.WEAPONS)}; age: {', '.join(story_art.AGES)}.\n"
        "Dress each person for their OWN time and job. Someone of the last two hundred years wears a suit, shirt, uniform, lab_coat, dress or spacesuit (with a hat, cap, "
        "military_cap or glasses only if they are known for it), never the armour, robe, crown or turban of an old tale, and carries no old weapon. An astronaut wears the "
        "spacesuit, with the space_helmet. People of an ancient or fairy tale wear none of the modern things.\n"
        "For EACH section choose the backdrop: sky: " + ", ".join(story_art.SKIES) + " (the mood of the moment: sunset or dusk for calm or sad, fire or storm for battle and "
        "danger, rays for a solemn card, night for secrets, dawn for hope; day only for a peaceful, bright scene, and vary the sky between sections) and ground (choose by where the story takes place: trees for woods, countryside and gardens; palms ONLY for deserts, oases and tropical shores; city for a town): " + ", ".join(story_art.GROUNDS) + ".\n"
        "Then list the beats of each section. A beat starts at a sentence number and says what is on screen from there until the next beat. It is ONE of two kinds. "
        "A CHARACTER beat: \"character\" is the person that sentence is about or who speaks in it, and their name is shown. A CARD beat: \"character\" is null, \"name\" is the "
        "card's title of at most 3 words, and \"emblem\" is the one object that shows it, from: " + ", ".join(story_art.EMBLEMS) + " (or empty when none fits). Use a card when the "
        "sentence is about a thing, a curse, a weapon or someone you did not describe. A character beat may set \"mood\" (from the same mood list) when the person feels differently at that moment than usual: nobody smiles while falling or dying. \"role\" is a short line under the name of at most 5 words (like \"The King's Son\"; empty is fine). "
        "A sentence that holds a number worth showing big may "
        "have \"big\" (the number exactly as the narration says it) and \"label\" (at most 4 words). Use a new beat when the person on screen should change, about every "
        "one or two sentences, and always a beat at sentence 1 of every section. Never invent facts: only what the narration says.\n"
        f"Also list for each section \"props\": up to {MAX_PROPS} things a viewer should SEE that a sentence mentions, such as an object, an animal, a vehicle or a building "
        "(never a person), each as {\"sentence\": its number, \"object\": one to three plain words, like \"wooden horse\" or \"golden apple\"}. Prefer the thing the "
        "moment turns on. Leave the list empty when the section names no such thing.\n\n"
        "Reply with raw JSON only:\n"
        "Also give \"setting\": the time and world of the story in at most 12 words (like \"an ancient Persian fantasy\").\n"
        "{\"setting\": \"...\", \"characters\": {\"Name\": {\"skin\": \"...\", \"headgear\": \"...\", ...}}, \"sections\": [{\"sky\": \"...\", \"ground\": \"...\", \"props\": [{\"sentence\": 2, \"object\": \"...\"}], \"beats\": "
        "[{\"sentence\": 1, \"character\": \"Name\" or null, \"name\": \"...\", \"role\": \"...\", \"emblem\": \"\", \"big\": \"\", \"label\": \"\"}]}]}")


def _parse(reply):
    from engine.script_gen import robust_json_parse
    try:
        data = robust_json_parse(reply)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _clip(text, n):
    """At most n characters, cut between words (a name cut inside one, "... Bor", was taken for a second person)."""
    text = " ".join(str(text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n + 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut else text[:n]).strip()


# words in a sentence that name an object the kit can draw: (pattern, emblem, the card's title)
OBJECT_WORDS = ((r"lightning|thunderbolt", "lightning", "The Thunderbolt"), (r"box|casket", "box", "The Box"), (r"wings", "wings", "The Wings"),
                (r"wheel", "wheel", "The Wheel"), (r"swords?|blades?", "sword", "The Blade"), (r"spears?", "spear", "The Spear"), (r"arrows?", "arrow", "The Arrow"),
                (r"crown|throne", "crown", "The Throne"), (r"flames?|fire", "fire", "The Flame"), (r"skulls?", "skull", "Death"), (r"mount|mountains?", "mountain", "The Mountain"),
                (r"the sun", "sun", "The Sun"))
MAX_ADDED_CARDS = 3


MAX_PROPS = 2                 # things a section may ask to show
MAX_DRAWINGS = 6              # new drawings one video may ask for


def kit_emblem(name):
    """(emblem, title) when the kit already draws this thing, else None."""
    return next(((e, title) for pattern, e, title in OBJECT_WORDS if re.fullmatch(rf"(?:(?:the|a|an)\s+)?(?:{pattern})", str(name).strip(), re.I)), None)


def check_props(raw, narration, characters):
    """The things the model wants shown, as [{"sentence", "object"}]: one to three plain words, never a person of the story, and the sentence has to mention it."""
    sents = sentences(narration)
    out = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        name = " ".join(str(row.get("object") or "").lower().split())
        name = re.sub(r"^(a|an|the)\s+", "", name)
        try:
            k = int(row.get("sentence"))
        except (TypeError, ValueError):
            continue
        if not (1 <= k <= len(sents) and re.fullmatch(r"[a-z][a-z' -]{1,29}", name) and len(name.split()) <= 3):
            continue
        if any(name == c.lower() or name in c.lower().split() for c in characters):
            continue
        said = sents[k - 1].lower()
        if not any(len(w) >= 3 and re.search(rf"\b{re.escape(w[:max(3, len(w) - 1)])}", said) for w in name.split()):
            continue                                       # only what the narration says
        if all(name != o["object"] for o in out):
            out.append({"sentence": k, "object": name})
    return out[:MAX_PROPS]


def free_slot(row, count, k):
    """(the beat before, the beat at k or None) when a card may take sentence k, else None: never the first sentence, and only where the same face carries on."""
    if not 2 <= k <= count:
        return None
    at = {b["sentence"]: b for b in row["beats"]}
    before = at[max(n for n in at if n < k)]
    here = at.get(k)
    if here and here["character"] != before["character"]:
        return None                                        # this sentence brings someone new on screen: leave it
    return before, here


def wanted_drawings(plan_, script):
    """The names of the things worth drawing: asked for by a section and not in the kit. Each can be shown, beside the speaker if no card fits."""
    names = [o["object"] for row in plan_["sections"] for o in row.get("props", []) if not kit_emblem(o["object"])]
    return list(dict.fromkeys(names))[:MAX_DRAWINGS]


MAX_ASIDES = 2                # things shown beside the speaker in one section
MAX_VIDEO_ASIDES = 7


def add_asides(plan_, script, drawn=()):
    """Shows a thing BESIDE what is on screen while its sentence is spoken, so the face stays: the section's own things first (from the kit, or among `drawn`), then
    anything a sentence names that the kit draws. Not over a card that already shows an object or a figure; each thing once in a video."""
    used = {b["emblem"] for s in plan_["sections"] for b in s["beats"] if b.get("emblem")}
    total = 0
    for sec, row in zip(script["sections"], plan_["sections"]):
        sents = sentences(sec.get("narration"))
        choices = []
        for o in row.get("props", []):
            kit = kit_emblem(o["object"])
            if kit:
                choices.append((o["sentence"], kit[0]))
            elif o["object"] in drawn:
                choices.append((o["sentence"], "custom:" + o["object"]))
        for k, text in enumerate(sents, 1):
            choices += [(k, e) for pattern, e, _ in OBJECT_WORDS if re.search(rf"\b(?:{pattern})\b", text, re.I)]
        taken = set()
        for k, emblem in choices:
            if len(taken) >= MAX_ASIDES or total >= MAX_VIDEO_ASIDES:
                break
            if emblem in used or k in taken or not 1 <= k <= len(sents):
                continue
            beat = [b for b in row["beats"] if b["sentence"] <= k][-1]
            if beat.get("emblem") or beat.get("big"):
                continue                                    # the screen is already showing a thing
            beat.setdefault("asides", []).append({"sentence": k, "emblem": emblem})
            used.add(emblem)
            taken.add(k)
            total += 1
    return plan_


def aside_times(asides, sentence_times, start, end):
    """[(at, until)] seconds inside a beat that runs from `start` to `end`: each thing appears when its sentence starts and stays for the sentence, at least 2.5 s
    where the beat allows, and leaves when the next thing comes."""
    out = []
    ordered = sorted(asides, key=lambda a: a["sentence"])
    for i, a in enumerate(ordered):
        s_from, s_to = sentence_times[min(a["sentence"], len(sentence_times)) - 1]
        at = max(0.0, s_from - start)
        until = max(s_to - start, at + 2.5)
        if i + 1 < len(ordered):
            until = min(until, max(at + 0.8, sentence_times[min(ordered[i + 1]["sentence"], len(sentence_times)) - 1][0] - start))
        out.append((a["emblem"], round(at, 2), round(min(until, end - start), 2)))
    return out


def add_object_cards(plan_, script, drawn=()):
    """Adds title cards the model did not plan (it often plans none), at most one in a section, each thing once and three in a video. The things a section asked to
    show come first (from the kit, or among `drawn`, the names that now have a drawing); then any sentence that names something the kit draws. Only where
    nothing is lost (see `free_slot`); the face comes back on the next sentence."""
    used = {b["emblem"] for s in plan_["sections"] for b in s["beats"] if b.get("emblem")}
    added = 0
    for sec, row in zip(script["sections"], plan_["sections"]):
        if added >= MAX_ADDED_CARDS or any(not b["character"] for b in row["beats"]):
            continue
        sents = sentences(sec.get("narration"))
        choices = []                                       # (sentence, emblem, title), best first
        for o in row.get("props", []):
            kit = kit_emblem(o["object"])
            if kit:
                choices.append((o["sentence"], kit[0], kit[1]))
            elif o["object"] in drawn:
                choices.append((o["sentence"], "custom:" + o["object"], o["object"].title()))
        for k, text in enumerate(sents, 1):
            choices += [(k, e, title) for pattern, e, title in OBJECT_WORDS if re.search(rf"\b(?:{pattern})\b", text, re.I)]
        for k, emblem, title in choices:
            slot = None if emblem in used else free_slot(row, len(sents), k)
            if not slot:
                continue
            before, here = slot
            at = {b["sentence"] for b in row["beats"]}
            card = {"sentence": k, "character": None, "name": title[:MAX_NAME], "role": "", "mood": "", "emblem": emblem, "big": "", "label": ""}
            row["beats"] = [b for b in row["beats"] if b["sentence"] != k] + [card]
            if k < len(sents) and k + 1 not in at:
                row["beats"].append(dict(here or before, sentence=k + 1))
            row["beats"].sort(key=lambda b: b["sentence"])
            used.add(emblem)
            added += 1
            break
    return plan_


def is_title(name, narration, cast=()):
    """Can a card with no picture and no number stand on this title alone? Two words or more, a name from the cast, or one word the narration
    writes as a name (with a capital in the middle of a sentence). A single ordinary word on an empty screen ("Moment", "Who", "Girl") shows nothing."""
    words = name.split()
    if len(words) != 1:
        return bool(words)
    word = words[0]
    if any(word.lower() == n.lower() for n in cast):
        return True
    capital = word[:1].upper() + word[1:]
    return re.search(r"[^.!?\s\"'\u201c(]\s+" + re.escape(capital) + r"\b", narration) is not None


def first_named(chars, narration):
    """The person a section opens on when the plan has none: the one its narration names first (a whole name, else a part of it), else the first of the cast."""
    low = narration.lower()
    found = []
    for name in chars:
        places = [m.start() for part in [name.lower(), *[w for w in name.lower().split() if len(w) > 3]]
                  for m in [re.search(r"\b" + re.escape(part) + r"\b", low)] if m]
        if places:
            found.append((min(places), name))
    return min(found)[1] if found else next(iter(chars or {}), None)


def check_plan(reply, script, library=None):
    """(plan, problem): the plan with only usable parts. {"characters": {name: spec}, "sections": [{"sky", "ground", "beats": [{"sentence", "character", "name", "role",
    "big", "label"}]}]}, one entry of sections per section of the script. A section the model left out gets a calm default, so a plan is never refused for that alone."""
    data = _parse(reply) if isinstance(reply, str) else reply
    if not isinstance(data, dict):
        return None, "the answer was not a JSON object"
    library = named_here(library or {}, script)      # a saved look is used only for a person this narration clearly names, also when the model names one itself
    chars = dict(list(library.items())[:MAX_CHARACTERS])                          # saved people of this story need no new description
    raw_chars = data.get("characters") if isinstance(data.get("characters"), dict) else {}
    for name, spec in raw_chars.items():
        name = _clip(name, MAX_NAME)
        if name and (name in chars or len(chars) < MAX_CHARACTERS):
            chars[name] = library.get(name) or story_art.clean_spec(spec)
    told = " ".join(str(s.get("narration") or "") for s in script["sections"])
    chars = {name: spec if name in library else no_stray_snakes(name, apply_facts(spec, facts_from(name, told)), told) for name, spec in chars.items()}
    chars = tell_apart(chars, fixed=library)
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
            mood = str(b.get("mood") or "").strip().lower()
            name = _clip(b.get("name") or who, MAX_NAME)
            if who and name.lower() != who.lower():
                if name and not any(w in who.lower().split() for w in re.findall(r"[a-z]+", name.lower())):
                    who = ""                      # a title about someone or something else ("Abhimanyu" over Krishna's face): it is a card, not this face
                else:
                    name = who                    # "Krishna's Counsel" over Krishna: the plate under a face is that person's own name
            beat = {"sentence": k, "character": who or None, "name": name, "role": _clip(b.get("role"), MAX_ROLE), "mood": mood if who and mood in story_art.MOODS else "",
                    "emblem": emblem if not who and not big and emblem in story_art.EMBLEMS else "",
                    "big": big, "label": _clip(b.get("label"), 30) if big else ""}
            heading = str(sec.get("title") or "").strip().lower()
            if not beat["character"] and not beat["big"] and not beat["emblem"] and heading and beat["name"].lower() == heading:
                continue                                       # a card that only repeats the section's heading shows nothing
            if beat["character"] or beat["big"] or beat["emblem"] or (beat["name"] and is_title(beat["name"], narration, chars)):
                beats.append(beat)
        beats.sort(key=lambda x: x["sentence"])
        if not beats or beats[0]["sentence"] != 1:
            first = first_named(chars, narration)
            beats.insert(0, {"sentence": 1, "character": first, "name": first or _clip(sec.get("title"), MAX_NAME), "role": "", "emblem": "", "big": "", "label": ""})
        sky = str(row.get("sky") or "").strip().lower()
        ground = str(row.get("ground") or "").strip().lower()
        out_sections.append({"sky": sky if sky in story_art.SKIES else "sunset", "ground": ground if ground in story_art.GROUNDS else "none", "beats": beats,
                             "props": check_props(row.get("props"), narration, chars)})
    if not chars and not any(b["name"] for s in out_sections for b in s["beats"]):
        return None, "no character or card was planned"
    return {"characters": chars, "sections": out_sections, "setting": _clip(data.get("setting"), 90)}, ""


def _key(script, aspect):
    raw = "|".join([str(script.get("title", "")), *[str(s.get("narration", "")) for s in script["sections"]], aspect, "story-v19"])
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
    for attempt in range(2):
        try:
            reply = ask(prompt + (f"\n\nYour last answer could not be used: {problem}. Answer again, following the format exactly." if problem else ""))
        except Exception as e:
            print(f"[Warning] The text model could not plan the story's pictures ({' '.join(str(e).split())[:100]}).")
            return None
        plan_, problem = check_plan(reply, script, library)
        if plan_ and attempt == 0 and not any(b["character"] for s in plan_["sections"] for b in s["beats"]):
            plan_, problem = None, ("no beat shows a person. Describe the people named in THIS narration under \"characters\", and set \"character\" to that exact name "
                                    "on the beats where they act or speak")
        if plan_:
            if getattr(ask, "last_source", None) == "local":          # a small model's looks are often wrong: do not hand them to later videos
                print("[Warning] The story's pictures were planned by the model on this PC, which often gets people wrong (age, man or woman, who is missing). "
                      "Check the video; these characters are not saved for later ones.")
            else:
                for name, spec in plan_["characters"].items():
                    if name not in library:
                        save_character(name, spec)
            os.makedirs(session_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"key": key, "plan": plan_}, f, indent=1)
            return plan_
        print(f"[Log] The story plan was not usable: {problem}.")
    return None


def reviewed(plan_, script, ask, session_dir, folder, drawn, vision=None, render=None):
    """(report, plan) after ShortsFlow's own review (engine/story_review.py). The reviewed plan and its drawings are kept with the run, so a resumed run, or its
    other shape, shows the same thing without reviewing again. A review that fails leaves the plan as it was and says so."""
    from engine import story_review
    key = hashlib.sha1((_key(script, "any") + json.dumps(plan_, sort_keys=True)).encode("utf-8")).hexdigest()[:12]
    path = os.path.join(session_dir, "story_review.json")
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("key") == key and all(os.path.isfile(p) for p in saved["drawn"].values()):
            drawn.update(saved["drawn"])
            return saved["report"], saved["plan"]
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    fixed = copy.deepcopy(plan_)
    try:
        report = story_review.run(fixed, script, ask, folder, drawn, vision=vision, render=render)
    except Exception as e:                                       # the review is a second look: it must never cost the video
        print(f"[Warning] The story review stopped ({' '.join(str(e).split())[:120]}); the plan is used as it was.")
        return {"checked": 0, "needed": [], "replaced": [], "removed": [], "added": [], "left": [], "notes": ["the review stopped with an error"]}, plan_
    for line in story_review.summary(report):
        print(f"[Log] Story review: {line[2:]}")
    os.makedirs(session_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"key": key, "report": report, "plan": fixed, "drawn": drawn}, f, indent=1)
    return report, fixed


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


def attach(script, session_dir, aspect, ask, words, timing, vision=None, render=None):
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
    # things the kit cannot draw: the model draws them, they are checked blind, and only what passes gets a card (engine/story_objects.py)
    wanted = wanted_drawings(plan_, script)
    setting = plan_.get("setting") or str(script.get("title", ""))
    objects = story_objects.make(wanted, ask, folder, vision=vision, render=render, setting=setting) if wanted else {}
    drawn = {name: got["path"] for name, got in objects.items() if got["path"]}
    add_object_cards(plan_, script, drawn)
    add_asides(plan_, script, drawn)
    review, plan_ = reviewed(plan_, script, ask, session_dir, folder, drawn, vision, render)
    paths = {}

    def bust(name, mood):
        """The drawing of a person in the mood of the moment (their own mood when the beat sets none), drawn once per mood. A creature has one drawing of its own."""
        if plan_["characters"][name].get("creature"):
            return plan_["characters"][name]["creature"]
        if (name, mood) not in paths:
            spec = dict(plan_["characters"][name], **({"mood": mood} if mood else {}))
            p = os.path.join(folder, f"char_{_slug(name)}{'_' + mood if mood else ''}.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write(story_art.character_svg(spec))
            paths[(name, mood)] = p
        return paths[(name, mood)]
    emblems = {}
    kinds = {b.get("emblem") for s in plan_["sections"] for b in s["beats"] if b.get("emblem")}
    kinds |= {a["emblem"] for s in plan_["sections"] for b in s["beats"] for a in b.get("asides", [])}
    for kind in sorted(kinds):
        p = os.path.join(folder, f"emblem_{kind}.svg")
        if kind.startswith("custom:"):
            emblems[kind] = drawn.get(kind[len("custom:"):])
            continue
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
        beats = [{"from": a, "to": b, "character": bust(bt["character"], bt.get("mood", "")) if bt["character"] else None, "name": bt["name"], "role": bt["role"],
                  "emblem": emblems.get(bt.get("emblem")), "big": bt["big"], "label": bt["label"]} for bt, (a, b) in zip(row["beats"], times)]
        narration = sec.get("narration")
        by_sentence = beat_times(narration, ws, end - start, [{"sentence": k} for k in range(1, len(sentences(narration)) + 1)])
        for shown_beat, bt, (a, b) in zip(beats, row["beats"], times):
            if bt.get("asides"):
                shown_beat["asides"] = [{"src": emblems[e], "at": x, "until": y} for e, x, y in aside_times(bt["asides"], by_sentence, a, b) if emblems.get(e) and y > x]
        shown = {bt["emblem"] for bt in row["beats"] if bt.get("emblem")} | {a["emblem"] for bt in row["beats"] for a in bt.get("asides", [])}
        report = [{"name": o["object"], "status": objects.get(o["object"], {}).get("status") or ("in the kit" if kit_emblem(o["object"]) else "not drawn"),
                   "shown": ("custom:" + o["object"]) in shown or bool(kit_emblem(o["object"]) and kit_emblem(o["object"])[0] in shown)} for o in row.get("props", [])]
        out.append({"kind": "story", "backdrop": bd, "beats": beats, "characters": sorted({bt["character"] for bt in row["beats"] if bt["character"]}),
                    "cards": [bt["name"] for bt in row["beats"] if not bt["character"]], "objects": report, "review": review})
    return out
