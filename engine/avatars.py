"""The drawn presenters of the case explainer (`--case avatar=NAME`): ready-made ones and the ones people make, which are saved as small JSON
files in the workspace's `presenters/` folder. The drawing is remotion-video/src/Presenter.tsx; this file only holds the parts list and checks
it, so a home-made file can never pass anything but known parts and colours to the renderer.

A presenter is a kind (a person, a cat, a dog or a robot) plus parts: skin or fur colour, hair style and colour, eye colour, beard, glasses,
lashes, lip and outfit colours, and for animals a pattern and a lighter fur colour. People of any gender are made from the same parts.
"""
import json
import os
import re

KINDS = ("human", "cat", "dog", "robot", "photo")       # photo: a real face that talks (engine/talking_head.py, optional add-on)
HAIR = ("short", "side", "long", "bob", "bun", "curly", "ponytail", "bald")
BEARD = ("none", "stubble", "full", "moustache")
GLASSES = ("none", "round", "square")
PATTERN = ("plain", "tabby", "patch")
COLOURS = ("skin", "hairColor", "eyeColor", "lips", "outfit", "furLight")
CHOICES = {"kind": KINDS, "hair": HAIR, "beard": BEARD, "glasses": GLASSES, "pattern": PATTERN}
FOLDER = "presenters"

DEFAULT = {"kind": "human", "name": "", "skin": "#f1c3a0", "hair": "short", "hairColor": "#2b1d15", "eyeColor": "#3b6fd8", "beard": "none",
           "glasses": "none", "lashes": False, "lips": "#b0505a", "outfit": "#ff8a3d", "pattern": "plain", "furLight": "#fff4e8"}

# Skin tones to pick from (light to deep) and hair colours, so the builder and the photo suggestion speak the same small vocabulary.
SKIN_TONES = {"very light": "#f8d9c0", "light": "#f1c3a0", "medium light": "#dfa67b", "medium": "#c68e64", "medium deep": "#a0683f", "deep": "#7a4a2a", "very deep": "#4f2e1a"}
HAIR_COLOURS = {"black": "#1b1512", "dark brown": "#2b1d15", "brown": "#5a3a24", "auburn": "#7a2f1a", "red": "#b4451f", "blonde": "#d9b26a",
                "grey": "#9a9a9a", "white": "#e9e6e0", "blue": "#3d6fe0", "pink": "#e06aa6"}
EYE_COLOURS = {"brown": "#5b3a1e", "dark brown": "#3a2412", "blue": "#3b6fd8", "green": "#3f9a52", "grey": "#7b8894", "hazel": "#8a6a2c", "amber": "#d39a2a"}

PRESETS = {
    "alex": {"kind": "human", "name": "Alex", "hair": "short", "hairColor": "#2b1d15", "skin": "#f1c3a0", "eyeColor": "#3b6fd8", "outfit": "#ff8a3d"},
    "maya": {"kind": "human", "name": "Maya", "hair": "long", "hairColor": "#3a2418", "skin": "#e9b48e", "eyeColor": "#5b3a1e", "lashes": True,
             "lips": "#c0505f", "outfit": "#14b8a6"},
    "priya": {"kind": "human", "name": "Priya", "hair": "bun", "hairColor": "#1b1512", "skin": "#c68e64", "eyeColor": "#3a2412", "lashes": True,
              "glasses": "square", "lips": "#a8404e", "outfit": "#8b5cf6"},
    "sam": {"kind": "human", "name": "Sam", "hair": "curly", "hairColor": "#1b1512", "skin": "#8d5a3b", "eyeColor": "#3a2412", "beard": "stubble",
            "glasses": "round", "lips": "#7a3a3a", "outfit": "#22c55e"},
    "leo": {"kind": "human", "name": "Leo", "hair": "side", "hairColor": "#d9b26a", "skin": "#f8d9c0", "eyeColor": "#3f9a52", "beard": "full",
            "outfit": "#2563eb"},
    "nora": {"kind": "human", "name": "Nora", "hair": "bob", "hairColor": "#9a9a9a", "skin": "#f1c3a0", "eyeColor": "#7b8894", "lashes": True,
             "glasses": "round", "lips": "#b0505a", "outfit": "#e11d48"},
    "miso": {"kind": "cat", "name": "Miso", "skin": "#f0a050", "pattern": "tabby", "eyeColor": "#3f9a52", "furLight": "#fff4e8"},
    "luna": {"kind": "cat", "name": "Luna", "skin": "#7d8696", "pattern": "plain", "eyeColor": "#d39a2a", "furLight": "#e9edf3"},
    "biscuit": {"kind": "dog", "name": "Biscuit", "skin": "#c98a4a", "pattern": "patch", "eyeColor": "#3a2412", "furLight": "#fbe8cf"},
    "bolt": {"kind": "robot", "name": "Bolt", "skin": "#c9d2e3", "eyeColor": "#38e1ff"},
}


