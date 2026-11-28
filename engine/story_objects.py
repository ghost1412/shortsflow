"""Objects and animals a story needs that the kit has no drawing for (a wooden horse, a ship, a golden apple): the text model draws each one, and ShortsFlow checks
its own work before using it.

1. Draw: the same one-object request and the same checks as the icons of the picture scenes (`engine/art_icons.py`: flat shapes only, nothing else survives).
2. Check, blind, in two steps: the drawings are put on a numbered picture (the `DrawingSheet` still of the video renderer) and an image-reading model says what
   each one depicts without being told what it should be; the text model then decides whether that is the wanted thing. (A first version let the image model pick
   from a list of names: poor drawings passed by being the nearest name on it.) Asking "is this a horse?" would only get a yes; a drawing passes when the model finds the
   right name by itself.
3. A drawing that is not recognised is drawn once more; if it fails again it is left out and the story keeps its face on screen.
4. Only a drawing that passed is saved (`~/.shortsflow/story_objects`) and reused by later videos. With no image-reading model, a drawing is used in this video,
   marked unchecked, and not saved.

Only the names of the things and the fixed style examples go to the text model, and only the drawings and the names to the image model (Gemini sends them to
Google; the local one keeps them on this PC).
"""
import base64
import json
import os
import re
import subprocess
import time
import uuid

from engine import art_icons

ROUNDS = 2
BUSY_TRIES = 3                # a model that does not answer is asked again, after a wait: free tiers are often busy for a minute
BUSY_WAIT = 35                # two waits outlast the minute a rate-limited Gemini model is left alone (25 s ones gave up just before it came back)
TONES = ("threatening", "gentle", "neutral")


def rows_of(data, key):
    """The list under `key` in a model's JSON answer, however it was wrapped: {key: [...]}, a bare list of rows, or that object inside a list ([{key: [...]}], which
    once made every verdict of a check disappear). None when there is no such list."""
    if isinstance(data, list):
        inner = [row for r in data if isinstance(r, dict) and isinstance(r.get(key), list) for row in r[key]]
        data = inner or data
        return [r for r in data if isinstance(r, dict)] or None
    if isinstance(data, dict):
        if isinstance(data.get(key), list):
            return [r for r in data[key] if isinstance(r, dict)]
        if "id" in data:                                   # one row on its own
            return [data]
    return None


LOCAL_WAIT = 2               # the model on this PC that gave an unusable answer is not busy or rate-limited: asking again at once costs nothing


def patiently(call, label, local=None):
    """call() until it gives something usable: a model that raises or answers nothing is asked again after a wait. None when it never does.
    `local()` says whether the model that just answered runs on this PC: its unusable answer (not an error) is asked again after LOCAL_WAIT seconds, not BUSY_WAIT."""
    for attempt in range(BUSY_TRIES):
        wait = BUSY_WAIT
        try:
            got = call()
            if got is not None:
                return got
            why = "no usable answer"
            if local and local():
                wait = min(BUSY_WAIT, LOCAL_WAIT)
        except Exception as e:
            why = " ".join(str(e).split())[:90]
        if attempt + 1 < BUSY_TRIES:
            print(f"[Log] The {label} did not answer ({why}); trying again in {wait} s.")
            time.sleep(wait)
    print(f"[Warning] The {label} gave nothing usable after {BUSY_TRIES} tries ({why}).")
    return None


def library_dir():
    return os.getenv("SHORTSFLOW_STORY_OBJECTS") or os.path.join(os.path.expanduser("~"), ".shortsflow", "story_objects")


def slug(name):
    return art_icons.slug(name)


