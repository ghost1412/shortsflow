"""The drawings of the story look of the case explainer (`--case template=story`): characters and backdrops, drawn by code.

A character is a bust (head, shoulders, headgear, ornaments) described by a small spec the text model fills in (`clean_spec` checks it: only known parts and
colours), so the same spec always draws the same person and the person can be saved (`engine/case_story.py`) and met again in another video. A backdrop is a sky
(sunset, dusk, night, dawn, fire, storm, rays, day) with a ground silhouette (battlefield, hills, city, trees, sea, none). Both are flat shapes with soft light, no
photographs and no image model: nothing leaves the PC.
"""
import math
import random
import re

from engine import story_beasts

SKIN = {"fair": "#f1c9a0", "tan": "#d9a066", "brown": "#b57a47", "dark": "#7d4d2e", "blue": "#3f6fd8", "grey": "#b9b3a8", "green": "#6fae6a", "ashen": "#d9d6cf", "red": "#b85342"}
FIGURES = ("man", "woman", "child")
HAIR = ("short", "long", "braid", "bun", "bald", "snakes")
HAIR_COLOURS = {"black": "#1f1620", "brown": "#5a3a22", "white": "#e9e6e1", "red": "#9a3b1c", "blonde": "#d9ac52"}
MARKINGS = ("none", "stripe", "paint", "scar")
HEADGEAR = ("crown", "helmet", "turban", "topknot", "hood", "hat", "cap", "military_cap", "space_helmet", "none")
FACIAL_HAIR = ("none", "moustache", "beard", "long_beard")
OUTFITS = ("armour", "robe", "shawl", "simple", "suit", "shirt", "uniform", "lab_coat", "dress", "spacesuit", "none")
ORNAMENTS = ("halo", "feather", "tilak", "earrings", "necklace", "glasses", *story_beasts.FEATURES)
SPECIES = story_beasts.SPECIES
MOODS = ("neutral", "stern", "sad", "angry", "proud", "calm")
WEAPONS = ("none", "bow", "spear", "staff", "sword", "twin_blades", "trident")
AGES = ("young", "adult", "old")
COLOURS = {"gold": "#e9b949", "silver": "#c9ced6", "red": "#c0392b", "blue": "#2f5fc4", "green": "#2e8b57", "purple": "#7b3fa0", "white": "#f4efe6",
           "black": "#241a2b", "saffron": "#e8832a", "teal": "#1f8a8a", "maroon": "#7a1f2b", "brown": "#7a4a2a"}
SKIES = ("sunset", "dusk", "night", "dawn", "fire", "storm", "rays", "day")
GROUNDS = ("battlefield", "hills", "city", "trees", "sea", "none")

MODERN_OUTFITS = ("suit", "shirt", "uniform", "lab_coat", "dress", "spacesuit")
DEFAULT_SPEC = {"skin": "tan", "headgear": "none", "headgear_colour": "gold", "facial_hair": "none", "outfit": "robe", "outfit_colour": "maroon",
                "trim_colour": "gold", "ornaments": [], "mood": "neutral", "weapon": "none", "age": "adult", "figure": "man", "hair": "short", "hair_colour": "black",
                "marking": "none", "marking_colour": "red", "species": "human", "coat_colour": ""}


def _hex(value, table, default):
    v = str(value or "").strip().lower()
    if v in table:
        return v
    return default


def clean_spec(raw):
    """A spec with only known values (anything else falls back to the default for that part); a skin may also be a '#rrggbb' colour."""
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULT_SPEC)
    out["species"] = _hex(raw.get("species"), SPECIES, "human")
    coat = str(raw.get("coat_colour") or "").strip().lower()
    out["coat_colour"] = coat if coat in story_beasts.COATS and out["species"] != "human" else ""
    skin = str(raw.get("skin") or "").strip().lower()
    out["skin"] = skin if skin in SKIN or re.fullmatch(r"#[0-9a-f]{6}", skin) else DEFAULT_SPEC["skin"]
    out["headgear"] = _hex(raw.get("headgear"), HEADGEAR, "none")
    out["facial_hair"] = _hex(raw.get("facial_hair"), FACIAL_HAIR, "none")
    out["outfit"] = _hex(raw.get("outfit"), OUTFITS, "robe" if out["species"] == "human" else "none")      # an animal wears only what it is given
    if out["species"] == "human" and out["outfit"] == "none":
        out["outfit"] = "simple"
    out["mood"] = _hex(raw.get("mood"), MOODS, "neutral")
    out["weapon"] = _hex(raw.get("weapon"), WEAPONS, "none")
    out["age"] = _hex(raw.get("age"), AGES, "adult")
    out["figure"] = _hex(raw.get("figure"), FIGURES, "man")
    out["hair"] = _hex(raw.get("hair"), HAIR, "long" if out["figure"] == "woman" else "short")
    out["hair_colour"] = _hex(raw.get("hair_colour"), HAIR_COLOURS, "white" if out["age"] == "old" else "black")
    out["marking"] = _hex(raw.get("marking"), MARKINGS, "none")
    if out["figure"] != "man":
        out["facial_hair"] = "none"
    for key, default in (("headgear_colour", "gold"), ("outfit_colour", "maroon"), ("trim_colour", "gold"), ("marking_colour", "red")):
        out[key] = _hex(raw.get(key), COLOURS, default)
    orn = raw.get("ornaments")
    orn = [orn] if isinstance(orn, str) else orn if isinstance(orn, list) else []
    out["ornaments"] = [o for o in dict.fromkeys(str(x).strip().lower() for x in orn) if o in ORNAMENTS]
    if out["outfit"] in MODERN_OUTFITS:                  # someone dressed for the modern age keeps nothing of an old tale (a model gave a cosmonaut a halo)
        out["ornaments"] = [o for o in out["ornaments"] if o not in ("halo", "tilak", "feather")]
        if out["marking"] in ("stripe", "paint"):
            out["marking"] = "none"
        if out["weapon"] in ("bow", "spear", "staff", "sword", "twin_blades", "trident"):
            out["weapon"] = "none"
        if out["headgear"] in ("helmet", "topknot"):
            out["headgear"] = "none"
        if out["figure"] == "man" and out["hair"] in ("braid", "bun"):
            out["hair"] = "short"
    return out


