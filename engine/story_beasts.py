"""Animal heads and monster features for the story look, drawn by code like the people (600 x 800, the head centred near 300, 290).

A character is an animal when its spec's "species" is not "human"; it may wear any outfit (a monkey in saffron, a wolf in a coat), and with no
clothes of its own (outfit "none") it shows its coat. Monster features ("snake" hair, horns, fangs, glowing eyes, wings) go on a person or an animal.
Built for any story: an animal is a head shape, a kind of ears, a muzzle or beak, and what sets it apart."""

COATS = {"brown": "#8a5a34", "tan": "#c99a63", "grey": "#8f939c", "white": "#efeae0", "black": "#2e2933", "orange": "#d9782f", "yellow": "#ecc548",
         "green": "#5f9a52", "red": "#b24a32", "pink": "#e6a3a0"}
# head: (half width, half height); ears; face front; the rest
ANIMALS = {
    "cat": {"head": (112, 104), "ears": "pointed", "front": "muzzle", "coat": "orange", "extra": ("whiskers",)},
    "dog": {"head": (106, 112), "ears": "floppy", "front": "muzzle", "coat": "tan", "extra": ()},
    "wolf": {"head": (102, 110), "ears": "pointed", "front": "long_muzzle", "coat": "grey", "extra": ("cheek_ruff",)},
    "fox": {"head": (102, 102), "ears": "tall_pointed", "front": "long_muzzle", "coat": "orange", "extra": ("cheek_ruff", "white_cheeks")},
    "hare": {"head": (92, 106), "ears": "long", "front": "muzzle", "coat": "tan", "extra": ("whiskers", "teeth")},
    "mouse": {"head": (98, 98), "ears": "big_round", "front": "muzzle", "coat": "grey", "extra": ("whiskers", "teeth")},
    "bear": {"head": (122, 112), "ears": "round", "front": "muzzle", "coat": "brown", "extra": ()},
    "lion": {"head": (106, 108), "ears": "round", "front": "muzzle", "coat": "yellow", "extra": ("mane", "whiskers")},
    "monkey": {"head": (104, 112), "ears": "side", "front": "ape", "coat": "brown", "extra": ()},
    "pig": {"head": (114, 106), "ears": "pointed", "front": "snout", "coat": "pink", "extra": ()},
    "sheep": {"head": (90, 112), "ears": "side_leaf", "front": "muzzle", "coat": "white", "extra": ("wool",)},
    "cow": {"head": (108, 114), "ears": "side_leaf", "front": "broad_muzzle", "coat": "white", "extra": ("small_horns", "patch")},
    "horse": {"head": (84, 134), "ears": "pointed", "front": "broad_muzzle", "coat": "brown", "extra": ("forelock",)},
    "elephant": {"head": (110, 112), "ears": "fan", "front": "trunk", "coat": "grey", "extra": ("tusks",)},
    "duck": {"head": (100, 100), "ears": "none", "front": "bill", "coat": "yellow", "extra": ("tuft",)},
    "swan": {"head": (88, 96), "ears": "none", "front": "bill", "coat": "white", "extra": ("mask", "long_neck")},
    "bird": {"head": (100, 100), "ears": "none", "front": "beak", "coat": "red", "extra": ("crest",)},
    "owl": {"head": (122, 112), "ears": "tufts", "front": "beak", "coat": "brown", "extra": ("eye_discs",)},
    "frog": {"head": (126, 90), "ears": "none", "front": "wide_mouth", "coat": "green", "extra": ("top_eyes",)},
    "tortoise": {"head": (92, 100), "ears": "none", "front": "flat", "coat": "green", "extra": ("shell",)},
    "snake": {"head": (92, 96), "ears": "none", "front": "flat", "coat": "green", "extra": ("hood_flaps", "tongue")},
}
SPECIES = ("human", *ANIMALS)
FEATURES = ("horns", "fangs", "glowing_eyes", "spread_wings")          # monster features, listed under a spec's "ornaments"
INK = "#1d1218"


def _mix(a, b, t):
    pa, pb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def _dark(c, k=0.28):
    return _mix(c, "#000000", k)