def clean(spec):
    """A safe presenter spec: only known parts and #rrggbb colours, anything else replaced by the default. Raises ValueError when it is not a dict."""
    if not isinstance(spec, dict):
        raise ValueError("A presenter is a set of parts (a JSON object).")
    out = dict(DEFAULT)
    for key, allowed in CHOICES.items():
        if spec.get(key) in allowed:
            out[key] = spec[key]
    for key in COLOURS:
        if isinstance(spec.get(key), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", spec[key]):
            out[key] = spec[key].lower()
    out["lashes"] = bool(spec.get("lashes", False))
    if out["kind"] == "photo":
        photo = str(spec.get("photo") or "")
        if not re.fullmatch(r"[a-z0-9_-]{1,30}\.(jpg|png)", photo):
            raise ValueError("A photo presenter needs its photo saved with it (save it from the Presenters card).")
        out["photo"] = photo
    out["name"] = re.sub(r"[^\w .'-]", "", str(spec.get("name") or ""))[:20].strip()
    return out


def slug(name):
    return re.sub(r"[^a-z0-9_-]", "", str(name or "").lower().replace(" ", "_"))[:30]


def folder(home):
    return os.path.join(home, FOLDER)


def names(home=None):
    """Every presenter that can be chosen: the ready-made ones, then the saved ones."""
    saved = []
    if home and os.path.isdir(folder(home)):
        saved = sorted(os.path.splitext(f)[0] for f in os.listdir(folder(home)) if f.endswith(".json") and slug(os.path.splitext(f)[0]))
    return list(PRESETS) + [n for n in saved if n not in PRESETS]


def load(name, home=None):
    """The clean spec of a presenter by name (ready-made or saved), or None for off/empty. Raises ValueError for an unknown name."""
    key = slug(name)
    if not key or key in ("off", "none", "no"):
        return None
    if home:
        path = os.path.join(folder(home), key + ".json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return clean(json.load(f))
    if key in PRESETS:
        return clean(PRESETS[key])
    raise ValueError(f"No presenter called '{name}'. Choose from: {', '.join(names(home))}, or off.")


def save(home, name, spec):
    """Save a home-made presenter as presenters/<name>.json in the workspace. Returns (slug, path). A ready-made name cannot be overwritten."""
    key = slug(name)
    if not key:
        raise ValueError("Give the presenter a name (letters and numbers).")
    if key in PRESETS:
        raise ValueError(f"'{key}' is a ready-made presenter: pick another name.")
    data = clean({**spec, "name": spec.get("name") or name})
    os.makedirs(folder(home), exist_ok=True)
    path = os.path.join(folder(home), key + ".json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)
    return key, path


def nearest(table, colour):
    """The name in `table` whose colour is closest to `colour` (#rrggbb)."""
    def rgb(c):
        n = int(c[1:], 16)
        return n >> 16, (n >> 8) & 255, n & 255
    r, g, b = rgb(colour)
    return min(table, key=lambda k: sum((x - y) ** 2 for x, y in zip(rgb(table[k]), (r, g, b))))


PHOTO_PROMPT = ("Look at the person in this photo and describe them for a cartoon avatar. Reply with JSON only, no other text: "
                '{"skin": one of [' + ", ".join(f'"{k}"' for k in SKIN_TONES) + '], '
                '"hair": one of [' + ", ".join(f'"{k}"' for k in HAIR) + '] (long = past the shoulders, bob = chin length, side = short with a side sweep), '
                '"hair_color": one of [' + ", ".join(f'"{k}"' for k in HAIR_COLOURS) + '], '
                '"eye_color": one of [' + ", ".join(f'"{k}"' for k in EYE_COLOURS) + '], '
                '"beard": one of [' + ", ".join(f'"{k}"' for k in BEARD) + '], '
                '"glasses": one of [' + ", ".join(f'"{k}"' for k in GLASSES) + '], "lashes": true or false (long visible eyelashes or eye makeup)}')


def _photo_jpeg(path, size=768):
    from PIL import Image, ImageOps
    import io
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((size, size))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        return buf.getvalue()


def from_answer(text, base=None):
    """A clean spec from the vision model's JSON answer (names from the small vocabularies above); unknown values keep `base`'s parts."""
    spec = dict(base or DEFAULT)
    spec["kind"] = "human"
    m = re.search(r"\{.*\}", str(text or ""), re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict) or not data:
        raise ValueError("The vision model did not describe the photo. Try a clear, front-facing photo, or set the parts by hand.")
    pick = lambda v: str(v or "").strip().lower()
    if pick(data.get("skin")) in SKIN_TONES:
        spec["skin"] = SKIN_TONES[pick(data["skin"])]
    if pick(data.get("hair")) in HAIR:
        spec["hair"] = pick(data["hair"])
    if pick(data.get("hair_color")) in HAIR_COLOURS:
        spec["hairColor"] = HAIR_COLOURS[pick(data["hair_color"])]
    if pick(data.get("eye_color")) in EYE_COLOURS:
        spec["eyeColor"] = EYE_COLOURS[pick(data["eye_color"])]
    if pick(data.get("beard")) in BEARD:
        spec["beard"] = pick(data["beard"])
    if pick(data.get("glasses")) in GLASSES:
        spec["glasses"] = pick(data["glasses"])
    if isinstance(data.get("lashes"), bool):
        spec["lashes"] = data["lashes"]
    return clean(spec)


def suggest_from_photo(path, use="local", base=None, ask=None):
    """Suggest a person presenter that looks like the one in a photo. `use` is "local" (an Ollama vision model on this PC: the photo stays here)
    or "gemini" (the photo is sent to Google). Returns (spec, message). Raises ValueError with a plain reason when it cannot."""
    from engine import visual_context as vc
    if not path or not os.path.isfile(path):
        raise ValueError("Choose a photo first.")
    if ask is None:
        if use == "gemini":
            if not vc.gemini_key():
                raise ValueError("Reading the photo with Gemini needs a Gemini key (Settings). Or choose 'this PC'.")
            ask = lambda frames, prompt: vc.describe_gemini(frames, vc.GEMINI_MODELS[0], prompt=prompt)
            label = "Gemini (the photo was sent to Google)"
        else:
            model = vc.pick_vision_model()
            if not model:
                raise ValueError("Reading the photo on this PC needs a local vision model: install Ollama and run `ollama pull gemma3:12b`.")
            ask = lambda frames, prompt: vc.describe(frames, model, prompt=prompt)
            label = f"{model} on this PC (the photo stayed here)"
    else:
        label = "test"
    spec = from_answer(ask([_photo_jpeg(path)], PHOTO_PROMPT), base)
    return spec, f"Suggested by {label}. Check it in the preview and change anything that is off."


PREVIEW_WORDS = "Hi there I am your host and I will walk you through it".split()


def render_preview(spec, out_path, accent="#00e5a8", remotion_dir=None, run=None):
    """A 3-second silent clip of the presenter's card saying a few words (the builder's preview). Returns out_path. Raises RuntimeError on failure."""
    import subprocess
    import uuid
    remotion_dir = remotion_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "remotion-video")
    words, t = [], 0.4
    for w in PREVIEW_WORDS:
        words.append({"word": w, "start": round(t, 2), "end": round(t + 0.17 + 0.03 * len(w), 2)})
        t = words[-1]["end"] + 0.04
    props_name = f"temp_props_presenter_{uuid.uuid4().hex[:8]}.json"
    props_path = os.path.join(remotion_dir, props_name)
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump({"avatar": clean(spec), "words": words, "accent": accent}, f)
    cmd = ["npx", "remotion", "render", "PresenterCard", os.path.abspath(out_path), f"--props={props_name}", "--codec=h264", "--log=error"]
    try:
        result = (run or subprocess.run)(" ".join(f'"{c}"' if " " in c else c for c in cmd) if os.name == "nt" else cmd, shell=os.name == "nt",
                                         cwd=remotion_dir, capture_output=True, text=True, timeout=300)
    finally:
        try:
            os.remove(props_path)
        except OSError:
            pass
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError("The preview could not be drawn: " + (getattr(result, "stderr", "") or "")[-300:])
    return out_path


KIND_LABELS = {"human": "person", "cat": "cat", "dog": "dog", "robot": "robot", "photo": "real photo"}


def save_photo(home, name, photo_path):
    """Save a realistic presenter: the photo (resized, EXIF turned upright) as presenters/<name>.jpg and its JSON. Returns (slug, path)."""
    from PIL import Image, ImageOps
    key = slug(name)
    if not key:
        raise ValueError("Give the presenter a name (letters and numbers).")
    if key in PRESETS:
        raise ValueError(f"'{key}' is a ready-made presenter: pick another name.")
    if not photo_path or not os.path.isfile(photo_path):
        raise ValueError("Choose a photo first.")
    os.makedirs(folder(home), exist_ok=True)
    with Image.open(photo_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1024, 1024))
        im.save(os.path.join(folder(home), key + ".jpg"), "JPEG", quality=92)
    path = os.path.join(folder(home), key + ".json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(clean({"kind": "photo", "name": name, "photo": key + ".jpg"}), f, indent=1)
    return key, path


def photo_path(spec, home):
    """The full path of a photo presenter's picture, or None."""
    if spec and spec.get("kind") == "photo" and home:
        path = os.path.join(folder(home), spec["photo"])
        return path if os.path.isfile(path) else None
    return None


def choices(home=None):
    """[(label, name)] for a picker: Off first, then every presenter with its kind."""
    out = [("Off (no presenter)", "off")]
    for n in names(home):
        try:
            spec = load(n, home)
        except (ValueError, OSError):
            continue
        out.append((f"{spec.get('name') or n} ({KIND_LABELS[spec['kind']]}{', saved' if n not in PRESETS else ''})", n))
    return out
