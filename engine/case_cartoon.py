"""Cartoon pictures for the beats of a case explainer (`--case background=cartoon`): one flat, friendly illustration per `footage` phrase.

Three ways to make a picture, chosen by `--case cartoon=auto|local|cloud|drawn` (auto tries them in this order and keeps the first that works):

  local  the optional image add-on on this PC (engine/image_server.py, Stable Diffusion class model on the GPU). Nothing leaves the PC.
  cloud  Gemini image generation, else a Hugging Face model, with the keys already in `.env`. Only the beat's two-to-four word phrase and
         the fixed style sentence are sent, never the sources or the narration.
  drawn  the text model picks one icon and a setting from the kit in engine/art_kit.py and the kit draws it in one flat style. No download, no GPU;
         with llm=local nothing leaves the PC. Always available when any text model answers.

Pictures are cached by phrase, shape and way of making, so a re-run (or a redo with another look) makes nothing again. A phrase that no way can
draw is skipped: that beat keeps the look's own background.
"""
import base64
import hashlib
import os
import re
import xml.etree.ElementTree as ET

SOURCES = ("auto", "local", "cloud", "drawn")
STYLE = ("flat vector cartoon illustration, bold clean outlines, bright simple colours, friendly explainer-video style, "
         "one clear subject, simple background, no text, no letters, no numbers, no logos, no watermark")
GEMINI_MODEL = "gemini-2.5-flash-image"
HF_MODEL = "black-forest-labs/FLUX.1-schnell"
CLOUD_TIMEOUT = 90


def prompt_for(phrase):
    """The picture request for a beat's phrase: the phrase as the subject plus the one fixed style sentence."""
    phrase = " ".join(re.findall(r"[A-Za-z0-9]+", str(phrase or "")))[:60]
    return f"{phrase}, {STYLE}" if phrase else ""


def shape_of(aspect):
    """(width, height) of the picture for a video shape; local models like multiples of 64."""
    if aspect == "1:1":
        return (768, 768)
    return (576, 1024) if aspect == "9:16" else (1024, 576)


def cache_file(cache_dir, phrase, aspect, source, ext):
    key = hashlib.sha1(f"{phrase.lower().strip()}|{aspect}|{source}|{STYLE}|v3".encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")[:30]
    return os.path.join(cache_dir, f"{slug}_{aspect.replace(':', 'x')}_{source}_{key}.{ext}")


# ---- cloud -------------------------------------------------------------------------------------------------------------------------

def _gemini(prompt, aspect, api_key, post):
    model = os.getenv("GEMINI_IMAGE_MODEL", GEMINI_MODEL)
    r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", params={"key": api_key},
             json={"contents": [{"parts": [{"text": prompt + (", vertical 9:16 composition" if aspect == "9:16" else ", wide 16:9 composition")}]}],
                   "generationConfig": {"responseModalities": ["IMAGE"]}}, timeout=CLOUD_TIMEOUT)
    r.raise_for_status()
    for cand in r.json().get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no picture in the answer")


def _hugging_face(prompt, aspect, api_key, post):
    """Through huggingface_hub, which knows the current provider routes (a fixed URL went stale once); `post` is unused here."""
    import io
    from huggingface_hub import InferenceClient
    w, h = shape_of(aspect)
    image = InferenceClient(api_key=api_key, timeout=CLOUD_TIMEOUT).text_to_image(prompt, model=os.getenv("HF_IMAGE_MODEL", HF_MODEL), width=w, height=h)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def make_cloud(prompt, aspect, post=None, env=None):
    """Picture bytes from Gemini, else Hugging Face; None when neither key is set or both fail."""
    env = env if env is not None else os.environ
    if post is None:
        import requests
        post = requests.post
    for name, key, fn in (("Gemini", env.get("GEMINI_API_KEY"), _gemini), ("Hugging Face", env.get("HF_API_KEY"), _hugging_face)):
        if not key:
            continue
        try:
            return fn(prompt, aspect, key, post)
        except Exception as e:
            print(f"[Warning] {name} could not draw a cartoon ({' '.join(str(e).split())[:100]}).")
    return None


# ---- local add-on ------------------------------------------------------------------------------------------------------------------

def make_local(prompt, aspect, post=None, url=None):
    """Picture bytes from the local image server (engine/image_server.py) when it is running; None when it is not or it fails."""
    from engine import image_server
    if post is None:
        import requests
        post = requests.post
    url = url or image_server.base_url()
    w, h = shape_of(aspect)
    try:
        r = post(f"{url}/generate", json={"prompt": prompt, "width": w, "height": h}, timeout=600)
        r.raise_for_status()
        return r.content if r.content else None
    except Exception as e:
        print(f"[Warning] The local image server could not draw a cartoon ({' '.join(str(e).split())[:100]}).")
        return None


# ---- drawn (a kit icon picked by the text model) ------------------------------------------------------------------------------------