def _light(c, k=0.45):
    return _mix(c, "#ffffff", k)


def coat_colour(spec):
    species = ANIMALS[spec["species"]]
    return COATS[spec.get("coat_colour") or species["coat"]]


def _pair(make):
    """A shape and its mirror image about the head's middle line."""
    return make() + f'<g transform="translate(600 0) scale(-1 1)">{make()}</g>'


def _ears(kind, coat, w, h):
    inner, edge, x, top = _light(coat, 0.35), _dark(coat, 0.2), 300 - w, 290 - h
    if kind == "pointed":
        return _pair(lambda: f'<path d="M{x + 14} {top + 62} L{x + 8} {top - 48} L{x + 92} {top + 14} Z" fill="{coat}"/><path d="M{x + 28} {top + 40} L{x + 24} {top - 18} L{x + 72} {top + 18} Z" fill="{inner}"/>')
    if kind == "tall_pointed":
        return _pair(lambda: f'<path d="M{x + 8} {top + 70} L{x - 6} {top - 90} L{x + 96} {top + 12} Z" fill="{coat}"/><path d="M{x + 24} {top + 44} L{x + 12} {top - 52} L{x + 74} {top + 16} Z" fill="{INK}" opacity="0.55"/>')
    if kind == "floppy":
        return _pair(lambda: f'<path d="M{x + 34} {top + 26} Q{x - 64} {top + 40} {x - 40} {top + 178} Q{x - 8} {top + 212} {x + 22} {top + 168} Q{x + 40} {top + 96} {x + 34} {top + 26} Z" fill="{edge}"/>')
    if kind == "long":
        return _pair(lambda: f'<ellipse cx="{x + 52}" cy="{top - 62}" rx="30" ry="112" fill="{coat}" transform="rotate(-11 {x + 52} {top + 30})"/><ellipse cx="{x + 52}" cy="{top - 62}" rx="15" ry="86" fill="{inner}" transform="rotate(-11 {x + 52} {top + 30})"/>')
    if kind in ("round", "big_round"):
        r = 62 if kind == "big_round" else 38
        return _pair(lambda: f'<circle cx="{x + 28}" cy="{top + 24}" r="{r}" fill="{coat}"/><circle cx="{x + 28}" cy="{top + 24}" r="{r * 0.6:.0f}" fill="{inner}"/>')
    if kind == "side":
        return _pair(lambda: f'<circle cx="{x - 8}" cy="290" r="44" fill="{coat}"/><circle cx="{x - 8}" cy="290" r="27" fill="{_light(coat, 0.5)}"/>')
    if kind == "side_leaf":
        return _pair(lambda: f'<path d="M{x + 16} 244 Q{x - 82} 236 {x - 72} 282 Q{x - 30} 312 {x + 18} 280 Z" fill="{edge}"/>')
    if kind == "fan":
        return _pair(lambda: f'<path d="M{x + 30} {top + 30} Q{x - 150} {top - 10} {x - 132} {top + 140} Q{x - 100} {top + 232} {x + 24} {top + 186} Z" fill="{edge}"/><path d="M{x + 6} {top + 52} Q{x - 108} {top + 34} {x - 96} {top + 132} Q{x - 76} {top + 190} {x + 6} {top + 160} Z" fill="{inner}" opacity="0.55"/>')
    if kind == "tufts":
        return _pair(lambda: f'<path d="M{x + 26} {top + 52} L{x + 2} {top - 34} L{x + 92} {top + 16} Z" fill="{edge}"/>')
    return ""