def _mix(a, b, t):
    """The colour t of the way from hex a to hex b."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def shade(colour, k=0.25):
    return _mix(colour, "#000000", k)


def tint(colour, k=0.3):
    return _mix(colour, "#ffffff", k)


def _skin(spec):
    s = spec["skin"]
    return SKIN.get(s) or s


# ---------------------------------------------------------------- characters (600 x 800)

def _suit(base, dark, trim):
    return [f'<path d="M214 470 L300 668 L386 470 Z" fill="#f6f3ec"/>',
            f'<path d="M285 492 L315 492 L327 520 L316 650 L300 676 L284 650 L273 520 Z" fill="{trim}"/><path d="M285 492 L315 492 L306 516 L294 516 Z" fill="{shade(trim, 0.3)}"/>',
            f'<path d="M214 470 L186 486 L238 570 L212 590 L300 700 L262 560 Z" fill="{dark}"/><path d="M386 470 L414 486 L362 570 L388 590 L300 700 L338 560 Z" fill="{shade(base, 0.4)}"/>',
            f'<circle cx="300" cy="730" r="10" fill="{shade(base, 0.5)}"/><circle cx="300" cy="772" r="10" fill="{shade(base, 0.5)}"/>']


def _shirt(base, dark, trim):
    light = tint(base, 0.45)
    return [f'<path d="M240 468 L300 520 L262 548 L222 484 Z" fill="{light}"/><path d="M360 468 L300 520 L338 548 L378 484 Z" fill="{light}"/>',
            f'<path d="M300 520 L300 800" stroke="{dark}" stroke-width="7"/>'] + [f'<circle cx="314" cy="{y}" r="8" fill="{light}"/>' for y in (566, 636, 706, 776)]


def _uniform(base, dark, trim):
    buttons = "".join(f'<circle cx="{x}" cy="{y}" r="11" fill="{trim}"/>' for x in (258, 342) for y in (566, 632, 698))
    return [f'<path d="M236 466 L300 512 L364 466 L364 500 L300 548 L236 500 Z" fill="{dark}"/>', buttons,
            f'<rect x="76" y="540" width="108" height="30" rx="12" fill="{trim}" transform="rotate(-20 130 555)"/><rect x="416" y="540" width="108" height="30" rx="12" fill="{trim}" transform="rotate(20 470 555)"/>',
            f'<rect x="378" y="610" width="76" height="14" fill="#d83a3a"/><rect x="378" y="628" width="76" height="14" fill="#f4efe6"/><rect x="378" y="646" width="76" height="14" fill="#2f5fc4"/>',
            f'<rect x="150" y="742" width="300" height="26" fill="{dark}"/><rect x="280" y="738" width="40" height="34" rx="6" fill="{trim}"/>']


def _lab_coat(base, dark, trim):
    coat, fold = "#f4f2ee", "#cfcbc2"
    return [f'<path d="M20 800 L48 610 Q70 505 190 470 L410 470 Q530 505 552 610 L580 800 Z" fill="{coat}"/><path d="M300 470 L410 470 Q530 505 552 610 L580 800 L300 800 Z" fill="{fold}" opacity="0.55"/>',
            f'<path d="M226 470 L300 640 L374 470 Z" fill="{base}"/>',
            f'<path d="M226 470 L196 492 L246 566 L222 584 L300 690 L272 560 Z" fill="{fold}"/><path d="M374 470 L404 492 L354 566 L378 584 L300 690 L328 560 Z" fill="{shade(fold, 0.12)}"/>',
            f'<path d="M300 690 L300 800" stroke="{shade(fold, 0.3)}" stroke-width="6"/><rect x="386" y="680" width="92" height="82" rx="8" fill="none" stroke="{shade(fold, 0.3)}" stroke-width="6"/>',
            f'<rect x="410" y="652" width="10" height="40" fill="{trim}"/>']


def _dress(base, dark, trim):
    return [f'<path d="M222 470 Q300 560 378 470 Z" fill="{shade(base, 0.45)}"/><path d="M222 470 Q300 560 378 470" stroke="{trim}" stroke-width="12" fill="none"/>',
            f'<path d="M160 700 Q300 730 440 700 L440 726 Q300 756 160 726 Z" fill="{trim}"/><path d="M110 600 Q150 680 138 800 M490 600 Q450 680 462 800" stroke="{dark}" stroke-width="10" fill="none"/>']


def _spacesuit(base, dark, trim):
    suit, fold, metal = "#eeece6", "#bfbcb3", COLOURS["silver"]
    return [f'<path d="M6 800 L30 590 Q60 480 190 456 L410 456 Q540 480 570 590 L594 800 Z" fill="{suit}"/><path d="M300 456 L410 456 Q540 480 570 590 L594 800 L300 800 Z" fill="{fold}" opacity="0.5"/>',
            f'<ellipse cx="300" cy="476" rx="104" ry="34" fill="{metal}"/><ellipse cx="300" cy="470" rx="78" ry="22" fill="{shade(metal, 0.35)}"/>',
            f'<path d="M96 540 Q132 660 118 800 M504 540 Q468 660 482 800" stroke="{fold}" stroke-width="14" fill="none"/>',
            f'<rect x="216" y="590" width="168" height="112" rx="16" fill="{shade(suit, 0.14)}" stroke="{shade(fold, 0.25)}" stroke-width="6"/>',
            '<circle cx="250" cy="626" r="15" fill="#d83a3a"/><circle cx="300" cy="626" r="15" fill="#2f5fc4"/><circle cx="350" cy="626" r="15" fill="#e9b949"/><rect x="240" y="662" width="120" height="18" rx="9" fill="#5b5964"/>',
            f'<circle cx="448" cy="600" r="30" fill="{trim}"/><circle cx="448" cy="600" r="18" fill="none" stroke="#f6f3ec" stroke-width="5"/>']


MODERN = {"suit": _suit, "shirt": _shirt, "uniform": _uniform, "lab_coat": _lab_coat, "dress": _dress, "spacesuit": _spacesuit}


def _body(spec, trim):
    outfit, base = spec["outfit"], COLOURS[spec["outfit_colour"]]
    dark = shade(base, 0.28)
    parts = [f'<path d="M20 800 L48 610 Q70 505 190 470 L410 470 Q530 505 552 610 L580 800 Z" fill="{base}"/>',
             f'<path d="M300 470 L410 470 Q530 505 552 610 L580 800 L300 800 Z" fill="{dark}" opacity="0.55"/>']
    if outfit == "armour":
        parts += [f'<circle cx="112" cy="595" r="74" fill="{trim}"/><circle cx="112" cy="595" r="56" fill="none" stroke="{shade(trim, 0.35)}" stroke-width="6"/>',
                  f'<circle cx="488" cy="595" r="74" fill="{shade(trim, 0.12)}"/><circle cx="488" cy="595" r="56" fill="none" stroke="{shade(trim, 0.45)}" stroke-width="6"/>',
                  f'<path d="M190 480 Q300 540 410 480 L420 800 L180 800 Z" fill="{tint(base, 0.08)}"/>',
                  f'<path d="M180 690 L420 690 L420 724 L180 724 Z" fill="{trim}"/>',
                  f'<circle cx="300" cy="640" r="30" fill="{trim}"/><circle cx="300" cy="640" r="15" fill="{shade(trim, 0.4)}"/>']
    elif outfit == "robe":
        parts += [f'<path d="M205 472 L300 640 L395 472 Z" fill="{tint(base, 0.18)}"/>',
                  f'<path d="M205 472 L300 640" stroke="{trim}" stroke-width="12" fill="none"/><path d="M395 472 L300 640" stroke="{trim}" stroke-width="12" fill="none"/>',
                  f'<rect x="170" y="700" width="260" height="22" fill="{trim}"/>']
    elif outfit == "shawl":
        parts += [f'<path d="M60 640 Q300 470 540 640 L560 800 L40 800 Z" fill="{tint(base, 0.12)}"/>',
                  f'<path d="M60 640 Q300 470 540 640" stroke="{trim}" stroke-width="10" fill="none"/>',
                  f'<path d="M210 530 L390 700" stroke="{dark}" stroke-width="22" opacity="0.5"/>']
    elif outfit in MODERN:
        parts += MODERN[outfit](base, dark, trim)
    else:
        parts += [f'<path d="M230 470 Q300 520 370 470" fill="{dark}"/>']
    if "necklace" in spec["ornaments"] or outfit == "armour":
        rng = random.Random(7)
        beads = ""
        for i in range(13):
            t = i / 12
            x = 210 + 180 * t
            y = 482 + 78 * math.sin(math.pi * t)
            beads += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="{rng.choice([trim, "#e24b4b", "#3aa6a6", "#f4efe6"])}"/>'
        parts.append(beads)
        parts.append(f'<circle cx="300" cy="568" r="22" fill="{trim}"/><circle cx="300" cy="568" r="11" fill="#e24b4b"/>')
    return "".join(parts)


def _headgear(spec, skin):
    kind, base = spec["headgear"], COLOURS[spec["headgear_colour"]]
    dark, light = shade(base, 0.3), tint(base, 0.35)
    jewel = "#d83a3a"
    if kind == "crown":
        crown = (f'<path d="M205 195 L190 90 L240 140 L270 52 L300 130 L330 52 L360 140 L410 90 L395 195 Q300 170 205 195 Z" fill="{base}"/>'
                 f'<path d="M205 195 Q300 170 395 195 L395 214 Q300 190 205 214 Z" fill="{dark}"/>'
                 f'<path d="M270 52 L300 130 L330 52" fill="none" stroke="{light}" stroke-width="5"/>'
                 f'<circle cx="300" cy="172" r="16" fill="{jewel}"/><circle cx="300" cy="172" r="7" fill="{tint(jewel, 0.6)}"/>'
                 f'<circle cx="250" cy="182" r="9" fill="#2f8f8f"/><circle cx="350" cy="182" r="9" fill="#2f8f8f"/>'
                 f'<circle cx="270" cy="52" r="10" fill="{jewel}"/><circle cx="330" cy="52" r="10" fill="{jewel}"/>')
        return crown
    if kind == "helmet":
        return (f'<path d="M200 214 Q205 95 300 40 Q395 95 400 214 Q300 188 200 214 Z" fill="{base}"/>'
                f'<path d="M300 40 L300 192" stroke="{dark}" stroke-width="8"/>'
                f'<path d="M200 214 Q300 188 400 214 L400 232 Q300 208 200 232 Z" fill="{dark}"/>'
                f'<path d="M300 40 L300 8" stroke="{base}" stroke-width="12" stroke-linecap="round"/><circle cx="300" cy="14" r="12" fill="{jewel}"/>'
                f'<path d="M232 120 Q300 70 368 120" stroke="{light}" stroke-width="6" fill="none"/>')
    if kind == "turban":
        return (f'<ellipse cx="300" cy="150" rx="118" ry="86" fill="{base}"/>'
                f'<path d="M190 168 Q300 100 410 168" stroke="{dark}" stroke-width="10" fill="none"/>'
                f'<path d="M196 196 Q300 128 404 196" stroke="{dark}" stroke-width="10" fill="none"/>'
                f'<path d="M210 130 Q300 70 390 130" stroke="{light}" stroke-width="8" fill="none"/>'
                f'<circle cx="300" cy="180" r="15" fill="{jewel}"/><circle cx="300" cy="180" r="6" fill="{tint(jewel, 0.6)}"/>')
    if kind == "topknot":
        return (f'<circle cx="300" cy="96" r="42" fill="{COLOURS["black"]}"/>'
                f'<path d="M212 190 Q300 120 388 190 Q300 168 212 190 Z" fill="{COLOURS["black"]}"/>'
                f'<rect x="262" y="132" width="76" height="12" rx="6" fill="{base}"/>')
    if kind == "hood":
        base = COLOURS[spec["outfit_colour"]]
        return (f'<path d="M170 400 Q150 120 300 78 Q450 120 430 400 Q410 250 300 214 Q190 250 170 400 Z" fill="{base}"/>'
                f'<path d="M190 390 Q175 140 300 98" stroke="{tint(base, 0.2)}" stroke-width="6" fill="none"/>')
    if kind == "hat":                     # a brimmed felt hat
        return (f'<path d="M222 196 Q222 70 300 78 Q378 70 378 196 Z" fill="{base}"/><path d="M262 82 Q300 106 338 82" stroke="{dark}" stroke-width="9" fill="none"/>'
                f'<path d="M224 166 Q300 188 376 166 L378 198 Q300 218 222 198 Z" fill="{dark}"/><ellipse cx="300" cy="202" rx="152" ry="26" fill="{base}"/>'
                f'<path d="M152 204 Q300 238 448 204" stroke="{dark}" stroke-width="7" fill="none"/>')
    if kind == "cap":                     # a flat cap
        return (f'<path d="M196 206 Q192 118 300 116 Q420 114 408 204 Q300 180 196 206 Z" fill="{base}"/>'
                f'<path d="M196 206 Q300 180 408 204 Q420 222 392 226 Q300 200 214 228 Q186 228 196 206 Z" fill="{dark}"/><circle cx="300" cy="124" r="10" fill="{dark}"/>')
    if kind == "military_cap":
        return (f'<path d="M188 168 Q196 92 300 90 Q404 92 412 168 Q300 140 188 168 Z" fill="{base}"/><path d="M200 168 Q300 142 400 168 L398 206 Q300 182 202 206 Z" fill="{dark}"/>'
                f'<path d="M202 204 Q300 180 398 204 Q392 244 300 236 Q208 244 202 204 Z" fill="{COLOURS["black"]}"/><circle cx="300" cy="160" r="18" fill="{COLOURS["gold"]}"/><circle cx="300" cy="160" r="7" fill="{base}"/>')
    if kind == "space_helmet":            # a clear bubble round the whole head, seated on the neck ring
        metal = COLOURS["silver"]
        return (f'<circle cx="300" cy="268" r="206" fill="#cfe6ff" opacity="0.13"/><circle cx="300" cy="268" r="206" fill="none" stroke="#eeece6" stroke-width="20"/>'
                f'<circle cx="300" cy="268" r="190" fill="none" stroke="{metal}" stroke-width="5" opacity="0.8"/>'
                f'<path d="M150 210 Q172 118 262 88" stroke="#ffffff" stroke-width="16" stroke-linecap="round" fill="none" opacity="0.65"/><path d="M146 262 Q146 246 148 236" stroke="#ffffff" stroke-width="14" stroke-linecap="round" fill="none" opacity="0.65"/>'
                f'<path d="M196 440 Q300 500 404 440 L414 470 Q300 530 186 470 Z" fill="{metal}"/>')
    return ""


def _hair_back(spec):
    """Long hair behind the head (drawn before the body, so the shoulders cover its ends)."""
    if spec["hair"] not in ("long", "braid") or spec["headgear"] in ("hood", "space_helmet"):
        return ""
    colour = HAIR_COLOURS[spec["hair_colour"]]
    return f'<path d="M300 132 C190 134 168 250 176 340 Q150 470 168 590 Q230 650 300 600 Q370 650 432 590 Q450 470 424 340 C432 250 410 134 300 132 Z" fill="{shade(colour, 0.12)}"/>'


def _hair_front(spec):
    """Locks that fall in front of the shoulders: two for long hair, a plait over one shoulder for a braid."""
    if spec["headgear"] in ("hood", "space_helmet"):
        return ""
    colour = HAIR_COLOURS[spec["hair_colour"]]
    if spec["hair"] == "long":
        return (f'<path d="M202 244 Q158 340 168 430 Q176 520 150 610 Q212 566 206 470 Q192 380 204 292 Z" fill="{colour}"/>'
                f'<path d="M398 244 Q442 340 432 430 Q424 520 450 610 Q388 566 394 470 Q408 380 396 292 Z" fill="{colour}"/>')
    if spec["hair"] == "braid":
        links = "".join(f'<ellipse cx="{398 + i * 7}" cy="{420 + i * 42}" rx="{27 - i * 2}" ry="30" fill="{colour}" stroke="{tint(colour, 0.2)}" stroke-width="3"/>' for i in range(6))
        return links + f'<circle cx="440" cy="668" r="14" fill="{COLOURS["gold"]}"/>'
    return ""


def _hair(spec):
    """Hair showing under bare or open headgear."""
    colour = HAIR_COLOURS[spec["hair_colour"]]
    if spec["hair"] != "bald" and spec["headgear"] in ("none", "crown", "helmet", "hat", "cap", "military_cap", "space_helmet"):
        bun = f'<circle cx="300" cy="126" r="46" fill="{colour}"/>' if spec["hair"] == "bun" and spec["headgear"] == "none" else ""
        return bun + f'<path d="M205 255 Q196 150 300 138 Q404 150 395 255 Q372 188 300 182 Q228 188 205 255 Z" fill="{colour}"/>'
    return ""


def _marking(spec):
    """War paint or a scar, drawn on the skin (under the eyes and mouth)."""
    kind, colour = spec["marking"], COLOURS[spec["marking_colour"]]
    if kind == "stripe":                  # a broad band from the crown of the head down over one eye to the jaw
        return f'<path d="M236 152 Q262 144 268 150 L276 262 L268 330 L252 408 Q238 398 232 388 L246 322 L238 262 Z" fill="{colour}" opacity="0.92"/>'
    if kind == "paint":                   # two lines across each cheek
        return (f'<path d="M214 326 L258 338 M216 344 L254 354 M386 326 L342 338 M384 344 L346 354" stroke="{colour}" stroke-width="9" stroke-linecap="round" fill="none"/>')
    if kind == "scar":
        return '<path d="M352 232 L330 336" stroke="#8a4a42" stroke-width="7" stroke-linecap="round" fill="none"/><path d="M338 258 l18 6 M332 288 l18 6" stroke="#8a4a42" stroke-width="4"/>'
    return ""


def _face(spec, skin):
    dark = shade(skin, 0.18)
    mood = spec["mood"]
    brow_colour = HAIR_COLOURS["white" if spec["age"] == "old" else spec["hair_colour"]]
    tilt = {"neutral": (0, 0), "stern": (6, 0), "sad": (-7, 2), "angry": (11, -2), "proud": (-2, -5), "calm": (-1, -2)}[mood]
    # brows: an inner end lower (angry/stern) or higher (sad)
    bl = f'<path d="M232 {268 + tilt[1]} Q258 {258 + tilt[1]} 282 {268 + tilt[1] + tilt[0]}" stroke="{brow_colour}" stroke-width="9" fill="none" stroke-linecap="round"/>'
    br = f'<path d="M368 {268 + tilt[1]} Q342 {258 + tilt[1]} 318 {268 + tilt[1] + tilt[0]}" stroke="{brow_colour}" stroke-width="9" fill="none" stroke-linecap="round"/>'
    lid = 8 if mood in ("calm", "sad") else 0
    eyes = ""
    for cx in (258, 342):
        eyes += (f'<path d="M{cx - 27} 292 Q{cx} {272 + lid} {cx + 27} 292 Q{cx} {308} {cx - 27} 292 Z" fill="#fbf7f0"/>'
                 f'<circle cx="{cx}" cy="291" r="10" fill="#1d1218"/><circle cx="{cx + 3}" cy="288" r="3" fill="#ffffff"/>'
                 f'<path d="M{cx - 29} 292 Q{cx} {270 + lid} {cx + 29} 292" stroke="#1d1218" stroke-width="5" fill="none"/>')
    mouth = {"neutral": "M270 372 Q300 378 330 372", "stern": "M272 374 L328 374", "sad": "M272 380 Q300 366 328 380",
             "angry": "M274 378 Q300 368 326 378", "proud": "M268 370 Q300 388 332 370", "calm": "M270 370 Q300 384 330 370"}[mood]
    nose = f'<path d="M300 292 Q288 340 276 346 Q300 358 324 346 Q312 340 300 292" fill="{dark}" opacity="0.55"/>'
    face = (f'<path d="M300 140 C200 140 188 250 204 322 C220 392 262 424 300 424 C338 424 380 392 396 322 C412 250 400 140 300 140 Z" fill="{skin}"/>'
            f'<path d="M300 140 C400 140 412 250 396 322 C380 392 338 424 300 424 Z" fill="{dark}" opacity="0.28"/>')
    ears = (f'<ellipse cx="198" cy="312" rx="19" ry="34" fill="{skin}"/><ellipse cx="402" cy="312" rx="19" ry="34" fill="{dark}"/>')
    lips = "#7a2f2f"
    if spec["figure"] == "woman":
        lips = "#b0344c"
        for cx, out_ in ((258, -1), (342, 1)):
            eyes += (f'<path d="M{cx + out_ * 27} 291 l{out_ * 13} -9 M{cx + out_ * 19} 283 l{out_ * 8} -12" stroke="#1d1218" stroke-width="4" stroke-linecap="round"/>')
    wrinkles = ""
    if spec["age"] == "old":
        wrinkles = f'<path d="M236 236 L264 232 M336 232 L364 236 M260 330 Q246 346 262 358 M340 330 Q354 346 338 358" stroke="{dark}" stroke-width="4" fill="none" opacity="0.7"/>'
    return ears, face + _marking(spec), bl + br + eyes + nose + f'<path d="{mouth}" stroke="{lips}" stroke-width="{10 if spec["figure"] == "woman" else 7}" fill="none" stroke-linecap="round"/>' + wrinkles


def _beard(spec):
    kind = spec["facial_hair"]
    colour = HAIR_COLOURS["white" if spec["age"] == "old" else spec["hair_colour"]]
    if kind == "none":
        return ""
    mous = (f'<path d="M300 352 Q270 336 236 352 Q262 372 300 360 Q338 372 364 352 Q330 336 300 352 Z" fill="{colour}"/>')
    if kind == "moustache":
        return mous
    if kind == "beard":
        return (f'<path d="M204 322 Q214 410 300 440 Q386 410 396 322 Q380 392 300 400 Q220 392 204 322 Z" fill="{colour}"/>' + mous)
    return (f'<path d="M204 322 Q200 440 262 560 Q300 600 338 560 Q400 440 396 322 Q380 392 300 404 Q220 392 204 322 Z" fill="{colour}"/>' + mous)


def _extras(spec):
    out = ""
    if "glasses" in spec["ornaments"]:
        frame = '#2a2430'
        out += (f'<circle cx="258" cy="292" r="38" fill="#cfe6ff" fill-opacity="0.12" stroke="{frame}" stroke-width="6"/><circle cx="342" cy="292" r="38" fill="#cfe6ff" fill-opacity="0.12" stroke="{frame}" stroke-width="6"/>'
                f'<path d="M296 288 Q300 280 304 288 M220 286 L200 300 M380 286 L400 300" stroke="{frame}" stroke-width="6" fill="none"/>')
    if "tilak" in spec["ornaments"]:
        out += '<path d="M300 200 L300 246" stroke="#f4efe6" stroke-width="8" stroke-linecap="round"/><circle cx="300" cy="258" r="6" fill="#d83a3a"/>'
    if "earrings" in spec["ornaments"]:
        gold = COLOURS["gold"]
        out += f'<circle cx="198" cy="352" r="11" fill="{gold}"/><circle cx="402" cy="352" r="11" fill="{gold}"/>'
    if "feather" in spec["ornaments"]:
        at = "translate(372 96) rotate(24)" if spec["headgear"] in ("crown", "helmet", "turban") else "translate(374 214) rotate(30) scale(0.7)"
        out += (f'<g transform="{at}"><path d="M0 0 Q-34 -60 0 -150 Q34 -60 0 0 Z" fill="#1f8a6a"/>'
                '<ellipse cx="0" cy="-96" rx="16" ry="26" fill="#2f6fd0"/><ellipse cx="0" cy="-96" rx="7" ry="12" fill="#f4d35e"/>'
                '<path d="M0 0 L0 -150" stroke="#145c47" stroke-width="3"/></g>')
    return out


def _weapon(spec):
    w = spec["weapon"]
    gold = COLOURS["gold"]
    if w == "bow":
        return (f'<path d="M96 120 Q-40 400 96 700" stroke="{COLOURS["brown"]}" stroke-width="16" fill="none" stroke-linecap="round"/>'
                f'<path d="M96 120 L96 700" stroke="#e8e0d0" stroke-width="3"/>')
    if w == "spear":
        return (f'<path d="M64 760 L64 90" stroke="{COLOURS["brown"]}" stroke-width="12"/><path d="M64 30 L88 110 L40 110 Z" fill="{COLOURS["silver"]}"/>'
                f'<rect x="52" y="112" width="24" height="16" fill="{gold}"/>')
    if w == "twin_blades":                 # a curved blade on each side, with its chain
        blade = lambda x, d: (f'<path d="M{x} 640 Q{x - d * 70} 430 {x - d * 6} 210 Q{x + d * 40} 330 {x + d * 30} 470 Q{x + d * 22} 560 {x + d * 22} 640 Z" fill="{COLOURS["silver"]}" stroke="{shade(COLOURS["silver"], 0.4)}" stroke-width="5"/>'
                              f'<rect x="{x - 18}" y="640" width="58" height="16" rx="6" fill="{gold}"/>' + "".join(f'<ellipse cx="{x + 10}" cy="{672 + i * 24}" rx="9" ry="15" fill="none" stroke="{COLOURS["silver"]}" stroke-width="5"/>' for i in range(4)))
        return blade(70, 1) + blade(520, -1)
    if w == "trident":
        return (f'<path d="M70 780 L70 190" stroke="{COLOURS["brown"]}" stroke-width="13"/><path d="M24 80 L24 170 Q24 196 70 196 Q116 196 116 170 L116 80 M70 190 L70 50" stroke="{gold}" stroke-width="13" fill="none"/>'
                + "".join(f'<path d="M{x - 14} {y + 26} L{x} {y} L{x + 14} {y + 26} Z" fill="{gold}"/>' for x, y in ((24, 56), (70, 24), (116, 56))))
    if w == "staff":
        return f'<path d="M60 790 L60 60" stroke="{COLOURS["brown"]}" stroke-width="14" stroke-linecap="round"/><circle cx="60" cy="52" r="22" fill="none" stroke="{gold}" stroke-width="8"/>'
    if w == "sword":
        return (f'<path d="M520 720 L520 200" stroke="{COLOURS["silver"]}" stroke-width="22"/><path d="M510 200 L520 150 L530 200 Z" fill="{COLOURS["silver"]}"/>'
                f'<rect x="480" y="720" width="80" height="14" fill="{gold}"/>')
    return ""


def _halo(spec):
    if "halo" not in spec["ornaments"]:
        return ""
    gold = COLOURS["gold"]
    rays = "".join(f'<path d="M300 250 L{300 + 250 * math.cos(a):.0f} {250 + 250 * math.sin(a):.0f}" stroke="{gold}" stroke-width="10" stroke-linecap="round" opacity="0.8"/>'
                   for a in [i * math.pi / 8 for i in range(16)])
    return (f'<g opacity="0.95">{rays}<circle cx="300" cy="250" r="168" fill="url(#halo)"/></g>'
            f'<defs><radialGradient id="halo"><stop offset="0.55" stop-color="{tint(gold, 0.4)}" stop-opacity="0.95"/><stop offset="1" stop-color="{gold}" stop-opacity="0.15"/></radialGradient></defs>')


def character_svg(spec):
    """The bust as an SVG document (viewBox 0 0 600 800, transparent background) for a character spec (`clean_spec`)."""
    spec = clean_spec(spec)
    skin = _skin(spec)
    trim = COLOURS[spec["trim_colour"]]
    if spec["species"] != "human":
        behind, neck, head = story_beasts.parts(spec)
        clothes = story_beasts.coat_body(spec) if spec["outfit"] == "none" else _body(spec, trim)
        body = (_halo(spec) + story_beasts.wings(spec) + behind + _weapon(spec) + neck + clothes + story_beasts.horns(spec) + head + _extras(dict(spec, ornaments=[o for o in spec["ornaments"] if o != "earrings"]))
                + _headgear(spec, skin))
        return _document(spec, body)
    ears, face, features = _face(spec, skin)
    neck = f'<path d="M258 400 L258 480 Q300 520 342 480 L342 400 Z" fill="{shade(skin, 0.22)}"/>'
    snakes = spec["hair"] == "snakes" and spec["headgear"] not in ("hood", "space_helmet")
    monster = ((story_beasts.human_glow() if "glowing_eyes" in spec["ornaments"] else "") + (story_beasts.human_fangs() if "fangs" in spec["ornaments"] else ""))
    body = (_halo(spec) + story_beasts.wings(spec) + _weapon(spec) + _hair_back(spec) + (story_beasts.snake_hair() if snakes else "") + neck + _body(spec, trim)
            + story_beasts.horns(spec) + ears + face + _hair(spec) + features + monster + _beard(spec) + _extras(spec) + _headgear(spec, skin) + _hair_front(spec))
    return _document(spec, body)


def is_beast(spec):
    """Does this spec show something other than an ordinary person: an animal, or monster features?"""
    return bool(spec.get("creature") or spec.get("species", "human") != "human" or spec.get("hair") == "snakes"
                or any(f in (spec.get("ornaments") or []) for f in story_beasts.FEATURES))


def _document(spec, body):
    if spec["figure"] == "child":                      # smaller, still standing on the bottom edge
        body = f'<g transform="translate(60 160) scale(0.8)">{body}</g>'

    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" width="600" height="800">{body}</svg>'


# ---------------------------------------------------------------- backdrops

SKY_STOPS = {
    "sunset": ("#140c2e", "#3b1d5e", "#b8426a", "#f0743a", "#ffc15a"),
    "dusk": ("#0c0a24", "#241a4e", "#5c3a7e", "#a85a82", "#e8967a"),
    "night": ("#04040f", "#0a0e2a", "#14204a", "#1c2d5c", "#2a3f72"),
    "dawn": ("#3a4a7a", "#8a7aa8", "#e0a0a0", "#f6c88a", "#fff0c0"),
    "fire": ("#120404", "#3a0808", "#8a1c10", "#d6481c", "#ffa030"),
    "storm": ("#0a0c12", "#1c2230", "#2f3948", "#445060", "#66707c"),
    "rays": ("#050404", "#0d0906", "#1a120a", "#2a1c0c", "#3a2810"),
    "day": ("#3a78c8", "#5a96d8", "#86b6e6", "#b8d6f0", "#eaf2f6"),
}
GROUND_COLOUR = {"sunset": "#10081a", "dusk": "#0b0716", "night": "#03030a", "dawn": "#241830", "fire": "#080202", "storm": "#06080c", "rays": "#050302", "day": "#1c3a2a"}


def _stars(w, h, horizon, rng, count):
    return "".join(f'<circle cx="{rng.uniform(0, w):.0f}" cy="{rng.uniform(0, horizon * 0.8):.0f}" r="{rng.uniform(0.8, 2.6):.1f}" fill="#ffffff" opacity="{rng.uniform(0.25, 0.9):.2f}"/>'
                   for _ in range(count))


def _ground(kind, w, h, horizon, colour, rng):
    y = horizon
    if kind == "none":
        return ""
    if kind == "battlefield":
        out = f'<path d="M0 {y + 30} Q{w * 0.25} {y - 10} {w * 0.5} {y + 20} T{w} {y + 10} L{w} {h} L0 {h} Z" fill="{colour}"/>'
        for i in range(26):
            x = rng.uniform(0, w)
            top = y - rng.uniform(40, 150)
            out += f'<path d="M{x:.0f} {y + 24} L{x:.0f} {top:.0f}" stroke="{colour}" stroke-width="3"/>'
            if i % 3 == 0:
                out += f'<path d="M{x:.0f} {top:.0f} L{x + 34:.0f} {top + 12:.0f} L{x:.0f} {top + 26:.0f} Z" fill="{colour}"/>'
            elif i % 3 == 1:
                out += f'<path d="M{x - 6:.0f} {top + 14:.0f} L{x:.0f} {top - 10:.0f} L{x + 6:.0f} {top + 14:.0f} Z" fill="{colour}"/>'
        return out
    if kind == "hills":
        return (f'<path d="M0 {y - 60} Q{w * 0.2} {y - 160} {w * 0.45} {y - 40} T{w} {y - 90} L{w} {h} L0 {h} Z" fill="{shade(colour, 0.0)}" opacity="0.8"/>'
                f'<path d="M0 {y + 10} Q{w * 0.3} {y - 80} {w * 0.6} {y + 10} T{w} {y - 20} L{w} {h} L0 {h} Z" fill="{colour}"/>')
    if kind == "city":
        out = f'<rect x="0" y="{y + 20}" width="{w}" height="{h - y}" fill="{colour}"/>'
        x = 0
        while x < w:
            bw = rng.uniform(50, 120)
            bh = rng.uniform(50, 190)
            out += f'<rect x="{x:.0f}" y="{y + 20 - bh:.0f}" width="{bw:.0f}" height="{bh:.0f}" fill="{colour}"/>'
            if rng.random() < 0.45:
                out += f'<path d="M{x + 6:.0f} {y + 20 - bh:.0f} Q{x + bw / 2:.0f} {y + 20 - bh - bw * 0.7:.0f} {x + bw - 6:.0f} {y + 20 - bh:.0f} Z" fill="{colour}"/>'
                out += f'<path d="M{x + bw / 2:.0f} {y + 20 - bh - bw * 0.6:.0f} L{x + bw / 2:.0f} {y + 20 - bh - bw * 0.95:.0f}" stroke="{colour}" stroke-width="3"/>'
            x += bw - 4
        return out
    if kind == "trees":
        out = f'<path d="M0 {y + 20} Q{w * 0.5} {y - 20} {w} {y + 20} L{w} {h} L0 {h} Z" fill="{colour}"/>'
        for _ in range(9):
            x = rng.uniform(0, w)
            top = y - rng.uniform(120, 300)
            out += f'<path d="M{x:.0f} {y + 20} Q{x + rng.uniform(-30, 30):.0f} {(y + top) / 2:.0f} {x + rng.uniform(-20, 20):.0f} {top:.0f}" stroke="{colour}" stroke-width="9" fill="none"/>'
            for a in (-2.6, -2.0, -1.2, -0.5):
                out += f'<path d="M{x:.0f} {top:.0f} q{math.cos(a) * 70:.0f} {math.sin(a) * 40:.0f} {math.cos(a) * 110:.0f} {math.sin(a) * 10 + 36:.0f}" stroke="{colour}" stroke-width="7" fill="none"/>'
        return out
    if kind == "sea":
        out = f'<rect x="0" y="{y}" width="{w}" height="{h - y}" fill="{shade(colour, 0.0)}"/>'
        for i in range(14):
            yy = y + 20 + i * (h - y) / 14
            out += f'<path d="M{rng.uniform(0, w * 0.4):.0f} {yy:.0f} h{rng.uniform(80, 300):.0f}" stroke="#ffffff" stroke-width="2" opacity="0.13"/>'
        return out
    return ""


def backdrop_svg(sky="sunset", ground="battlefield", w=1080, h=1920, seed=3):
    """A full-frame backdrop as an SVG document: a sky with its light and a ground silhouette."""
    sky = sky if sky in SKIES else "sunset"
    ground = ground if ground in GROUNDS else "none"
    rng = random.Random(seed)
    stops = SKY_STOPS[sky]
    horizon = h * (0.68 if h > w else 0.72)
    grad = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in zip((0, 0.3, 0.55, 0.8, 1), stops))
    body = f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">{grad}</linearGradient>' \
           f'<radialGradient id="glow" cx="0.5" cy="1" r="0.9"><stop offset="0" stop-color="{stops[4]}" stop-opacity="0.95"/><stop offset="0.5" stop-color="{stops[3]}" stop-opacity="0.35"/><stop offset="1" stop-color="{stops[3]}" stop-opacity="0"/></radialGradient>' \
           f'<radialGradient id="vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.6"/></radialGradient></defs>'
    body += f'<rect width="{w}" height="{h}" fill="url(#sky)"/>'
    if sky in ("sunset", "dusk", "night", "fire", "storm"):
        body += _stars(w, h, horizon, rng, 70 if sky in ("night", "dusk") else 26)
    if sky == "rays":
        cx, cy = w / 2, h * 0.46
        rays = ""
        n = 28
        for i in range(n):
            a0 = i * 2 * math.pi / n
            a1 = a0 + math.pi / n * 0.8
            r = max(w, h)
            rays += f'<path d="M{cx:.0f} {cy:.0f} L{cx + r * math.cos(a0):.0f} {cy + r * math.sin(a0):.0f} L{cx + r * math.cos(a1):.0f} {cy + r * math.sin(a1):.0f} Z" fill="#f2c15a" opacity="0.13"/>'
        body += rays + f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{w * 0.5:.0f}" fill="url(#glow)" opacity="0.4"/>'
    else:
        sun_y = horizon + 6
        sun_x = w * (0.5 if h <= w else 0.8)             # to one side in a tall frame: in the middle it showed as a disc under the character's chin
        body += f'<ellipse cx="{w / 2:.0f}" cy="{sun_y:.0f}" rx="{w * 0.9:.0f}" ry="{h * 0.34:.0f}" fill="url(#glow)"/>'
        if sky in ("sunset", "dawn", "fire", "day"):
            body += f'<circle cx="{sun_x:.0f}" cy="{sun_y - 20:.0f}" r="{w * 0.12:.0f}" fill="{tint(stops[4], 0.55)}" opacity="0.92"/>'
        if sky == "night":
            body += f'<circle cx="{w * 0.72:.0f}" cy="{h * 0.32:.0f}" r="{w * 0.065:.0f}" fill="#f1ecd8" opacity="0.92"/>'
        if sky in ("storm", "day"):
            for _ in range(7):
                cx, cy = rng.uniform(0, w), rng.uniform(h * 0.08, horizon * 0.8)
                body += f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rng.uniform(140, 320):.0f}" ry="{rng.uniform(30, 70):.0f}" fill="#ffffff" opacity="{0.07 if sky == "storm" else 0.35}"/>'
    body += _ground(ground, w, h, horizon, GROUND_COLOUR[sky], rng)
    body += f'<rect width="{w}" height="{h}" fill="url(#vig)"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">{body}</svg>'


# ---------------------------------------------------------------- emblems (600 x 600): the object of a title card

EMBLEMS = ("wheel", "spear", "arrow", "bow", "sun", "crown", "sword", "fire", "lightning", "box", "skull", "mountain", "wings")


def emblem_svg(kind, colour="#f0c15a"):
    """A gold object for a title card (the chariot wheel, the spear, ...) as an SVG document (viewBox 0 0 600 600); '' for an unknown kind."""
    gold, dark, light = colour, shade(colour, 0.38), tint(colour, 0.4)
    body = ""
    if kind == "wheel":
        spokes = "".join(f'<path d="M300 300 L{300 + 214 * math.cos(a):.0f} {300 + 214 * math.sin(a):.0f}" stroke="{gold}" stroke-width="14" stroke-linecap="round"/>'
                         for a in [i * math.pi / 8 for i in range(16)])
        studs = "".join(f'<circle cx="{300 + 250 * math.cos(a):.0f}" cy="{300 + 250 * math.sin(a):.0f}" r="9" fill="{light}"/>' for a in [i * math.pi / 12 for i in range(24)])
        body = (f'<circle cx="300" cy="300" r="250" fill="none" stroke="{dark}" stroke-width="40"/><circle cx="300" cy="300" r="250" fill="none" stroke="{gold}" stroke-width="26"/>'
                f'<circle cx="300" cy="300" r="196" fill="none" stroke="{gold}" stroke-width="10"/>{spokes}{studs}'
                f'<circle cx="300" cy="300" r="52" fill="{gold}"/><circle cx="300" cy="300" r="26" fill="{dark}"/>')
    elif kind == "spear":
        body = (f'<path d="M300 20 Q352 150 330 250 L270 250 Q248 150 300 20 Z" fill="{light}"/><path d="M300 20 Q326 150 318 250 L300 250 Z" fill="{gold}"/>'
                f'<rect x="262" y="250" width="76" height="22" rx="8" fill="{gold}"/><rect x="287" y="272" width="26" height="300" fill="{dark}"/>'
                f'<path d="M300 300 L300 560" stroke="{gold}" stroke-width="6"/><path d="M270 560 L300 600 L330 560 Z" fill="{gold}"/>'
                f'<path d="M262 300 L240 380 M338 300 L360 380" stroke="#c0392b" stroke-width="10" stroke-linecap="round"/>')
    elif kind == "arrow":
        body = (f'<g transform="rotate(-38 300 300)"><rect x="40" y="288" width="440" height="24" rx="8" fill="{dark}"/><rect x="40" y="294" width="440" height="8" fill="{gold}"/>'
                f'<path d="M560 300 L470 252 L488 300 L470 348 Z" fill="{light}"/><path d="M40 300 L10 262 L90 270 L110 300 L90 330 L10 338 Z" fill="#c0392b"/></g>')
    elif kind == "bow":
        body = (f'<path d="M180 40 Q-40 300 180 560" fill="none" stroke="{dark}" stroke-width="40" stroke-linecap="round"/><path d="M180 40 Q-20 300 180 560" fill="none" stroke="{gold}" stroke-width="22" stroke-linecap="round"/>'
                f'<path d="M180 40 L180 560" stroke="#f4efe6" stroke-width="5"/><g><rect x="150" y="288" width="400" height="22" rx="8" fill="{dark}"/>'
                f'<path d="M580 299 L520 262 L534 299 L520 336 Z" fill="{light}"/></g>')
    elif kind == "sun":
        rays = "".join(f'<path d="M300 300 L{300 + 280 * math.cos(a):.0f} {300 + 280 * math.sin(a):.0f}" stroke="{gold}" stroke-width="{16 if i % 2 else 26}" stroke-linecap="round"/>'
                       for i, a in enumerate([i * math.pi / 10 for i in range(20)]))
        body = f'{rays}<circle cx="300" cy="300" r="150" fill="{dark}"/><circle cx="300" cy="300" r="136" fill="{gold}"/><circle cx="260" cy="262" r="40" fill="{light}" opacity="0.7"/>'
    elif kind == "crown":
        body = (f'<path d="M80 420 L40 160 L180 280 L300 90 L420 280 L560 160 L520 420 Z" fill="{gold}"/><path d="M80 420 L520 420 L520 480 L80 480 Z" fill="{dark}"/>'
                f'<circle cx="300" cy="360" r="38" fill="#d83a3a"/><circle cx="190" cy="372" r="22" fill="#2f8f8f"/><circle cx="410" cy="372" r="22" fill="#2f8f8f"/>'
                f'<circle cx="40" cy="160" r="22" fill="#d83a3a"/><circle cx="560" cy="160" r="22" fill="#d83a3a"/><circle cx="300" cy="90" r="24" fill="#d83a3a"/>')
    elif kind == "sword":
        body = (f'<path d="M300 20 L336 120 L336 380 L264 380 L264 120 Z" fill="{tint(COLOURS["silver"], 0.2)}"/><path d="M300 20 L336 120 L336 380 L300 380 Z" fill="{COLOURS["silver"]}"/>'
                f'<path d="M300 40 L300 380" stroke="#8d95a3" stroke-width="5"/><rect x="190" y="380" width="220" height="34" rx="14" fill="{gold}"/>'
                f'<rect x="282" y="414" width="36" height="120" rx="8" fill="{dark}"/><circle cx="300" cy="556" r="30" fill="{gold}"/><circle cx="300" cy="556" r="12" fill="#d83a3a"/>')
    elif kind == "fire":
        body = (f'<path d="M300 30 Q420 170 400 300 Q460 260 450 200 Q560 320 500 440 Q460 560 300 570 Q140 560 100 440 Q60 330 170 220 Q170 280 220 300 Q190 170 300 30 Z" fill="#e8501c"/>'
                f'<path d="M300 200 Q380 300 360 380 Q400 360 400 330 Q450 420 400 480 Q360 540 300 540 Q240 540 205 480 Q170 410 230 330 Q240 380 270 380 Q250 290 300 200 Z" fill="#ffa030"/>'
                f'<path d="M300 360 Q340 420 330 470 Q316 510 300 510 Q270 500 266 460 Q266 410 300 360 Z" fill="#ffe08a"/>')
    elif kind == "lightning":
        body = (f'<path d="M370 20 L150 330 L275 330 L205 580 L460 230 L320 230 L420 20 Z" fill="{gold}" stroke="{dark}" stroke-width="14" stroke-linejoin="round"/>'
                f'<path d="M366 62 L206 300 L300 300 Z" fill="{light}" opacity="0.8"/>')
    elif kind == "box":                    # a closed chest with light escaping under its lid
        body = (f'<path d="M90 250 Q300 110 510 250 L510 292 L90 292 Z" fill="{gold}" stroke="{dark}" stroke-width="12"/><rect x="90" y="316" width="420" height="220" rx="14" fill="{dark}"/>'
                f'<rect x="90" y="292" width="420" height="24" fill="{light}"/><rect x="108" y="334" width="384" height="184" rx="8" fill="none" stroke="{gold}" stroke-width="10"/>'
                f'<circle cx="300" cy="426" r="44" fill="{gold}"/><circle cx="300" cy="416" r="12" fill="{dark}"/><path d="M293 420 L286 458 L314 458 L307 420 Z" fill="{dark}"/>'
                + "".join(f'<path d="M{x} 286 L{x + dx} 180" stroke="{light}" stroke-width="9" stroke-linecap="round" opacity="0.75"/>' for x, dx in ((130, -50), (210, -22), (390, 22), (470, 50))))
    elif kind == "skull":
        body = (f'<path d="M300 60 C160 60 100 160 108 270 C112 340 150 372 178 392 L186 470 Q200 500 232 490 L368 490 Q400 500 414 470 L422 392 C450 372 488 340 492 270 C500 160 440 60 300 60 Z" fill="{light}" stroke="{dark}" stroke-width="12"/>'
                f'<ellipse cx="222" cy="288" rx="52" ry="58" fill="#241208"/><ellipse cx="378" cy="288" rx="52" ry="58" fill="#241208"/><path d="M300 336 L270 396 L330 396 Z" fill="#241208"/>'
                + "".join(f'<path d="M{x} 438 L{x} 492" stroke="{dark}" stroke-width="10"/>' for x in (244, 281, 319, 356)))
    elif kind == "mountain":
        body = (f'<path d="M20 520 L230 130 L330 290 L390 200 L580 520 Z" fill="{dark}"/><path d="M230 130 L330 290 L300 520 L20 520 Z" fill="{gold}"/>'
                f'<path d="M230 130 L182 220 L212 206 L236 236 L262 204 L282 214 Z" fill="{light}"/><path d="M390 200 L352 258 L378 250 L398 276 L424 256 Z" fill="{light}"/>')
    elif kind == "wings":
        def wing(d):
            return "".join(f'<path d="M{300 + d * 18} {250 + i * 34} Q{300 + d * (150 + i * 6)} {120 + i * 58} {300 + d * (272 - i * 24)} {150 + i * 76} Q{300 + d * (160 - i * 8)} {250 + i * 56} {300 + d * 18} {300 + i * 30} Z" '
                           f'fill="{light if i % 2 else gold}" stroke="{dark}" stroke-width="7"/>' for i in range(5))
        body = wing(-1) + wing(1) + f'<ellipse cx="300" cy="320" rx="22" ry="96" fill="{dark}"/>'
    if not body:
        return ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" width="600" height="600">{body}</svg>'
