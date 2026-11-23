"""Icons drawn by the text model while a video is made, for things the built-in kit (engine/art_kit.py) has no icon for.

The kit covers the topics it was written for. A label about a vaccine, a tractor or a pyramid has no icon there, so the model names the thing and this
module asks it to DRAW that one icon: a single object is far easier than a whole scene (a free-hand scene came out as abstract boxes). The request shows
three kit icons as style examples (line weight, colours, shapes), the answer is checked against a short list of tags and attributes, and the icon is saved
in a library folder, `~/.shortsflow/icons`, so the next video that needs it makes nothing: the library grows with use. A thing the model cannot draw falls
back to the nearest built-in icon (the caller's choice).

Only the name of the thing and the fixed style examples are sent to the text model; the sources and the narration are not.
"""
import json
import os
import re
import xml.etree.ElementTree as ET

from engine import art_kit as kit

ALLOWED_TAGS = {"g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path"}
ALLOWED_ATTRS = {"x", "y", "width", "height", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "stroke", "stroke-width", "stroke-linecap",
                 "stroke-linejoin", "opacity", "fill-opacity", "transform", "stroke-dasharray"}
MIN_SHAPES = 4
MIN_FILLED = 3                 # shapes with a fill: a drawing of outlines only is a few scratches, not an icon
MIN_SPAN = 70                  # the drawing must be at least this wide and this tall (of 200): not a speck in the corner
TRIES = 3
MAX_SHAPES = 60
MAX_BYTES = 12000
LIMIT = 135                     # no coordinate may leave the 200 x 200 box by more than this: the icon must sit where the kit puts its icons
EXAMPLES = ("server", "shield", "rocket")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def home():
    return os.environ.get("SHORTSFLOW_ICONS") or os.path.join(os.path.expanduser("~"), ".shortsflow", "icons")


def slug(concept):
    return re.sub(r"[^a-z0-9]+", "_", str(concept or "").lower()).strip("_")[:30]


def request(concept):
    examples = "\n\n".join(f"Example, a {n}:\n{kit.ICONS[n]('#3b82f6')}" for n in EXAMPLES)
    return (f"Draw ONE flat cartoon icon of: {concept}.\n"
            "It is a single object in the same style as these examples, drawn in a 200 x 200 box centred on (0, 0) (x and y from -100 to 100):\n\n"
            f"{examples}\n\n"
            "Rules: thick dark outlines (stroke=\"#1f2937\" stroke-width=\"6\" stroke-linejoin=\"round\" stroke-linecap=\"round\") on every main shape, bright flat fills "
            "(blue #3b82f6, orange #f59e0b, green #22c55e, purple #8b5cf6, red #ef4444, yellow #facc15, teal #14b8a6, white, light grey), 8 to 25 shapes, the "
            "object large (it should fill about 160 of the 200 units), instantly recognisable, no text or letters. Use only <g>, <rect>, <circle>, <ellipse>, "
            "<line>, <polyline>, <polygon>, <path>. Do not use <svg>, <defs>, gradients, <style> or <image>.\n"
            'Answer with one JSON object and nothing else: {"svg": "<the shapes only, no svg wrapper>"}.')