def svg_doc(markup):
    """The model's shapes (a 200 x 200 box centred on 0) as a whole SVG document."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-110 -110 220 220" width="600" height="600">{markup}</svg>'


def load(name, directory=None):
    path = os.path.join(directory or library_dir(), f"{slug(name)}.svg")
    return path if os.path.isfile(path) else None


def _write(folder, name, text):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{slug(name)}.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def render_sheet(documents, out, run=None, remotion_dir=None):
    """One JPEG with the drawings numbered 1, 2, 3 ... Returns `out`, or None when the renderer cannot make it."""
    from engine.paths import project_root
    remotion_dir = remotion_dir or os.path.join(project_root(), "remotion-video")
    props_name = f"temp_props_sheet_{uuid.uuid4().hex[:8]}.json"
    props_path = os.path.join(remotion_dir, props_name)
    items = ["data:image/svg+xml;base64," + base64.b64encode(d.encode("utf-8")).decode() for d in documents]
    cmd = ["npx", "remotion", "still", "DrawingSheet", os.path.abspath(out), f"--props={props_name}", "--image-format=jpeg", "--log=error"]
    try:
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f)
        done = (run or subprocess.run)(" ".join(f'"{c}"' if " " in c else c for c in cmd) if os.name == "nt" else cmd, shell=os.name == "nt",
                                       cwd=remotion_dir, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[Warning] The drawings could not be put on a picture to check them ({str(e)[:80]}).")
        return None
    finally:
        try:
            os.remove(props_path)
        except OSError:
            pass
    if getattr(done, "returncode", 1) != 0 or not os.path.isfile(out):
        print(f"[Warning] The drawings could not be put on a picture to check them ({' '.join(str(getattr(done, 'stderr', '')).split())[:120]}).")
        return None
    return out


PER_SHEET = 3                 # drawings on one picture: the image model's answer is kept short enough to arrive whole


def look_question(count, feeling=False):
    return (("For each drawing also say, at the end of its description, how it feels to a viewer: (feels friendly), (feels neutral) or (feels threatening).\n" if feeling else "") +f"The picture shows {count} numbered flat cartoon drawing(s). Ignore the drawing style and the colours. For each number, say what object or creature it "
            "depicts, in at most 12 words, naming the features that tell its kind or period (for a ship: sails or oars, or funnels, portholes, a motor). Say what it "
            "looks like to you, even if it is unclear.\nAnswer on one line in exactly this form and nothing else: 1=description; 2=description")


def read_answer(text, count):
    """{number: description} from the image model's line "1=...; 2=..."; None when it holds none."""
    parts = re.split(r"(?:^|[;\n|])\s*(\d+)\s*[=:]\s*", str(text or "").strip())
    found = {}
    for i in range(1, len(parts) - 1, 2):
        n = int(parts[i])
        said = parts[i + 1].strip(" .;\"'*")
        if 1 <= n <= count and said:
            found.setdefault(n, said[:160])
    if not found and count == 1 and str(text or "").strip():
        found[1] = " ".join(str(text).split())[:160]              # a single drawing is often described without its number
    return found or None


def describe_all(documents, folder, vision, render=None, feeling=False):
    """What the image model sees in each drawing, told nothing about what it should be: a list of descriptions in order, None when nothing can look at them."""
    model, ask_image = vision[0], vision[1]
    if not documents or not ask_image:
        return None
    os.makedirs(folder, exist_ok=True)
    out = []
    for i in range(0, len(documents), PER_SHEET):
        batch = documents[i:i + PER_SHEET]
        sheet = (render or render_sheet)(batch, os.path.join(folder, f"look_{uuid.uuid4().hex[:6]}.jpg"))
        if not sheet:
            return None
        with open(sheet, "rb") as f:
            picture = f.read()
        answers = patiently(lambda: read_answer(ask_image([picture], model, prompt=look_question(len(batch), feeling)), len(batch)), "image model")
        if answers is None:
            return None
        out += [answers.get(n, "nothing recognisable") for n in range(1, len(batch) + 1)]
    return out


def same_question(pairs):
    lines = "\n".join(f"{i}. Wanted: {wanted}. Someone who was not told sees: {seen}" for i, (wanted, seen) in enumerate(pairs, 1))
    return ("Each drawing below was made to show one thing, and someone who was not told what it should be described it. For each, is what they saw that thing "
            "(the same kind of object or creature, in plain words or a close synonym)? A different thing is a no, even a similar-looking one (a stethoscope is not "
            "a thread, an owl is not a wolf, a butterfly is not a pair of wings).\n\n" + lines +
            "\n\nReply with raw JSON only: {\"verdicts\": [{\"id\": 1, \"same\": true}]}")