def background_request(phrase):
    from engine import art_kit as kit
    kinds = "\n".join(f"  {k}: {v}" for k, v in kit.HELP.items())
    return (f"Pick ONE icon that best illustrates the phrase \"{phrase}\" for a picture behind an explainer video.\n{kinds}\n"
            f"Colours: {', '.join(kit.COLORS)}. Settings: {', '.join(kit.SETTINGS)} (space for astronomy and physics, night for security, cloud for online services, "
            "city for companies and the public, office for work).\n"
            'Answer with one JSON object and nothing else, like {"setting": "space", "items": [{"kind": "black_hole", "color": "orange"}]}.')


def make_drawn(phrase, aspect, ask):
    """SVG text of a cartoon for `phrase`: the text model `ask(prompt) -> str` picks one icon of the kit (engine/art_kit.py) and the setting, and the kit draws
    it large, off to one side (the scene's panel covers the middle). None after two tries that name no usable icon."""
    from engine import art_kit as kit, case_art
    w, h = shape_of(aspect)
    for _ in range(2):
        try:
            spec, _problem = case_art.check_spec(ask(background_request(phrase)), 1)
            spec = case_art.resolve_custom(spec, ask) if spec else spec
        except Exception as e:
            print(f"[Warning] The text model could not pick a picture for '{phrase}' ({' '.join(str(e).split())[:100]}).")
            return None
        if spec:
            anchor = (50, 30) if h > w else (74, 50)
            layered = kit.compose_layers(dict(spec, links=[]), "16:9", canvas=(w, h), anchor=anchor, big=1.7 if h <= w else 1.5)
            return layered["background"][:-len("</svg>")] + "".join(i[i.index(">") + 1:i.rindex("</svg>")] for i in layered["items"]) + "</svg>"
    return None


# ---- one picture, and the pictures of a script -------------------------------------------------------------------------------------

def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "w" if isinstance(data, str) else "wb"
    with open(path, mode, **({"encoding": "utf-8"} if mode == "w" else {})) as f:
        f.write(data)
    return path


def local_ready():
    from engine import image_server
    return image_server.is_running()


def order(source, has_cloud_key, local_up):
    """The ways to try, in order, for a `cartoon=` choice. A list of ways ("local,drawn") is tried in that order and
    nothing else is added (a way left out is never used); "off" tries none; auto goes local (when its server answers), cloud (when a key is set), drawn."""
    if source == "off":
        return []
    if source not in ("auto", ""):
        return [w for w in dict.fromkeys(x.strip() for x in source.split(",")) if w in ("local", "cloud", "drawn")]
    return (["local"] if local_up else []) + (["cloud"] if has_cloud_key else []) + ["drawn"]


def make_image(phrase, cache_dir, aspect="16:9", source="auto", ask=None, makers=None):
    """Path of a cartoon for `phrase`, None when no way worked. `makers` replaces the three makers (tests): {"local"|"cloud"|"drawn": fn(prompt)}."""
    phrase = " ".join(str(phrase or "").split())
    prompt = prompt_for(phrase)
    if not prompt:
        return None
    makers = makers or {
        "local": lambda p: make_local(p, aspect),
        "cloud": lambda p: make_cloud(p, aspect),
        "drawn": lambda p: make_drawn(phrase, aspect, ask) if ask else None,
    }
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("HF_API_KEY"))
    ways = order(source, has_key, local_ready() if source == "auto" else "local" in source)
    files = {way: cache_file(cache_dir, phrase, aspect, way, "svg" if way == "drawn" else "png") for way in ways}
    for way in ways:                                    # a picture made before is used first, so a re-run asks nobody again
        if os.path.isfile(files[way]):
            return files[way]
    for way in ways:
        data = makers[way](prompt)
        if data:
            return _save(files[way], data)
    return None


def attach(script, session_dir, aspect="16:9", source="auto", ask=None, cache_dir=None, makers=None):
    """[None | [{"path", "kind": "cartoon"}]] per section: a cartoon for each of the section's `footage` phrases, one per beat."""
    cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".shortsflow", "cartoons")
    started = False
    if source == "off":
        return [None] * len(script["sections"])
    if makers is None and ("local" in source or source == "auto"):
        from engine import image_server
        try:
            _, started = image_server.ensure_running()          # installed add-on: started for these pictures only
        except RuntimeError as e:
            print(f"[Warning] {e}")
    try:
        return _attach(script, aspect, source, ask, cache_dir, makers)
    finally:
        if started:
            from engine import image_server
            image_server.stop()                                  # give the graphics card back


def _attach(script, aspect, source, ask, cache_dir, makers):
    out = []
    for sec in script["sections"]:
        if sec.get("scene") == "illustration":          # its own picture fills the scene: a background would be hidden behind it
            out.append(None)
            continue
        phrases = sec.get("footage") or []
        phrases = [phrases] if isinstance(phrases, str) else phrases
        found = []
        for phrase in phrases:
            got = make_image(phrase, cache_dir, aspect, source, ask=ask, makers=makers) if phrase else None
            if got and all(got != f["path"] for f in found):
                found.append({"path": got, "kind": "cartoon"})
        out.append(found or None)
    return out
