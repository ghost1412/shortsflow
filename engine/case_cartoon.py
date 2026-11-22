"""Cartoon pictures for the beats of a case explainer (`--case background=cartoon`): one flat, friendly illustration per `footage` phrase.

Three ways to make a picture, chosen by `--case cartoon=auto|local|cloud|drawn` (auto tries them in this order and keeps the first that works):

  local  the optional image add-on on this PC (engine/image_server.py, Stable Diffusion class model on the GPU). Nothing leaves the PC.
  cloud  Gemini image generation, else a Hugging Face model, with the keys already in `.env`. Only the beat's two-to-four word phrase and
         the fixed style sentence are sent, never the sources or the narration.
  drawn  the text model writes a simple SVG scene (flat shapes, no text), checked against a short list of allowed tags. No download, no GPU;
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
    key = hashlib.sha1(f"{phrase.lower().strip()}|{aspect}|{source}|{STYLE}|v2".encode("utf-8")).hexdigest()[:10]
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


# ---- drawn (SVG written by the text model) -------------------------------------------------------------------------------------------

ALLOWED_TAGS = {"svg", "g", "defs", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "linearGradient", "radialGradient", "stop"}
ALLOWED_ATTRS = {"viewBox", "xmlns", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "stroke",
                 "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform", "id", "offset",
                 "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "fx", "fy", "preserveAspectRatio"}
MAX_SVG = 40000


def _unwrap(raw):
    """The reply as plain text: some providers answer in JSON mode, so the SVG arrives as a string inside {"svg": "..."} with escaped quotes."""
    import json
    text = str(raw or "").strip()
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
            for v in (list(data.values()) if isinstance(data, dict) else list(data)):
                if isinstance(v, str) and "<svg" in v:
                    return v
        except ValueError:
            pass
    return text


def clean_svg(raw, aspect="16:9"):
    """A safe SVG text from a model's reply, None when it is not usable: only flat-shape tags and plain attributes are kept, no scripts, links,
    images, styles or fonts, so the file can only draw shapes. The viewBox is forced to the video shape."""
    text = _unwrap(raw)
    m = re.search(r"<svg\b.*?</svg\s*>", text, re.S | re.I)
    if not m or len(m.group(0)) > MAX_SVG:
        return None
    try:
        root = ET.fromstring(m.group(0))
    except ET.ParseError:
        return None
    count = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ALLOWED_TAGS:
            return None
        el.tag = tag                                   # no namespace on the tags: the one xmlns is written once below
        count += 1
        for attr in list(el.attrib):
            name = attr.split("}")[-1]
            value = el.attrib[attr]
            if name not in ALLOWED_ATTRS or re.search(r"url\s*\(\s*(?!#)|javascript:|data:|http", value, re.I):
                del el.attrib[attr]
    if count < 6:
        return None                                    # an empty or one-shape answer is not a scene
    w, h = shape_of(aspect)
    root.set("width", str(w))                          # an explicit size: an image with only a viewBox cannot always be decoded
    root.set("height", str(h))
    root.set("viewBox", f"0 0 {w} {h}")
    root.set("preserveAspectRatio", "xMidYMid slice")
    root.set("xmlns", "http://www.w3.org/2000/svg")
    return ET.tostring(root, encoding="unicode")


def svg_request(phrase, aspect):
    w, h = shape_of(aspect)
    return (f"Draw ONE flat cartoon illustration of: {phrase}.\n"
            f"Answer with a single SVG and nothing else. Canvas: viewBox=\"0 0 {w} {h}\". Style: flat colours, simple rounded shapes, thick dark "
            "outlines, a bright friendly palette, a plain sky or wall as the background, one clear subject in the middle, small details around it.\n"
            "Rules: use only <svg>, <g>, <defs>, <linearGradient>, <radialGradient>, <stop>, <rect>, <circle>, <ellipse>, <line>, <polyline>, "
            "<polygon>, <path>. No <text>, no <image>, no <style>, no scripts, no links, no fonts. Give 15 to 40 shapes. Keep the main subject "
            "inside the middle 70% of the canvas.")


def make_drawn(phrase, aspect, ask):
    """SVG text drawn by the text model `ask(prompt) -> str`; None after two tries that fail the checks."""
    for _ in range(2):
        try:
            svg = clean_svg(ask(svg_request(phrase, aspect)), aspect)
        except Exception as e:
            print(f"[Warning] The text model could not draw '{phrase}' ({' '.join(str(e).split())[:100]}).")
            return None
        if svg:
            return svg
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
        phrases = sec.get("footage") or []
        phrases = [phrases] if isinstance(phrases, str) else phrases
        found = []
        for phrase in phrases:
            got = make_image(phrase, cache_dir, aspect, source, ask=ask, makers=makers) if phrase else None
            if got and all(got != f["path"] for f in found):
                found.append({"path": got, "kind": "cartoon"})
        out.append(found or None)
    return out