def _eyes(spec, y=262, apart=44, r=17):
    glow = "glowing_eyes" in spec["ornaments"]
    angry = spec["mood"] in ("angry", "stern")
    out = ""
    for cx in (300 - apart, 300 + apart):
        if glow:
            out += f'<circle cx="{cx}" cy="{y}" r="{r + 12}" fill="#ffd84a" opacity="0.35"/><circle cx="{cx}" cy="{y}" r="{r}" fill="#ffd84a"/><ellipse cx="{cx}" cy="{y}" rx="{r * 0.24:.0f}" ry="{r * 0.8:.0f}" fill="#7a1d12"/>'
        else:
            out += f'<circle cx="{cx}" cy="{y}" r="{r}" fill="#fbf7f0"/><circle cx="{cx}" cy="{y + 2}" r="{r * 0.62:.0f}" fill="{INK}"/><circle cx="{cx + 4}" cy="{y - 4}" r="{r * 0.2:.0f}" fill="#ffffff"/>'
    if angry or spec["mood"] == "sad":
        tilt = 15 if angry else -12
        for cx, side in ((300 - apart, 1), (300 + apart, -1)):
            out += f'<path d="M{cx - side * (r + 8)} {y - r - 12} L{cx + side * (r + 8)} {y - r - 12 + tilt}" stroke="{INK}" stroke-width="9" stroke-linecap="round"/>'
    return out


def _mouth(spec, y, width=34):
    bend = {"sad": -14, "angry": -9, "stern": 0, "calm": 12, "proud": 16, "neutral": 7}[spec["mood"]]
    return f'<path d="M{300 - width} {y} Q300 {y + bend} {300 + width} {y}" stroke="{INK}" stroke-width="6" fill="none" stroke-linecap="round"/>'


def _fangs(y, apart=24):
    return "".join(f'<path d="M{x - 9} {y} L{x} {y + 34} L{x + 9} {y} Z" fill="#fbf7f0" stroke="{INK}" stroke-width="2"/>' for x in (300 - apart, 300 + apart))


def _front(spec, kind, coat, w, h):
    pale, dark = _light(coat, 0.5), _dark(coat, 0.35)
    if kind in ("muzzle", "broad_muzzle"):
        cy, rx, ry = (352, 56, 42) if kind == "muzzle" else (290 + h - 34, 68, 46)
        nose = (f'<path d="M278 {cy - 22} Q300 {cy - 34} 322 {cy - 22} Q312 {cy + 2} 300 {cy + 2} Q288 {cy + 2} 278 {cy - 22} Z" fill="{INK}"/>' if kind == "muzzle"
                else f'<ellipse cx="274" cy="{cy - 8}" rx="10" ry="15" fill="{INK}" opacity="0.8"/><ellipse cx="326" cy="{cy - 8}" rx="10" ry="15" fill="{INK}" opacity="0.8"/>')
        return _eyes(spec) + f'<ellipse cx="300" cy="{cy}" rx="{rx}" ry="{ry}" fill="{pale}"/>' + nose + _mouth(spec, cy + 20, 28), cy + 22
    if kind == "long_muzzle":
        return (_eyes(spec, 256) + f'<path d="M250 296 Q300 270 350 296 Q344 392 300 414 Q256 392 250 296 Z" fill="{pale}"/>'
                f'<ellipse cx="300" cy="374" rx="27" ry="18" fill="{INK}"/>' + _mouth(spec, 400, 24), 398)
    if kind == "snout":
        return (_eyes(spec) + f'<ellipse cx="300" cy="346" rx="52" ry="38" fill="{_light(coat, 0.22)}" stroke="{dark}" stroke-width="5"/>'
                f'<ellipse cx="281" cy="346" rx="9" ry="15" fill="{dark}"/><ellipse cx="319" cy="346" rx="9" ry="15" fill="{dark}"/>' + _mouth(spec, 398), 398)
    if kind == "ape":
        return (f'<path d="M300 232 Q262 196 236 232 Q214 272 240 304 Q214 352 250 392 Q300 428 350 392 Q386 352 360 304 Q386 272 364 232 Q338 196 300 232 Z" fill="{_light(coat, 0.55)}"/>'
                + _eyes(spec, 266, 38, 15) + f'<ellipse cx="287" cy="322" rx="7" ry="5" fill="{INK}"/><ellipse cx="313" cy="322" rx="7" ry="5" fill="{INK}"/>' + _mouth(spec, 362, 42), 364)
    if kind == "trunk":
        return (_eyes(spec, 258, 54, 14) + f'<path d="M274 288 Q268 392 290 452 Q308 498 346 480 Q362 466 344 458 Q326 466 318 442 Q304 390 326 288 Z" fill="{coat}" stroke="{dark}" stroke-width="5"/>'
                + "".join(f'<path d="M278 {y} Q300 {y + 10} 320 {y}" stroke="{dark}" stroke-width="4" fill="none" opacity="0.6"/>' for y in (330, 364, 398)), 370)
    if kind == "bill":
        beak = "#e8862b"
        return (_eyes(spec, 258, 40, 16) + f'<path d="M244 316 Q300 290 356 316 Q386 362 348 372 Q300 386 252 372 Q214 362 244 316 Z" fill="{beak}"/>'
                f'<path d="M246 346 Q300 364 354 346" stroke="{_dark(beak, 0.35)}" stroke-width="5" fill="none"/><circle cx="282" cy="318" r="5" fill="{_dark(beak, 0.4)}"/><circle cx="318" cy="318" r="5" fill="{_dark(beak, 0.4)}"/>', 372)
    if kind == "beak":
        beak = "#e9a62f"
        return _eyes(spec, 262, 46, 22) + f'<path d="M264 306 Q300 290 336 306 L300 380 Z" fill="{beak}"/><path d="M276 326 L324 326" stroke="{_dark(beak, 0.35)}" stroke-width="4"/>', 372
    if kind == "wide_mouth":
        return _mouth(spec, 330, 86) + f'<circle cx="276" cy="300" r="5" fill="{INK}"/><circle cx="324" cy="300" r="5" fill="{INK}"/>', 336
    return _eyes(spec, 268, 40, 16) + f'<circle cx="286" cy="316" r="5" fill="{INK}"/><circle cx="314" cy="316" r="5" fill="{INK}"/>' + _mouth(spec, 348, 40), 350


