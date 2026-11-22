"""Explaining pictures for the case explainer: the `illustration` scene.

A cartoon behind the scenes only sets the mood. Here the picture IS the explanation: every on-screen label of a section becomes one icon of a small
scene (an attacker, a server with a warning on it, a worried person...), and the video shows the picture with a numbered badge on each icon and the
numbered labels beside it, lit as the narrator reaches them. The words are drawn by the renderer, never inside the picture, so they are always right.

The text model does not draw shapes (free-form SVG came out as abstract boxes). It picks, per label, an icon of the tested kit in `engine/art_kit.py`
plus a colour, a mood or a status mark, the setting, and which things are linked by arrows; the kit draws it in one consistent flat style and knows exactly
where each icon is, so the badges always sit on the right things. The picture is made for the video's shape (wide, or square for the tall and square
formats), cached by section text, and a section whose picture cannot be made keeps a plain checklist.

Drawn only for now (`cartoon=` must allow `drawn`); picture models (local, cloud) could fill the same slot with fixed badge anchors later.
"""
import hashlib
import json
import os
import re

from engine import art_kit as kit

MAX_LABELS = 4            # icons that stay large and clear of each other and of the caption bar
MIN_LABELS = 2
MAX_LINKS = 4
ALIASES = {"attacker": "hacker", "intruder": "hacker", "criminal": "hacker", "user": "person", "developer": "person", "engineer": "person", "people": "group",
           "team": "group", "users": "group", "computer": "laptop", "pc": "laptop", "machine": "laptop", "mobile": "phone", "app": "phone", "rack": "server",
           "servers": "server", "datacenter": "server", "data": "database", "storage": "database", "internet": "globe", "web": "globe", "world": "globe",
           "padlock": "lock", "locked": "lock", "password": "key", "malware": "bug", "virus": "bug", "flaw": "bug", "vulnerability": "bug", "report": "document",
           "file": "document", "files": "folder", "email": "mail", "message": "mail", "company": "building", "office": "building", "home": "house",
           "process": "gear", "system": "gear", "settings": "gear", "growth": "chart_up", "decline": "chart_down", "loss": "chart_down", "cost": "money",
           "payment": "money", "time": "clock", "delay": "clock", "alert": "warning", "danger": "warning", "success": "check", "denied": "cross", "blocked": "cross",
           "search": "magnifier", "investigation": "magnifier", "flame": "fire", "network": "network", "signal": "wifi", "crash": "burst", "explosion": "burst",
           "outage": "burst", "idea": "bulb", "lesson": "bulb", "goal": "target", "ai": "robot", "bot": "robot", "protection": "shield", "defence": "shield",
           "defense": "shield", "fix": "shield", "open": "unlock", "cluster": "network", "mesh": "network",
           "blackhole": "black_hole", "black": "black_hole", "singularity": "black_hole", "antenna": "dish", "radio": "dish", "satellite": "dish",
           "particle": "atom", "electron": "atom", "quantum": "atom", "photon": "atom", "signal_wave": "wave", "frequency": "wave", "light": "wave",
           "universe": "galaxy", "space": "galaxy", "world": "planet", "earth": "planet", "sky": "telescope", "observatory": "telescope", "lab": "flask",
           "experiment": "flask", "chemistry": "flask", "lens": "camera", "image": "camera", "photo": "camera", "vision": "eye", "watch": "eye", "launch": "rocket"}


def art_aspect(aspect):
    """The shape of the picture for a video shape: wide (2:1, to use the width of a wide frame) for 16:9, square for the others (they leave room for the labels below)."""
    return "16:9" if aspect == "16:9" else "1:1"