def _shapes_in(raw):
    """The drawing as text from a model's answer (a JSON {"svg": ...} object, or the markup itself), '' when there is none."""
    text = str(raw or "").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            for v in data.values() if isinstance(data, dict) else []:
                if isinstance(v, str) and "<" in v:
                    text = v
                    break
        except ValueError:
            pass
    m = re.search(r"<svg\b[^>]*>(.*)</svg\s*>", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


def clean(raw):
    """The icon's markup, checked, or None: only flat shapes and plain attributes survive, at least MIN_SHAPES of them, and every number stays near the
    200 x 200 box, so the icon cannot hold a script, a link, an image or a drawing far outside its place."""
    body = _shapes_in(raw)
    if not body or len(body) > MAX_BYTES:
        return None
    try:
        root = ET.fromstring(f"<g xmlns='http://www.w3.org/2000/svg'>{body}</g>")
    except ET.ParseError:
        return None
    shapes = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ALLOWED_TAGS:
            return None
        el.tag = tag
        if tag == "rect" and not (NUMBER.fullmatch(el.attrib.get("width", "")) and NUMBER.fullmatch(el.attrib.get("height", ""))
                                  and float(el.attrib["width"]) > 0 and float(el.attrib["height"]) > 0):
            return None                                 # a rectangle with no size draws nothing (the model forgot width or height)
        if el is not root:
            shapes += tag != "g"
        for attr in list(el.attrib):
            value = el.attrib[attr]
            if attr not in ALLOWED_ATTRS or re.search(r"url\s*\(|javascript:|data:|http", value, re.I):
                del el.attrib[attr]
            elif attr in ("d", "points", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry") and any(abs(float(n)) > (2 * LIMIT if attr in ("width", "height") else LIMIT) for n in NUMBER.findall(value)):
                return None
    if not MIN_SHAPES <= shapes <= MAX_SHAPES:
        return None
    filled = sum(1 for el in root.iter() if el.tag in ("rect", "circle", "ellipse", "polygon", "path") and el.attrib.get("fill", "#000") not in ("none", "transparent"))
    xs, ys = _extent(root)
    if filled < MIN_FILLED or (xs and max(xs) - min(xs) < MIN_SPAN) or (ys and max(ys) - min(ys) < MIN_SPAN):
        return None
    return "".join(ET.tostring(child, encoding="unicode").replace(" xmlns=\"http://www.w3.org/2000/svg\"", "") for child in root)


def _extent(root):
    """The x values and the y values the shapes reach (approximate: a path's numbers are read in pairs), to tell a real drawing from a speck."""
    xs, ys = [], []
    num = lambda el, k: float(el.attrib.get(k, 0) or 0) if NUMBER.fullmatch(str(el.attrib.get(k, 0) or 0)) else 0.0
    for el in root.iter():
        tag, a = el.tag, el.attrib
        if tag in ("circle", "ellipse"):
            rx, ry = num(el, "rx") or num(el, "r"), num(el, "ry") or num(el, "r")
            xs += [num(el, "cx") - rx, num(el, "cx") + rx]
            ys += [num(el, "cy") - ry, num(el, "cy") + ry]
        elif tag == "rect":
            xs += [num(el, "x"), num(el, "x") + num(el, "width")]
            ys += [num(el, "y"), num(el, "y") + num(el, "height")]
        elif tag == "line":
            xs += [num(el, "x1"), num(el, "x2")]
            ys += [num(el, "y1"), num(el, "y2")]
        elif tag in ("polygon", "polyline", "path"):
            nums = [float(n) for n in NUMBER.findall(a.get("points" if tag != "path" else "d", ""))]
            xs += nums[0::2]
            ys += nums[1::2]
    return xs, ys


def path_of(concept, directory=None):
    return os.path.join(directory or home(), f"{slug(concept)}.v2.svg")      # v2: icons saved before the rectangle fix had invisible rectangles


def load(concept, directory=None):
    """The saved markup of an icon, None when it was never made."""
    try:
        with open(path_of(concept, directory), encoding="utf-8") as f:
            return f.read() or None
    except OSError:
        return None


def get(concept, ask, directory=None):
    """The markup of an icon for `concept` (saved, else drawn by the model and saved), None when the model cannot draw it in three tries. Registers it
    with the kit so scenes can use it by name."""
    name = slug(concept)
    if not name:
        return None
    markup = load(name, directory)
    if not markup and ask is not None:
        for _ in range(TRIES):
            try:
                markup = clean(ask(request(concept)))
            except Exception as e:
                print(f"[Warning] The text model could not draw an icon for '{concept}' ({' '.join(str(e).split())[:100]}).")
                return None
            if markup:
                os.makedirs(directory or home(), exist_ok=True)
                with open(path_of(name, directory), "w", encoding="utf-8") as f:
                    f.write(markup)
                break
    if markup:
        kit.register(name, markup)
    return markup