def _behind(extras, coat, w, h):
    out = ""
    if "mane" in extras:
        mane = _dark(coat, 0.42)
        out += "".join(f'<circle cx="{300 + x}" cy="{290 + y}" r="62" fill="{mane}"/>' for x, y in
                       ((-128, -50), (-86, -112), (0, -136), (86, -112), (128, -50), (140, 30), (-140, 30), (116, 100), (-116, 100), (60, 134), (-60, 134)))
    if "shell" in extras:
        shell = "#8a6b34"
        out += (f'<ellipse cx="300" cy="590" rx="296" ry="236" fill="{shell}" stroke="{_dark(shell, 0.35)}" stroke-width="12"/>'
                + "".join(f'<path d="M{x} {y} l46 -26 l46 26 l0 52 l-46 26 l-46 -26 Z" fill="{_light(shell, 0.22)}" stroke="{_dark(shell, 0.35)}" stroke-width="6"/>'
                          for x, y in ((62, 438), (160, 372), (348, 372), (446, 438), (26, 566), (482, 566))))
    if "hood_flaps" in extras:
        out += f'<path d="M300 150 Q92 170 128 380 Q170 500 300 520 Q430 500 472 380 Q508 170 300 150 Z" fill="{_dark(coat, 0.22)}"/>'
    return out