def request(section, topic, labels):
    items = "\n".join(f"{i + 1}. {label}" for i, label in enumerate(labels))
    kinds = "\n".join(f"  {k}: {v}" for k, v in kit.HELP.items())
    narration = " ".join(str(section.get("narration", "")).split())[:900]
    return (
        f"You are the art director of an explainer video about: {topic}\n"
        f"Plan ONE cartoon picture that EXPLAINS this part of it: \"{section.get('title', '')}\".\n"
        f"What the narrator says over it: {narration}\n\n"
        f"The picture shows these {len(labels)} things, one icon each, so a viewer understands the idea at a glance:\n{items}\n\n"
        f"Choose the icon for each, by what the thing IS in this story (not by its words):\n{kinds}\n"
        "If NONE of these fits a thing, write a short plain name for it instead (one to three words, like \"vaccine\" or \"stone pyramid\") as its kind and it will be drawn "
        "for you; do that rather than pick an icon that means something else.\n\n"
        "Make the picture tell the story: use a person's mood (angry, worried, happy) or a status mark (warning, check, cross, fire, lock, burst) on an icon to show what "
        "happened to it; use different icons for different things; set many=true when a thing is a large number of something (hundreds of servers, many users). "
        "Link things with arrows when one causes, sends or leads to another (list the pairs in the order the story goes).\n"
        f"Colours: {', '.join(kit.COLORS)}. Settings: {', '.join(kit.SETTINGS)} (night suits attacks and secrets, cloud suits online services, city suits companies "
        f"and the public, office suits work). Layouts: row (a story from left to right), hub (the first thing in the middle), triangle (exactly 3).\n\n"
        "Answer with one JSON object and nothing else, with exactly one item per thing, in the order above:\n"
        '{"setting": "night", "layout": "row", "items": [{"kind": "hacker", "color": "red"}, {"kind": "server", "color": "blue", "mark": "warning"}, '
        '{"kind": "database", "color": "teal", "mark": "cross", "many": false}], "links": [[1, 2], [2, 3]]}\n'
        '(a person also takes "mood": "worried"; "mark" and "many" are optional.)'
    )


def _json_in(reply):
    text = str(reply or "").strip()
    try:
        data = json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except ValueError:
            return None
    if isinstance(data, dict) and "items" not in data:                  # the provider may wrap the answer: {"picture": {...}}
        for v in data.values():
            if isinstance(v, dict) and "items" in v:
                return v
    return data if isinstance(data, dict) else None


def check_spec(reply, count):
    """(spec, problem): the checked scene spec from a model's reply (`count` items, valid kinds, colours, links), or (None, what is wrong)."""
    data = _json_in(reply)
    if not data or not isinstance(data.get("items"), list):
        return None, "it was not a JSON object with an \"items\" list"
    raw_items = data["items"]
    if len(raw_items) < count:
        return None, f"it had {len(raw_items)} items and {count} were needed"
    items = []
    for i, raw in enumerate(raw_items[:count]):
        raw = raw if isinstance(raw, dict) else {"kind": raw}
        kind = str(raw.get("kind", "")).strip().lower().replace(" ", "_").replace("-", "_")
        kind = kind if kind in kit.ICONS else ALIASES.get(kind, kind)
        custom = kind not in kit.ICONS
        if custom and not re.fullmatch(r"[a-z][a-z0-9_]{1,28}", kind):
            return None, f"item {i + 1} named the thing '{raw.get('kind')}': give a short plain name of one to three words"
        color = str(raw.get("color", "")).strip().lower()
        item = {"kind": kind, "color": color if color in kit.COLORS else kit.CYCLE[i % len(kit.CYCLE)]}
        if custom:
            item["custom"] = True                  # not in the kit: it is drawn by the model and saved (engine/art_icons.py)
        mood = str(raw.get("mood", "")).strip().lower()
        if mood in kit.MOODS:
            item["mood"] = mood
        mark = str(raw.get("mark", "") or "").strip().lower()
        if mark in kit.MARKS:
            item["mark"] = mark
        if raw.get("many") is True:
            item["many"] = True
        items.append(item)
    links = []
    for raw in (data.get("links") or [])[:MAX_LINKS]:
        try:
            a, b = (int(raw["from"]), int(raw["to"])) if isinstance(raw, dict) else (int(raw[0]), int(raw[1]))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if 1 <= a <= count and 1 <= b <= count and a != b:
            links.append({"from": a, "to": b, "dashed": bool(isinstance(raw, dict) and raw.get("dashed"))})
    setting, layout = str(data.get("setting", "")).lower(), str(data.get("layout", "")).lower()
    return {"setting": setting if setting in kit.SETTINGS else "office",
            "layout": layout if layout in kit.LAYOUTS and not (layout == "triangle" and count != 3) else "row",
            "items": items, "links": links}, ""


