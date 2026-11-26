"""Objects and animals a story needs that the kit has no drawing for (a wooden horse, a ship, a golden apple): the text model draws each one, and ShortsFlow checks
its own work before using it.

1. Draw: the same one-object request and the same checks as the icons of the picture scenes (`engine/art_icons.py`: flat shapes only, nothing else survives).
2. Check, blind: the drawings are put on one numbered picture (the `DrawingSheet` still of the video renderer) and an image-reading model is asked which name, from
   a list that also holds wrong ones, each drawing shows, or "none". The wrong ones include things that look alike (the text model names them: a pear and a bottle
   for an apple), because with only unlike names a poor drawing passes by being the nearest thing on the list. Asking "is this a horse?" would only get a yes; a drawing passes when the model finds the
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
import uuid

from engine import art_icons

ROUNDS = 2
DECOYS = ("a chair", "a fish", "a bicycle", "an umbrella", "a teapot", "a guitar", "a cactus", "an anchor", "a ladder", "a mushroom", "a key", "a drum")


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


def question(count, names):
    return (f"The picture shows {count} numbered drawings. For each number, say which ONE of these names the drawing shows. Choose only from this list, and answer "
            f"none when you cannot tell what it is: {'; '.join(names)}.\nAnswer on one line in exactly this form and nothing else: 1=name; 2=none")


def read_answer(text, count):
    """{number: name or "none"} from the image model's line; None when it holds no answer at all."""
    found = {}
    for m in re.finditer(r"(\d+)\s*[=:\-]\s*([^;\n|]+)", str(text or "")):
        n = int(m.group(1))
        if 1 <= n <= count:
            found.setdefault(n, m.group(2).strip(" .\"'*,").lower())
    return found or None


def _plain(name):
    return re.sub(r"^(a|an|the)\s+", "", " ".join(str(name).lower().split()))


LOOK_ALIKES = 3               # look-alike wrong answers asked for per name


def look_alikes(names, ask):
    """Wrong answers that would catch a poor drawing: for each name, things its drawing could be mistaken for ("golden apple": pear, bottle, lemon). [] when the
    text model gives none; the check then still has its unlike decoys."""
    if not ask or not names:
        return []
    prompt = (f"A drawing is to be checked by asking someone which thing it shows. For EACH of these, name {LOOK_ALIKES} different things that a poor drawing of it "
              f"could easily be mistaken for (similar outline, not the same thing and not a kind of it): {'; '.join(names)}.\n"
              'Reply with raw JSON only: {"look_alikes": ["...", "..."]} (one flat list, plain names of one to three words).')
    try:
        from engine.script_gen import robust_json_parse
        data = robust_json_parse(ask(prompt))
    except Exception:
        return []
    found = data.get("look_alikes") if isinstance(data, dict) else None
    out = []
    for item in found if isinstance(found, list) else []:
        name = _plain(item) if isinstance(item, str) else ""
        wanted = [_plain(n) for n in names]
        if re.fullmatch(r"[a-z][a-z' -]{1,29}", name) and name not in out and not any(name == w or name in w.split() or w in name.split() for w in wanted):
            out.append(name)
    return out[:LOOK_ALIKES * len(names)]


def check(drawings, folder, vision, render=None, similar=()):
    """{name: True or False} for [(name, svg document)]: whether the image model, not told which is which, named it right. None when it cannot be checked."""
    model, ask_image = vision[0], vision[1]
    if not drawings or not ask_image:
        return None
    os.makedirs(folder, exist_ok=True)
    sheet = (render or render_sheet)([d for _, d in drawings], os.path.join(folder, f"check_{uuid.uuid4().hex[:6]}.jpg"))
    if not sheet:
        return None
    wanted = [_plain(n) for n, _ in drawings]
    decoys = [d for d in DECOYS if _plain(d) not in wanted][:max(3, len(wanted))]
    names = sorted(set(wanted + [_plain(d) for d in decoys] + [_plain(s) for s in similar]))     # in alphabetical order: the order tells nothing
    with open(sheet, "rb") as f:
        reply = ask_image([f.read()], model, prompt=question(len(drawings), names))
    answers = read_answer(reply, len(drawings))
    if answers is None:
        return None
    return {name: _plain(answers.get(i, "none")) == _plain(name) for i, (name, _) in enumerate(drawings, 1)}


def _draw(name, ask, again=False):
    prompt = art_icons.request(name)
    if again:
        prompt += f"\n\nYour last drawing could not be recognised as {name}. Draw it again with its most typical shape, seen from the side, so that nobody could mistake it."
    for _ in range(art_icons.TRIES):
        markup = art_icons.clean(ask(prompt))
        if markup:
            return markup
    return None


def make(names, ask, folder, vision=None, render=None, directory=None):
    """{name: {"path": svg file or None, "status": "saved before" | "checked" | "unchecked" | "not recognised" | "not drawn"}} for every name asked for."""
    if vision is None:
        from engine.visual_context import choose_backend
        vision = choose_backend()
    results, todo = {}, []
    for name in dict.fromkeys(names):
        saved = load(name, directory)
        if saved:
            results[name] = {"path": saved, "status": "saved before"}
        else:
            todo.append(name)
    for round_ in range(ROUNDS):
        drawn = []
        for name in todo:
            try:
                markup = _draw(name, ask, again=round_ > 0) if ask else None
            except Exception as e:
                print(f"[Warning] The text model could not draw '{name}' ({' '.join(str(e).split())[:100]}).")
                markup = None
            if markup:
                drawn.append((name, svg_doc(markup)))
            else:
                results[name] = {"path": None, "status": "not drawn"}
        verdicts = check(drawn, folder, vision, render, similar=look_alikes([n for n, _ in drawn], ask)) if drawn else {}
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