def _on_top(extras, spec, coat, w, h, chin):
    pale, dark, top = _light(coat, 0.5), _dark(coat, 0.35), 290 - h
    out = ""
    if "white_cheeks" in extras:
        out += _pair(lambda: f'<path d="M{300 - w + 6} 300 Q{300 - 40} 330 264 {chin} Q{300 - w + 34} {chin - 6} {300 - w + 6} 300 Z" fill="#f6f1e6" opacity="0.92"/>')
    if "cheek_ruff" in extras:
        out += _pair(lambda: f'<path d="M{300 - w + 8} 286 L{300 - w - 38} 330 L{300 - w + 10} 336 L{300 - w - 18} 374 L{300 - w + 40} 366 Z" fill="{coat}"/>')
    if "whiskers" in extras:
        out += _pair(lambda: "".join(f'<path d="M262 {chin - 26 + i * 15} L{190} {chin - 40 + i * 28}" stroke="{_dark(coat, 0.55)}" stroke-width="3" stroke-linecap="round"/>' for i in range(3)))
    if "teeth" in extras and "fangs" not in spec["ornaments"]:
        out += f'<rect x="286" y="{chin + 6}" width="13" height="26" rx="3" fill="#fbf7f0" stroke="{INK}" stroke-width="2"/><rect x="301" y="{chin + 6}" width="13" height="26" rx="3" fill="#fbf7f0" stroke="{INK}" stroke-width="2"/>'
    if "wool" in extras:
        out += "".join(f'<circle cx="{300 + x}" cy="{top + y}" r="34" fill="#f7f3ea" stroke="#d9d2c3" stroke-width="3"/>' for x, y in ((-70, 26), (-36, 2), (6, -8), (48, 2), (76, 28)))
    if "patch" in extras:
        out += f'<path d="M{300 + 14} {top + 16} Q{300 + w} {top + 24} {300 + w - 10} 300 Q{300 + 44} 316 {300 + 26} 252 Z" fill="#3b2f2c" opacity="0.8"/>'
    if "small_horns" in extras and "horns" not in spec["ornaments"]:
        out += _pair(lambda: f'<path d="M{300 - 62} {top + 18} Q{300 - 112} {top - 6} {300 - 98} {top - 48} Q{300 - 78} {top - 14} {300 - 42} {top + 4} Z" fill="#e7dcc0"/>')
    if "forelock" in extras:
        mane = _dark(coat, 0.5)
        out += f'<path d="M258 {top + 6} Q300 {top - 34} 342 {top + 6} Q322 {top + 62} 306 {top + 26} Q292 {top + 86} 258 {top + 6} Z" fill="{mane}"/>'
    if "tusks" in extras:
        out += _pair(lambda: '<path d="M258 356 Q226 412 246 452 Q252 408 280 372 Z" fill="#f4eedb"/>')
    if "tuft" in extras:
        out += f'<path d="M300 {top + 6} q-10 -52 26 -60 q-16 26 -6 58 M300 {top + 6} q-36 -34 -44 -26 q24 6 30 30" fill="{coat}" stroke="{dark}" stroke-width="3"/>'
    if "mask" in extras:
        out += _pair(lambda: f'<path d="M300 300 Q282 286 254 288 Q258 308 266 322 Z" fill="{INK}"/>')
    if "crest" in extras:
        out += "".join(f'<path d="M{286 + i * 14} {top + 10} q{i * 10 - 8} -54 {i * 22} -66 q-4 34 {-i * 8 + 12} 66 Z" fill="{dark}"/>' for i in range(3))
    if "tongue" in extras:
        out += f'<path d="M300 {chin + 4} L300 {chin + 62} l-20 26 M300 {chin + 62} l20 26" stroke="#c4313f" stroke-width="8" fill="none" stroke-linecap="round"/>'
    return out


def parts(spec):
    """(behind the body, the neck, the head with its face) for an animal spec."""
    animal = ANIMALS[spec["species"]]
    coat, (w, h), extras = coat_colour(spec), animal["head"], animal["extra"]
    neck_top = 210 if "long_neck" in extras else 380
    neck = f'<path d="M252 {neck_top + 20} L252 484 Q300 522 348 484 L348 {neck_top + 20} Z" fill="{_dark(coat, 0.2)}"/>'
    head = _ears(animal["ears"], coat, w, h)
    if "top_eyes" in extras:
        head += _pair(lambda: f'<circle cx="244" cy="212" r="46" fill="{coat}"/>')
    head += f'<ellipse cx="300" cy="290" rx="{w}" ry="{h}" fill="{coat}"/><path d="M300 {290 - h} A{w} {h} 0 0 1 300 {290 + h} Z" fill="{_dark(coat, 0.3)}" opacity="0.22"/>'
    if "eye_discs" in extras:
        head += _pair(lambda: f'<circle cx="254" cy="264" r="54" fill="{_light(coat, 0.55)}"/>')
    face, chin = _front(spec, animal["front"], coat, w, h)
    if "top_eyes" in extras:
        face += _eyes(spec, 212, 56, 25)
    head += face + _on_top(extras, spec, coat, w, h, chin)
    if "fangs" in spec["ornaments"]:
        head += _fangs(chin + 4)
    return _behind(extras, coat, w, h), neck, head