FALLBACK = "star"        # the icon used for a thing the model cannot draw


def resolve_custom(spec, ask, directory=None):
    """The spec with every icon the kit lacks drawn (or loaded from the library of drawn icons); one that cannot be drawn becomes FALLBACK."""
    from engine import art_icons
    for item in spec["items"]:
        if item.pop("custom", False) and not art_icons.get(item["kind"], ask, directory):
            print(f"[Warning] No icon could be drawn for '{item['kind'].replace('_', ' ')}'; using a {FALLBACK}.")
            item["kind"] = FALLBACK
    return spec


def usable_labels(section):
    labels = [str(x).strip() for x in section.get("on_screen") or [] if str(x).strip()]
    return labels[:MAX_LABELS]


def _key(section, labels, aspect):
    raw = "|".join([str(section.get("title", "")), str(section.get("narration", "")), *labels, art_aspect(aspect), "kit-v4"])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def make(section, topic, aspect, ask, cache_dir):
    """{"path": background svg, "points": {label: (x, y)}, "items": {label: svg}, "centres": {label: (x, y)}, "links": [{"path", "from": label, "to": label}]}
    for a section, None when the labels are too few or two tries fail the checks. The files are layers (the background, one picture per
    icon, one per arrow) so the video can bring each in when the narrator reaches it."""
    labels = usable_labels(section)
    if len(labels) < MIN_LABELS:
        return None
    key = _key(section, labels, aspect)
    meta_path = os.path.join(cache_dir, f"art_{key}.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            if all(os.path.isfile(p) for p in [meta["path"], *meta["items"].values(), *(l["path"] for l in meta["links"])]):
                return {"path": meta["path"], "points": {k: tuple(v) for k, v in meta["points"].items()}, "items": meta["items"],
                        "centres": {k: tuple(v) for k, v in meta["centres"].items()}, "links": meta["links"]}
        except (OSError, ValueError, KeyError):
            pass
    prompt, problem = request(section, topic, labels), ""
    for _ in range(2):
        try:
            reply = ask(prompt + (f"\n\nYour last answer could not be used: {problem}. Answer again, following the format exactly." if problem else ""))
        except Exception as e:
            print(f"[Warning] The text model could not plan the picture for '{section.get('title', '')}' ({' '.join(str(e).split())[:100]}).")
            return None
        spec, problem = check_spec(reply, len(labels))
        if not spec:
            continue
        layered = kit.compose_layers(resolve_custom(spec, ask), art_aspect(aspect))
        os.makedirs(cache_dir, exist_ok=True)

        def write(name, svg):
            path = os.path.join(cache_dir, f"art_{key}_{name}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            return path
        meta = {"path": write("bg", layered["background"]),
                "points": {l: list(p) for l, p in zip(labels, layered["badges"])},
                "items": {l: write(f"i{i}", svg) for i, (l, svg) in enumerate(zip(labels, layered["items"]))},
                "centres": {l: list(c) for l, c in zip(labels, layered["centres"])},
                "links": [{"path": write(f"l{i}", l["svg"]), "from": labels[l["from"] - 1], "to": labels[l["to"] - 1]} for i, l in enumerate(layered["links"])]}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        return {"path": meta["path"], "points": {k: tuple(v) for k, v in meta["points"].items()}, "items": meta["items"],
                "centres": {k: tuple(v) for k, v in meta["centres"].items()}, "links": meta["links"]}
    return None


def attach(script, session_dir, aspect, source, ask, cache_dir=None):
    """[None | {"path", "points"}] per section: a picture for each `illustration` section (None for the others, and for all of them when
    `source` is off or leaves out `drawn`, the only way pictures that explain are made so far)."""
    from engine import case_cartoon as cc
    cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".shortsflow", "cartoons")
    ways = cc.order(source, False, False)
    out = []
    for sec in script["sections"]:
        if sec.get("scene") != "illustration" or "drawn" not in ways or ask is None:
            out.append(None)
            continue
        got = make(sec, script.get("title", ""), aspect, ask, cache_dir)
        out.append(got)
        if not got:
            print(f"[Warning] No picture for '{sec.get('title', '')}'; it shows its labels as a checklist instead.")
    return out