def check(drawings, folder, vision, ask, render=None):
    """{name: True or False} for [(name, svg document)]: described blind by the image model, then compared with the wanted name by the text model. None when it
    cannot be checked."""
    seen = describe_all([d for _, d in drawings], folder, vision, render)
    if seen is None or not ask:
        return None
    def compare():
        from engine.script_gen import robust_json_parse
        return rows_of(robust_json_parse(ask(same_question([(n, s) for (n, _), s in zip(drawings, seen)]))), "verdicts") or None
    rows = patiently(compare, "text model (comparing)")
    verdicts = {}
    for r in rows if isinstance(rows, list) else []:
        try:
            verdicts[int(r["id"])] = r.get("same") is True
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    if not verdicts:
        return None
    return {name: verdicts.get(i, False) for i, (name, _) in enumerate(drawings, 1)}


def figure_request(name, tone):
    """The request for a being of the story: a character that fills the frame, not a friendly icon."""
    mood = {"threatening": "It must look dangerous and frightening, never cute or smiling: narrowed or glaring eyes, bared fangs, claws or horns as fits, dark and muted colours.",
            "gentle": "It should look calm and kind.", "neutral": ""}[tone if tone in TONES else "neutral"]
    return (art_icons.request(name) + "\n\nThis one is a CHARACTER in a story, not an icon: show the whole being or its head and shoulders, large and facing the viewer, "
            "in colours that suit it (not the bright icon colours). " + mood)


def _draw(name, ask, again=False, setting="", feedback="", tone=""):
    prompt = figure_request(name, tone) if tone else art_icons.request(name)
    if setting:
        prompt += f"\n\nThe story: {setting}. Draw it as it would look in that time and world (nothing modern in an old story)."
    if feedback:
        prompt += f"\nAn earlier picture was rejected because: {feedback}. Avoid that."
    if again:
        prompt += f"\n\nYour last drawing could not be recognised as {name}. Draw it again with its most typical shape, seen from the side, so that nobody could mistake it."
    for _ in range(art_icons.TRIES):
        markup = art_icons.clean(ask(prompt))
        if markup:
            return markup
    return None


def make(names, ask, folder, vision=None, render=None, directory=None, setting="", feedback="", fresh=False, tone=""):
    """{name: {"path": svg file or None, "status": "saved before" | "checked" | "unchecked" | "not recognised" | "not drawn"}} for every name asked for."""
    if vision is None:
        from engine.visual_context import choose_backend
        vision = choose_backend()
    results, todo = {}, []
    if tone:                                       # beings are kept apart from objects: an icon saved earlier must not return as a character
        directory = os.path.join(directory or library_dir(), "figures_" + (tone if tone in TONES else "neutral"))
    for name in dict.fromkeys(names):
        saved = None if fresh else load(name, directory)             # a rejected picture must not come back from the library
        if saved:
            results[name] = {"path": saved, "status": "saved before"}
        else:
            todo.append(name)
    for round_ in range(ROUNDS):
        drawn = []
        for name in todo:
            markup = patiently(lambda: _draw(name, ask, again=round_ > 0, setting=setting, feedback=feedback, tone=tone), f"text model (drawing '{name}')",
                              local=lambda: getattr(ask, "last_source", None) == "local") if ask else None
            if markup:
                drawn.append((name, svg_doc(markup)))
            else:
                results[name] = {"path": None, "status": "not drawn"}
        verdicts = check(drawn, folder, vision, ask, render) if drawn else {}
        todo = []
        for name, document in drawn:
            if verdicts is None:                       # nothing can look at it: used here, flagged, never saved
                results[name] = {"path": _write(folder, name, document), "status": "unchecked"}
            elif verdicts.get(name):
                _write(directory or library_dir(), name, document)
                results[name] = {"path": _write(folder, name, document), "status": "checked"}
            else:
                _write(folder, f"rejected_{round_ + 1}_{name}", document)          # kept in the run for a person to see, never used
                results[name] = {"path": None, "status": "not recognised"}
                todo.append(name)
        if not todo:
            break
    for name, got in results.items():
        print(f"[Log] Story drawing '{name}': {got['status']}.")
    return results