def coat_body(spec):
    """The shoulders of an animal that wears nothing: its coat and a paler chest."""
    coat = coat_colour(spec)
    return (f'<path d="M20 800 L48 610 Q70 505 190 470 L410 470 Q530 505 552 610 L580 800 Z" fill="{coat}"/><path d="M300 470 L410 470 Q530 505 552 610 L580 800 L300 800 Z" fill="{_dark(coat, 0.3)}" opacity="0.45"/>'
            f'<path d="M300 500 Q392 560 368 800 L232 800 Q208 560 300 500 Z" fill="{_light(coat, 0.45)}" opacity="0.9"/>')


def wings(spec):
    """Spread wings behind the shoulders: leathery in dark red-grey for a person or beast, feathered in its coat colour for a bird."""
    if "spread_wings" not in spec["ornaments"]:
        return ""
    feathered = spec["species"] in ("duck", "swan", "bird", "owl")
    colour = coat_colour(spec) if feathered else "#5a2f3f"
    if feathered:
        return _pair(lambda: "".join(f'<path d="M180 560 Q{40 - i * 6} {330 + i * 70} {6} {250 + i * 105} Q{70 + i * 8} {440 + i * 70} 190 {640}Z" fill="{_light(colour, 0.12 * (i % 2))}" stroke="{_dark(colour, 0.3)}" stroke-width="3"/>' for i in range(4)))
    return _pair(lambda: f'<path d="M190 540 Q86 300 8 214 Q22 320 4 392 Q52 380 58 456 Q104 436 110 520 Q150 500 176 640 Z" fill="{colour}" stroke="{_dark(colour, 0.4)}" stroke-width="5"/>')


def horns(spec):
    if "horns" not in spec["ornaments"]:
        return ""
    top = 290 - (ANIMALS[spec["species"]]["head"][1] if spec["species"] in ANIMALS else 150)
    return _pair(lambda: f'<path d="M238 {top + 40} Q158 {top + 4} 156 {top - 92} Q186 {top - 30} 262 {top + 14} Z" fill="#d8c7a0" stroke="#6e5c3c" stroke-width="5"/>')


def snake_hair():
    """A head of snakes (behind the face): coiling necks with small heads, forked tongues and eyes."""
    green, dark = "#4f8a3f", "#2f5a28"
    paths = (("M262 190 Q150 150 128 220 Q108 288 62 266", 62, 266), ("M250 220 Q120 240 142 318 Q166 392 84 396", 84, 396), ("M282 160 Q232 60 170 92 Q124 118 108 72", 108, 72),
             ("M300 150 Q330 40 262 40 Q220 40 236 8", 236, 8))
    one = lambda: "".join(f'<path d="{d}" stroke="{dark}" stroke-width="30" fill="none" stroke-linecap="round"/><path d="{d}" stroke="{green}" stroke-width="20" fill="none" stroke-linecap="round"/>'
                          f'<ellipse cx="{x}" cy="{y}" rx="24" ry="17" fill="{green}" stroke="{dark}" stroke-width="5"/><circle cx="{x - 5}" cy="{y - 4}" r="4" fill="#ffd84a"/>'
                          f'<path d="M{x - 22} {y + 4} l-18 8 m18 -8 l-16 -6" stroke="#c4313f" stroke-width="3" fill="none"/>' for d, x, y in paths)
    return _pair(one)


def human_fangs():
    return _fangs(372, 17)


def human_glow():
    return "".join(f'<circle cx="{cx}" cy="291" r="24" fill="#ffd84a" opacity="0.35"/><circle cx="{cx}" cy="291" r="11" fill="#ffd84a"/><ellipse cx="{cx}" cy="291" rx="3" ry="9" fill="#7a1d12"/>' for cx in (258, 342))
