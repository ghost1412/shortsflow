"""A kit of flat icons and a scene composer for the explaining pictures (engine/case_art.py).

The text model never draws shapes here: it only chooses, for each on-screen label, which ICON stands for it (a person with a mood, a server, a lock, a
cloud, a bug...), its colour and an optional status mark, plus the setting, the layout and which things are linked by arrows. This module draws the
icons (all in one flat style: thick dark outline, bright fills), places them, and says exactly where each one is, so the badges of the video sit on the
right things. Every icon is drawn in a 200 x 200 box centred on (0, 0).

    compose(spec, aspect) -> (svg text, [(x, y) badge position in percent of the picture, one per item])
"""
import math

OUT = "#1f2937"
SKIN = "#f2c29b"
COLORS = {"blue": "#3b82f6", "orange": "#f59e0b", "green": "#22c55e", "purple": "#8b5cf6", "red": "#ef4444", "yellow": "#facc15",
          "teal": "#14b8a6", "pink": "#ec4899", "gray": "#94a3b8", "navy": "#334155"}
CYCLE = ("blue", "orange", "green", "purple", "teal", "pink")
MOODS = ("neutral", "happy", "angry", "worried")
SETTINGS = ("office", "city", "cloud", "night", "space")
LAYOUTS = ("row", "hub", "triangle")


def mix(hex_color, other, k):
    """`hex_color` mixed with `other` (k = share of other, 0 to 1)."""
    a = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(a, b))


def light(c, k=0.55):
    return mix(c, "#ffffff", k)


def dark(c, k=0.3):
    return mix(c, "#000000", k)


def S(width=6):
    return f'stroke="{OUT}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"'


# ---- icons: each returns SVG for a 200 x 200 box centred on 0,0 ------------------------------------------------------------------

def person(c, mood="neutral"):
    brows = {"angry": f'<path d="M-27 -45 L-7 -36 M27 -45 L7 -36" {S(5)} fill="none"/>',
             "worried": f'<path d="M-27 -36 L-7 -45 M27 -36 L7 -45" {S(5)} fill="none"/>'}.get(mood, "")
    mouth = {"happy": f'<path d="M-15 -10 Q0 8 15 -10" {S(5)} fill="none"/>',
             "angry": f'<path d="M-13 -4 Q0 -14 13 -4" {S(5)} fill="none"/>',
             "worried": f'<ellipse cx="0" cy="-5" rx="8" ry="6" fill="{OUT}"/>'}.get(mood, f'<path d="M-10 -7 L10 -7" {S(5)} fill="none"/>')
    return (f'<path d="M-54 92 Q-54 22 0 22 Q54 22 54 92 Z" fill="{c}" {S()}/>'
            f'<circle cx="0" cy="-26" r="40" fill="{SKIN}" {S()}/>'
            f'<path d="M-40 -32 Q-38 -76 0 -74 Q40 -76 40 -32 Q22 -54 0 -52 Q-24 -54 -40 -32 Z" fill="{dark("#8a5a3c", 0.2)}" {S(5)}/>'
            f'<circle cx="-15" cy="-26" r="5.5" fill="{OUT}"/><circle cx="15" cy="-26" r="5.5" fill="{OUT}"/>{brows}{mouth}')


def hacker(c, mood="neutral"):
    return (f'<path d="M-60 92 Q-60 14 0 14 Q60 14 60 92 Z" fill="{OUT}" {S()}/>'
            f'<circle cx="0" cy="-26" r="52" fill="{OUT}" {S()}/><ellipse cx="0" cy="-22" rx="34" ry="30" fill="#0b1220"/>'
            f'<ellipse cx="-15" cy="-26" rx="8" ry="5" fill="{light(c, 0.2)}"/><ellipse cx="15" cy="-26" rx="8" ry="5" fill="{light(c, 0.2)}"/>'
            f'<path d="M-14 0 Q0 10 14 0" stroke="{light(c, 0.2)}" stroke-width="4" fill="none" stroke-linecap="round"/>')


def group(c, mood="neutral"):
    one = lambda x, y, s, col: f'<g transform="translate({x} {y}) scale({s})">{person(col, mood)}</g>'
    return one(-52, 16, 0.62, dark(c, 0.15)) + one(52, 16, 0.62, light(c, 0.2)) + one(0, 4, 0.78, c)


def laptop(c, mood=None):
    return (f'<rect x="-70" y="-66" width="140" height="96" rx="9" fill="#334155" {S()}/><rect x="-59" y="-55" width="118" height="74" rx="4" fill="{light(c, 0.7)}"/>'
            f'<rect x="-46" y="-42" width="52" height="8" rx="3" fill="{c}"/><rect x="-46" y="-26" width="86" height="8" rx="3" fill="{light(c, 0.3)}"/>'
            f'<rect x="-46" y="-10" width="64" height="8" rx="3" fill="{light(c, 0.3)}"/>'
            f'<path d="M-94 36 L94 36 L82 64 L-82 64 Z" fill="#cbd5e1" {S()}/>')


def phone(c, mood=None):
    return (f'<rect x="-40" y="-84" width="80" height="168" rx="18" fill="{c}" {S()}/><rect x="-31" y="-64" width="62" height="116" rx="6" fill="{light(c, 0.75)}"/>'
            f'<rect x="-20" y="-50" width="40" height="8" rx="3" fill="{c}"/><rect x="-20" y="-32" width="30" height="8" rx="3" fill="{light(c, 0.3)}"/>'
            f'<circle cx="0" cy="68" r="6" fill="{OUT}"/>')


def server(c, mood=None):
    rows = ""
    for i, y in enumerate((-84, -30, 24)):
        rows += (f'<rect x="-72" y="{y}" width="144" height="52" rx="9" fill="{c}" {S()}/>'
                 f'<circle cx="-50" cy="{y + 26}" r="7" fill="{"#22c55e" if i != 1 else "#facc15"}" stroke="{OUT}" stroke-width="3"/>'
                 f'<rect x="-28" y="{y + 20}" width="74" height="12" rx="4" fill="{dark(c, 0.25)}"/>')
    return rows + f'<rect x="-52" y="78" width="104" height="10" rx="4" fill="#475569" {S(4)}/>'


def database(c, mood=None):
    return (f'<path d="M-64 -52 L-64 52 A64 26 0 0 0 64 52 L64 -52 Z" fill="{c}" {S()}/><ellipse cx="0" cy="-52" rx="64" ry="26" fill="{light(c, 0.45)}" {S()}/>'
            f'<path d="M-64 -8 A64 26 0 0 0 64 -8 M-64 34 A64 26 0 0 0 64 34" fill="none" {S(5)}/>')


def cloud(c, mood=None):
    return (f'<path d="M-62 44 Q-94 44 -94 12 Q-94 -18 -60 -22 Q-54 -64 -8 -64 Q36 -66 48 -30 Q88 -30 90 8 Q90 44 54 44 Z" fill="{light(c, 0.55)}" {S()}/>'
            f'<path d="M-40 10 Q-20 -8 0 10" stroke="{c}" stroke-width="6" fill="none" stroke-linecap="round" opacity="0.7"/>')


def lock(c, mood=None):
    return (f'<path d="M-32 -8 L-32 -42 A32 32 0 0 1 32 -42 L32 -8" fill="none" stroke="{OUT}" stroke-width="16" stroke-linecap="round"/>'
            f'<path d="M-32 -8 L-32 -42 A32 32 0 0 1 32 -42 L32 -8" fill="none" stroke="#cbd5e1" stroke-width="7" stroke-linecap="round"/>'
            f'<rect x="-56" y="-12" width="112" height="90" rx="16" fill="{c}" {S()}/><circle cx="0" cy="24" r="12" fill="{OUT}"/><rect x="-5" y="28" width="10" height="26" rx="4" fill="{OUT}"/>')


def unlock(c, mood=None):
    return (f'<path d="M32 -14 L32 -46 A32 32 0 0 0 -32 -46 L-32 -30" fill="none" stroke="{OUT}" stroke-width="16" stroke-linecap="round"/>'
            f'<path d="M32 -14 L32 -46 A32 32 0 0 0 -32 -46 L-32 -30" fill="none" stroke="#cbd5e1" stroke-width="7" stroke-linecap="round"/>'
            f'<rect x="-56" y="-12" width="112" height="90" rx="16" fill="{c}" {S()}/><circle cx="0" cy="24" r="12" fill="{OUT}"/><rect x="-5" y="28" width="10" height="26" rx="4" fill="{OUT}"/>')


def key(c, mood=None):
    return (f'<rect x="-6" y="-12" width="100" height="24" rx="8" fill="{c}" {S()}/><rect x="52" y="12" width="14" height="30" rx="4" fill="{c}" {S(5)}/>'
            f'<rect x="76" y="12" width="14" height="22" rx="4" fill="{c}" {S(5)}/><circle cx="-44" cy="0" r="40" fill="{c}" {S()}/><circle cx="-44" cy="0" r="15" fill="#ffffff" {S(5)}/>')


def shield(c, mood=None):
    return (f'<path d="M0 -88 L70 -60 L70 6 Q70 58 0 90 Q-70 58 -70 6 L-70 -60 Z" fill="{c}" {S()}/>'
            f'<path d="M0 -66 L52 -45 L52 4 Q52 44 0 70 Z" fill="{light(c, 0.25)}" opacity="0.7"/>'
            f'<polyline points="-30,4 -8,28 34,-22" fill="none" stroke="#ffffff" stroke-width="15" stroke-linecap="round" stroke-linejoin="round"/>')


def bug(c, mood=None):
    legs = "".join(f'<path d="M{sx * 36} {y} L{sx * 78} {y + dy}" {S(6)} fill="none"/>' for sx in (-1, 1) for y, dy in ((-14, -22), (10, 0), (34, 22)))
    return (legs + f'<path d="M-14 -66 L-30 -92 M14 -66 L30 -92" {S(5)} fill="none"/><ellipse cx="0" cy="12" rx="44" ry="56" fill="{c}" {S()}/>'
            f'<circle cx="0" cy="-52" r="24" fill="{dark(c, 0.2)}" {S()}/><path d="M0 -40 L0 64" {S(4)} fill="none"/>'
            f'<circle cx="-20" cy="-4" r="9" fill="{light(c, 0.55)}"/><circle cx="20" cy="22" r="9" fill="{light(c, 0.55)}"/><circle cx="-18" cy="36" r="7" fill="{light(c, 0.55)}"/>'
            f'<circle cx="-9" cy="-56" r="5" fill="#fff"/><circle cx="9" cy="-56" r="5" fill="#fff"/>')


def document(c, mood=None):
    lines = "".join(f'<rect x="-34" y="{y}" width="{w}" height="10" rx="4" fill="{light(c, 0.2)}"/>' for y, w in ((-16, 84), (6, 70), (28, 84), (50, 46)))
    return (f'<path d="M-56 -86 L22 -86 L58 -50 L58 86 L-56 86 Z" fill="#ffffff" {S()}/><path d="M22 -86 L22 -50 L58 -50 Z" fill="{light(c, 0.4)}" {S(5)}/>'
            f'<rect x="-34" y="-58" width="48" height="14" rx="4" fill="{c}"/>{lines}')


def folder(c, mood=None):
    return (f'<path d="M-84 -56 L-24 -56 L-6 -34 L84 -34 L84 66 L-84 66 Z" fill="{dark(c, 0.15)}" {S()}/>'
            f'<path d="M-84 -14 L84 -14 L84 66 L-84 66 Z" fill="{c}" {S()}/>')


def mail(c, mood=None):
    return (f'<rect x="-84" y="-56" width="168" height="112" rx="12" fill="#ffffff" {S()}/><path d="M-84 -50 L0 14 L84 -50" fill="{light(c, 0.55)}" {S()}/>'
            f'<path d="M-84 56 L-26 4 M84 56 L26 4" fill="none" {S(5)}/>')


def globe(c, mood=None):
    return (f'<circle r="74" fill="{c}" {S()}/><path d="M-38 -34 Q-18 -56 6 -40 Q-2 -14 -24 -6 Q-44 -12 -38 -34 Z M22 6 Q50 2 52 28 Q40 52 20 40 Q10 22 22 6 Z" fill="{light(c, 0.55)}"/>'
            f'<ellipse rx="32" ry="74" fill="none" {S(5)}/><path d="M-74 0 L74 0 M-64 -38 L64 -38 M-64 38 L64 38" fill="none" {S(4)}/>')


def building(c, mood=None):
    wins = "".join(f'<rect x="{x}" y="{y}" width="20" height="20" rx="3" fill="{light(c, 0.75)}"/>' for x in (-30, 0, 30) for y in (-64, -30, 4))
    return f'<rect x="-48" y="-88" width="96" height="176" rx="6" fill="{c}" {S()}/>{wins}<rect x="-14" y="44" width="28" height="44" rx="4" fill="{dark(c, 0.35)}"/>'


def house(c, mood=None):
    return (f'<rect x="-62" y="-14" width="124" height="96" rx="6" fill="{light(c, 0.35)}" {S()}/><path d="M-80 -8 L0 -82 L80 -8 Z" fill="{c}" {S()}/>'
            f'<rect x="-14" y="30" width="28" height="52" rx="4" fill="{dark(c, 0.3)}"/><rect x="26" y="14" width="24" height="24" rx="3" fill="#ffffff" {S(4)}/>')


def gear(c, mood=None):
    pts = []
    for i in range(16):
        r = 84 if i % 2 == 0 else 62
        for a in (i - 0.28, i + 0.28):
            ang = a * math.pi / 8
            pts.append(f"{r * math.cos(ang):.1f},{r * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{c}" {S()}/><circle r="26" fill="#ffffff" {S(5)}/>'


def chart_up(c, mood=None, down=False):
    heights = ((-70, 120), (-24, 80), (22, 40)) if down else ((-70, 40), (-24, 80), (22, 120))
    bars = "".join(f'<rect x="{x}" y="{58 - h}" width="34" height="{h}" rx="5" fill="{c}" {S(5)}/>' for x, h in heights)
    col, line, head = ("#ef4444", "-72,-84 -20,-40 4,-62 62,-4", "62,-4 34,-8 58,-30") if down else ("#22c55e", "-72,-6 -20,-50 4,-24 62,-82", "62,-82 34,-78 58,-56")
    return (bars + f'<path d="M-86 66 L86 66" {S(6)}/>'
            f'<polyline points="{line}" fill="none" stroke="{OUT}" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<polyline points="{line}" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<polyline points="{head}" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')


def chart_down(c, mood=None):
    return chart_up(c, mood, True)


def money(c, mood=None):
    return (f'<circle r="70" fill="#facc15" {S()}/><circle r="50" fill="none" stroke="{dark("#facc15", 0.3)}" stroke-width="6"/>'
            f'<path d="M20 -26 Q-26 -44 -24 -12 Q-22 8 0 10 Q26 12 24 36 Q18 58 -26 42 M0 -50 L0 58" fill="none" {S(9)}/>')


def clock(c, mood=None):
    return (f'<circle r="74" fill="{c}" {S()}/><circle r="56" fill="#ffffff" {S(5)}/><path d="M0 -40 L0 0 L28 18" fill="none" {S(8)}/><circle r="7" fill="{OUT}"/>'
            f'<path d="M0 -50 L0 -44 M50 0 L44 0 M0 50 L0 44 M-50 0 L-44 0" {S(5)}/>')


def warning(c, mood=None):
    return (f'<path d="M0 -84 L88 70 L-88 70 Z" fill="#facc15" {S(8)}/><rect x="-8" y="-36" width="16" height="58" rx="6" fill="{OUT}"/><circle cx="0" cy="46" r="9" fill="{OUT}"/>')


def check(c, mood=None):
    return f'<circle r="74" fill="#22c55e" {S()}/><polyline points="-34,2 -10,28 38,-26" fill="none" stroke="#fff" stroke-width="17" stroke-linecap="round" stroke-linejoin="round"/>'


def cross(c, mood=None):
    return f'<circle r="74" fill="#ef4444" {S()}/><path d="M-30 -30 L30 30 M30 -30 L-30 30" stroke="#fff" stroke-width="17" stroke-linecap="round"/>'


def magnifier(c, mood=None):
    return (f'<path d="M26 26 L80 80" stroke="{OUT}" stroke-width="24" stroke-linecap="round"/><path d="M26 26 L80 80" stroke="{c}" stroke-width="12" stroke-linecap="round"/>'
            f'<circle cx="-12" cy="-12" r="54" fill="{light(c, 0.8)}" {S(10)}/><path d="M-36 -26 Q-24 -46 -2 -42" stroke="#fff" stroke-width="8" fill="none" stroke-linecap="round"/>')


def fire(c, mood=None):
    return (f'<path d="M0 -88 Q40 -42 38 -4 Q60 -22 56 -52 Q92 -8 72 36 Q58 82 0 86 Q-62 82 -68 28 Q-72 -10 -34 -46 Q-30 -22 -14 -12 Q-26 -52 0 -88 Z" fill="#f97316" {S()}/>'
            f'<path d="M0 -20 Q28 6 26 36 Q18 62 0 62 Q-26 62 -28 34 Q-26 12 0 -20 Z" fill="#fde047"/>')


def wifi(c, mood=None):
    arcs = "".join(f'<path d="M{-r * 0.8:.0f} {-r * 0.55 + 40:.0f} A{r} {r} 0 0 1 {r * 0.8:.0f} {-r * 0.55 + 40:.0f}" fill="none" stroke="{OUT}" stroke-width="22" stroke-linecap="round"/>'
                   f'<path d="M{-r * 0.8:.0f} {-r * 0.55 + 40:.0f} A{r} {r} 0 0 1 {r * 0.8:.0f} {-r * 0.55 + 40:.0f}" fill="none" stroke="{c}" stroke-width="12" stroke-linecap="round"/>' for r in (96, 64, 34))
    return arcs + f'<circle cx="0" cy="56" r="14" fill="{c}" {S(5)}/>'


def burst(c, mood=None):
    pts = []
    for i in range(24):
        r = 90 if i % 2 == 0 else 54
        a = i * math.pi / 12
        pts.append(f"{r * math.cos(a):.1f},{r * math.sin(a):.1f}")
    inner = " ".join(f"{(52 if i % 2 == 0 else 28) * math.cos(i * math.pi / 8):.1f},{(52 if i % 2 == 0 else 28) * math.sin(i * math.pi / 8):.1f}" for i in range(16))
    return f'<polygon points="{" ".join(pts)}" fill="#f97316" {S()}/><polygon points="{inner}" fill="#fde047"/>'


def bulb(c, mood=None):
    rays = "".join(f'<path d="M{math.cos(a) * 66:.0f} {-26 + math.sin(a) * 66:.0f} L{math.cos(a) * 88:.0f} {-26 + math.sin(a) * 88:.0f}" {S(6)}/>' for a in (-2.4, -1.57, -0.74, 3.14, 0))
    return (rays + f'<path d="M-34 24 Q-52 4 -52 -22 A52 52 0 0 1 52 -22 Q52 4 34 24 Z" fill="#fde047" {S()}/><rect x="-28" y="24" width="56" height="30" rx="8" fill="#cbd5e1" {S()}/>'
            f'<path d="M-14 62 L14 62" {S(8)}/>')


def network(c, mood=None):
    nodes = ((0, -56), (-62, 44), (62, 44))
    lines = "".join(f'<path d="M{a[0]} {a[1]} L{b[0]} {b[1]}" {S(7)}/>' for a, b in ((nodes[0], nodes[1]), (nodes[0], nodes[2]), (nodes[1], nodes[2])))
    return lines + "".join(f'<circle cx="{x}" cy="{y}" r="26" fill="{c}" {S()}/>' for x, y in nodes)


def target(c, mood=None):
    return (f'<circle r="78" fill="#ffffff" {S()}/><circle r="56" fill="{c}" {S(5)}/><circle r="34" fill="#ffffff" {S(5)}/><circle r="14" fill="{dark(c, 0.1)}" {S(4)}/>'
            f'<path d="M0 0 L70 -70" {S(8)}/><path d="M70 -70 L50 -68 M70 -70 L68 -50" {S(8)}/>')


def robot(c, mood=None):
    return (f'<path d="M0 -62 L0 -88" {S(7)}/><circle cy="-92" r="10" fill="#ef4444" {S(5)}/><rect x="-62" y="-62" width="124" height="106" rx="22" fill="{c}" {S()}/>'
            f'<circle cx="-26" cy="-14" r="17" fill="#fff" {S(5)}/><circle cx="26" cy="-14" r="17" fill="#fff" {S(5)}/><circle cx="-26" cy="-14" r="7" fill="{OUT}"/><circle cx="26" cy="-14" r="7" fill="{OUT}"/>'
            f'<path d="M-24 22 L24 22" {S(6)}/><rect x="-44" y="52" width="88" height="40" rx="12" fill="{dark(c, 0.15)}" {S()}/>')


def box(c, mood=None):
    """a container, a package, a deployable unit"""
    return (f'<path d="M-72 -34 L0 -70 L72 -34 L72 44 L0 80 L-72 44 Z" fill="{c}" {S()}/><path d="M-72 -34 L0 2 L72 -34 M0 2 L0 80" fill="none" {S(6)}/>'
            f'<path d="M-72 -34 L0 2 L0 80 L-72 44 Z" fill="{dark(c, 0.18)}" {S(6)}/><path d="M-40 -52 L32 -16 L32 6" fill="none" stroke="{light(c, 0.7)}" stroke-width="9" stroke-linecap="round"/>')


def queue(c, mood=None):
    """a queue or pipeline of messages waiting in line"""
    cells = "".join(f'<rect x="{x}" y="-30" width="42" height="60" rx="9" fill="{light(c, k)}" {S(5)}/>' for x, k in ((-92, 0.0), (-44, 0.2), (4, 0.4)))
    return (f'<rect x="-100" y="-50" width="200" height="100" rx="18" fill="#e2e8f0" {S()}/>{cells}'
            f'<path d="M62 0 L86 0 M76 -12 L88 0 L76 12" fill="none" {S(7)}/>')


def chip(c, mood=None):
    """a processor, a chip, CPU load"""
    pins = "".join(f'<path d="M{p} -78 L{p} -58 M{p} 58 L{p} 78 M-78 {p} L-58 {p} M58 {p} L78 {p}" {S(7)}/>' for p in (-30, 0, 30))
    return pins + f'<rect x="-58" y="-58" width="116" height="116" rx="14" fill="{c}" {S()}/><rect x="-30" y="-30" width="60" height="60" rx="8" fill="{light(c, 0.55)}" {S(5)}/><circle r="9" fill="{OUT}"/>'


def layers(c, mood=None):
    """layers, a stack, tiers of a system"""
    one = lambda y, col: f'<path d="M0 {y - 34} L84 {y} L0 {y + 34} L-84 {y} Z" fill="{col}" {S(6)}/>'
    return one(40, dark(c, 0.2)) + one(8, c) + one(-24, light(c, 0.4))


def plug(c, mood=None):
    """a connection, an API, an integration"""
    return (f'<path d="M-24 -84 L-24 -40 M24 -84 L24 -40" {S(14)}/><rect x="-52" y="-44" width="104" height="70" rx="18" fill="{c}" {S()}/>'
            f'<path d="M0 26 L0 52 Q0 84 -36 84 L-70 84" fill="none" stroke="{OUT}" stroke-width="16" stroke-linecap="round"/>')


def bell(c, mood=None):
    """an alarm, a notification, an alert being raised"""
    return (f'<path d="M-62 40 Q-52 36 -52 8 Q-52 -52 0 -56 Q52 -52 52 8 Q52 36 62 40 Z" fill="#facc15" {S()}/><circle cx="0" cy="-64" r="10" fill="#facc15" {S(5)}/>'
            f'<path d="M-18 52 Q0 76 18 52 Z" fill="{c}" {S(5)}/><path d="M-82 -24 Q-90 -4 -82 16 M82 -24 Q90 -4 82 16" fill="none" {S(7)}/>')


def black_hole(c, mood=None):
    """a black hole with its glowing ring of gas"""
    return (f'<g transform="rotate(-16)"><ellipse rx="96" ry="30" fill="none" stroke="{OUT}" stroke-width="30"/><ellipse rx="96" ry="30" fill="none" stroke="{c}" stroke-width="20"/>'
            f'<ellipse rx="96" ry="30" fill="none" stroke="#fde68a" stroke-width="7"/></g>'
            f'<circle r="46" fill="#05070f" {S()}/><path d="M-64 -30 Q0 -92 64 -30" fill="none" stroke="{OUT}" stroke-width="22" stroke-linecap="round"/>'
            f'<path d="M-64 -30 Q0 -92 64 -30" fill="none" stroke="{c}" stroke-width="12" stroke-linecap="round"/>')


def planet(c, mood=None):
    return (f'<circle r="58" fill="{c}" {S()}/><path d="M-50 -20 Q0 -40 50 -20 M-58 8 Q0 -14 58 8" fill="none" stroke="{light(c, 0.35)}" stroke-width="9" stroke-linecap="round"/>'
            f'<g transform="rotate(-20)"><path d="M-102 0 A102 26 0 0 0 102 0" fill="none" stroke="{OUT}" stroke-width="18"/><path d="M-102 0 A102 26 0 0 0 102 0" fill="none" stroke="#fde68a" stroke-width="9"/></g>')


def star(c, mood=None):
    pts = " ".join(f"{(88 if i % 2 == 0 else 38) * math.cos(-math.pi / 2 + i * math.pi / 5):.1f},{(88 if i % 2 == 0 else 38) * math.sin(-math.pi / 2 + i * math.pi / 5):.1f}" for i in range(10))
    return f'<polygon points="{pts}" fill="#facc15" {S(7)}/><circle cx="-12" cy="-6" r="7" fill="#fff" opacity="0.7"/>'


def galaxy(c, mood=None):
    arms = "".join(f'<ellipse rx="{rx}" ry="{ry}" transform="rotate({a})" fill="none" stroke="{light(c, k)}" stroke-width="{w}" stroke-linecap="round" opacity="0.9"/>'
                   for rx, ry, a, k, w in ((88, 30, 24, 0.0, 12), (70, 22, 24, 0.3, 9), (88, 30, -30, 0.2, 10), (60, 18, -30, 0.5, 7)))
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="#fff"/>' for x, y in ((-70, 40), (74, -46), (30, 62), (-46, -58)))
    return f'<circle r="96" fill="#0b1020" {S(5)}/>{arms}{dots}<circle r="20" fill="#fde68a"/><circle r="10" fill="#fff"/>'


def telescope(c, mood=None):
    return (f'<path d="M0 22 L-46 92 M0 22 L46 92 M0 22 L0 92" {S(9)}/><g transform="rotate(-28 0 0)"><rect x="-92" y="-26" width="150" height="52" rx="10" fill="{c}" {S()}/>'
            f'<rect x="40" y="-34" width="34" height="68" rx="8" fill="{dark(c, 0.25)}" {S()}/><rect x="-104" y="-18" width="20" height="36" rx="6" fill="#cbd5e1" {S(5)}/><rect x="-62" y="-26" width="12" height="52" fill="{light(c, 0.4)}"/></g>'
            f'<circle cx="0" cy="22" r="11" fill="#cbd5e1" {S(5)}/>')


def dish(c, mood=None):
    return (f'<path d="M-6 20 L-44 92 M-6 20 L32 92 M-60 92 L56 92" {S(9)}/><path d="M-84 -50 Q-84 40 4 56 L40 -26 Q-30 -70 -84 -50 Z" fill="{c}" {S()}/>'
            f'<path d="M-52 -30 Q-52 20 6 36" fill="none" stroke="{light(c, 0.5)}" stroke-width="8" stroke-linecap="round"/><path d="M-22 6 L58 -50" {S(7)}/><circle cx="62" cy="-54" r="10" fill="#facc15" {S(5)}/>'
            f'<path d="M80 -78 Q104 -54 86 -22 M96 -92 Q132 -56 106 -8" fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round" opacity="0.8"/>')


def atom(c, mood=None):
    orbit = lambda a: f'<ellipse rx="92" ry="34" transform="rotate({a})" fill="none" stroke="{OUT}" stroke-width="12"/><ellipse rx="92" ry="34" transform="rotate({a})" fill="none" stroke="{c}" stroke-width="6"/>'
    electrons = "".join(f'<circle cx="{92 * math.cos(math.radians(t)) * math.cos(math.radians(a)) - 34 * math.sin(math.radians(t)) * math.sin(math.radians(a)):.1f}" '
                        f'cy="{92 * math.cos(math.radians(t)) * math.sin(math.radians(a)) + 34 * math.sin(math.radians(t)) * math.cos(math.radians(a)):.1f}" r="10" fill="#facc15" {S(5)}/>'
                        for a, t in ((0, 40), (60, 200), (120, 300)))
    return orbit(0) + orbit(60) + orbit(120) + f'<circle r="22" fill="#ef4444" {S(6)}/><circle cx="-6" cy="-6" r="6" fill="#fff" opacity="0.6"/>' + electrons


def wave(c, mood=None):
    path = "M-92 0 Q-69 -64 -46 0 T0 0 T46 0 T92 0"
    return (f'<rect x="-100" y="-62" width="200" height="124" rx="20" fill="#ffffff" {S()}/><path d="M-84 0 L84 0" stroke="#cbd5e1" stroke-width="5" stroke-dasharray="2 10" stroke-linecap="round"/>'
            f'<path d="{path}" transform="scale(0.88)" fill="none" stroke="{OUT}" stroke-width="20" stroke-linecap="round"/><path d="{path}" transform="scale(0.88)" fill="none" stroke="{c}" stroke-width="11" stroke-linecap="round"/>')


def magnet(c, mood=None):
    return (f'<path d="M-62 82 L-62 -6 A62 62 0 0 1 62 -6 L62 82" fill="none" stroke="{OUT}" stroke-width="52" stroke-linejoin="round"/>'
            f'<path d="M-62 82 L-62 -6 A62 62 0 0 1 62 -6 L62 82" fill="none" stroke="#ef4444" stroke-width="38"/><path d="M62 82 L62 -6 A62 62 0 0 0 0 -68" fill="none" stroke="#3b82f6" stroke-width="38"/>'
            f'<rect x="-81" y="58" width="38" height="28" fill="#e2e8f0" {S(5)}/><rect x="43" y="58" width="38" height="28" fill="#e2e8f0" {S(5)}/>')


def rocket(c, mood=None):
    return (f'<path d="M-24 52 Q-34 96 0 92 Q34 96 24 52 Z" fill="#f97316" {S(6)}/><path d="M-30 48 L-72 76 L-52 10 Z M30 48 L72 76 L52 10 Z" fill="{dark(c, 0.15)}" {S(6)}/>'
            f'<path d="M0 -92 Q50 -48 40 40 L-40 40 Q-50 -48 0 -92 Z" fill="#f8fafc" {S()}/><path d="M0 -92 Q26 -70 36 -40 L-36 -40 Q-26 -70 0 -92 Z" fill="{c}" {S(6)}/>'
            f'<circle cx="0" cy="-6" r="20" fill="#93c5fd" {S(6)}/>')


def flask(c, mood=None):
    return (f'<path d="M-22 -86 L-22 -34 L-78 66 Q-90 90 -62 90 L62 90 Q90 90 78 66 L22 -34 L22 -86" fill="#eaf6ff" {S()}/>'
            f'<path d="M-52 22 L52 22 L78 66 Q90 90 62 90 L-62 90 Q-90 90 -78 66 Z" fill="{c}" {S(6)}/><circle cx="-16" cy="52" r="8" fill="{light(c, 0.6)}"/><circle cx="18" cy="66" r="6" fill="{light(c, 0.6)}"/>'
            f'<rect x="-34" y="-96" width="68" height="16" rx="8" fill="#cbd5e1" {S(6)}/>')


def microscope(c, mood=None):
    return (f'<rect x="-70" y="74" width="140" height="18" rx="8" fill="#475569" {S(6)}/><path d="M-38 74 Q-90 62 -64 6 Q-50 -26 -8 -34" fill="none" stroke="{OUT}" stroke-width="26" stroke-linecap="round"/>'
            f'<path d="M-38 74 Q-90 62 -64 6 Q-50 -26 -8 -34" fill="none" stroke="{c}" stroke-width="14" stroke-linecap="round"/><g transform="rotate(-22 0 -40)"><rect x="-18" y="-96" width="38" height="92" rx="8" fill="{c}" {S()}/>'
            f'<rect x="-12" y="-4" width="26" height="22" rx="4" fill="#cbd5e1" {S(5)}/></g><rect x="-10" y="40" width="74" height="12" rx="5" fill="#cbd5e1" {S(6)}/>')


def sun(c, mood=None):
    rays = "".join(f'<path d="M{math.cos(a) * 62:.0f} {math.sin(a) * 62:.0f} L{math.cos(a) * 92:.0f} {math.sin(a) * 92:.0f}" {S(11)}/>' for a in [i * math.pi / 4 for i in range(8)])
    return rays + f'<circle r="52" fill="#facc15" {S()}/><circle cx="-14" cy="-14" r="12" fill="#fff" opacity="0.55"/>'


def moon(c, mood=None):
    return (f'<path d="M30 -80 A82 82 0 1 0 30 80 A64 64 0 0 1 30 -80 Z" fill="#fde68a" {S()}/><circle cx="-22" cy="-20" r="11" fill="#f3d06b"/><circle cx="-34" cy="30" r="8" fill="#f3d06b"/>'
            f'<polygon points="58,-34 63,-22 76,-22 66,-14 70,-2 58,-9 46,-2 50,-14 40,-22 53,-22" fill="#fde68a" {S(4)}/>')


def eye(c, mood=None):
    return (f'<path d="M-96 0 Q0 -84 96 0 Q0 84 -96 0 Z" fill="#ffffff" {S()}/><circle r="38" fill="{c}" {S(6)}/><circle r="17" fill="{OUT}"/><circle cx="-10" cy="-12" r="7" fill="#fff"/>')


def camera(c, mood=None):
    return (f'<rect x="-30" y="-62" width="60" height="22" rx="8" fill="{dark(c, 0.3)}" {S(6)}/><rect x="-92" y="-48" width="184" height="124" rx="22" fill="{c}" {S()}/>'
            f'<circle cy="14" r="44" fill="#e2e8f0" {S()}/><circle cy="14" r="28" fill="{OUT}"/><circle cx="-8" cy="6" r="9" fill="#93c5fd"/><circle cx="68" cy="-24" r="8" fill="#facc15" {S(4)}/>')


ICONS = {"person": person, "hacker": hacker, "group": group, "laptop": laptop, "phone": phone, "server": server, "database": database, "cloud": cloud,
         "lock": lock, "unlock": unlock, "key": key, "shield": shield, "bug": bug, "document": document, "folder": folder, "mail": mail, "globe": globe,
         "building": building, "house": house, "gear": gear, "chart_up": chart_up, "chart_down": chart_down, "money": money, "clock": clock,
         "warning": warning, "check": check, "cross": cross, "magnifier": magnifier, "fire": fire, "wifi": wifi, "burst": burst, "bulb": bulb,
         "network": network, "target": target, "robot": robot, "box": box, "queue": queue, "chip": chip, "layers": layers, "plug": plug, "bell": bell,
         "black_hole": black_hole, "planet": planet, "star": star, "galaxy": galaxy, "telescope": telescope, "dish": dish, "atom": atom, "wave": wave,
         "magnet": magnet, "rocket": rocket, "flask": flask, "microscope": microscope, "sun": sun, "moon": moon, "eye": eye, "camera": camera}
CUSTOM = {}                      # icons drawn while a video was made (engine/art_icons.py): name -> markup, colours of their own


def register(name, markup):
    """Make a drawn icon usable by name in scenes (it keeps its own colours; the colour a scene asks for does not recolour it)."""
    CUSTOM[name] = lambda c, mood=None, _m=markup: _m


def icon(kind):
    return ICONS.get(kind) or CUSTOM[kind]


MARKS = ("warning", "check", "cross", "fire", "lock", "burst")
HELP = {"person": "a person (add a mood: neutral, happy, angry, worried)", "hacker": "an attacker or intruder in a dark hood", "group": "a team, crowd or users",
        "laptop": "a computer or a developer's machine", "phone": "a phone or app", "server": "a server, a rack, machines in a data centre", "database": "stored data",
        "cloud": "the cloud or a cloud service", "lock": "something locked, secure, encrypted", "unlock": "something open, unlocked, exposed", "key": "a key, a password, access",
        "shield": "protection, defence, a fix", "bug": "a bug, malware, a flaw", "document": "a document, a report, a file, a policy", "folder": "files, a repository",
        "mail": "an email or a message", "globe": "the internet, the world, a website", "building": "a company or an office", "house": "a home or a small business",
        "gear": "a process, a system, how something works", "chart_up": "growth, a rise", "chart_down": "a drop, a decline, a loss", "money": "money, cost, a payment",
        "clock": "time, a delay, a deadline", "warning": "danger, an alert", "check": "success, approved", "cross": "failure, denied, blocked", "magnifier": "searching, an investigation, a finding",
        "fire": "an emergency or something burning", "wifi": "network, signal, connectivity", "burst": "a crash, an explosion, a sudden failure", "bulb": "an idea or a lesson",
        "network": "connected nodes, a cluster, a mesh", "target": "a goal or a target", "robot": "AI, a bot, automation",
        "box": "a container, a package, a service you deploy (a pod, a sidecar, a build)", "queue": "a message queue, a pipeline, requests waiting in line",
        "chip": "a processor, CPU load, hardware", "layers": "layers or tiers of a system, a stack", "plug": "a connection, an API, an integration", "bell": "an alarm or a notification",
        "black_hole": "a black hole, extreme gravity", "planet": "a planet or a world", "star": "a star, a bright source, a favourite", "galaxy": "a galaxy or the universe",
        "telescope": "a telescope, observing the sky", "dish": "a radio dish or antenna, receiving a signal (radio astronomy, satellites)",
        "atom": "an atom, a particle, quantum physics", "wave": "a wave, a signal, a frequency, a measurement over time", "magnet": "magnetism, attraction, a field",
        "rocket": "a launch, space travel, fast progress", "flask": "chemistry, an experiment, a lab test", "microscope": "very small things, biology, close study",
        "sun": "the sun, energy, heat, daylight", "moon": "the moon, night, a satellite", "eye": "seeing, observing, watching, surveillance",
        "camera": "a camera, an image, taking a photo"}


# ---- scene ----------------------------------------------------------------------------------------------------------------------

def background(setting, w, h):
    floor_y = h * 0.8
    if setting == "space":
        stars = "".join(f'<circle cx="{(i * 193) % w}" cy="{(i * 89) % h}" r="{1.2 + (i % 4) * 0.8}" fill="#f8fafc" opacity="{0.45 + (i % 5) * 0.1:.2f}"/>' for i in range(1, 46))
        return (f'<defs><radialGradient id="bg" cx="0.7" cy="0.35" r="1"><stop offset="0" stop-color="#2a1b5e"/><stop offset="0.55" stop-color="#0d1233"/><stop offset="1" stop-color="#04060f"/></radialGradient></defs>'
                f'<rect width="{w}" height="{h}" fill="url(#bg)"/><circle cx="{w * 0.2}" cy="{h * 0.28}" r="{h * 0.2}" fill="#5b3fa8" opacity="0.18"/>{stars}')
    if setting == "night":
        stars = "".join(f'<circle cx="{(i * 137) % w}" cy="{(i * 71) % int(h * 0.7)}" r="{1.5 + (i % 3)}" fill="#e2e8f0" opacity="0.7"/>' for i in range(1, 30))
        return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#1e3a5f"/></linearGradient></defs>'
                f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{stars}<rect y="{floor_y}" width="{w}" height="{h - floor_y}" fill="#0b1220"/>')
    if setting == "city":
        towers = "".join(f'<rect x="{x}" y="{floor_y - th}" width="{tw}" height="{th}" fill="#b6c8e0" opacity="0.75"/>' for x, tw, th in
                         ((w * 0.02, w * 0.09, h * 0.38), (w * 0.12, w * 0.07, h * 0.52), (w * 0.2, w * 0.1, h * 0.3), (w * 0.72, w * 0.09, h * 0.45), (w * 0.82, w * 0.07, h * 0.33), (w * 0.9, w * 0.09, h * 0.5)))
        return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9ad1ff"/><stop offset="1" stop-color="#e4f2ff"/></linearGradient></defs>'
                f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{towers}<rect y="{floor_y}" width="{w}" height="{h - floor_y}" fill="#8fa5be"/>')
    if setting == "cloud":
        puff = lambda x, y, s: f'<g transform="translate({x} {y}) scale({s})" fill="#ffffff" opacity="0.9"><ellipse rx="60" ry="26"/><ellipse cx="-30" cy="-14" rx="30" ry="24"/><ellipse cx="22" cy="-20" rx="36" ry="28"/></g>'
        return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6fb7ff"/><stop offset="1" stop-color="#d9efff"/></linearGradient></defs>'
                f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{puff(w * 0.15, h * 0.2, 1.3)}{puff(w * 0.78, h * 0.14, 1.0)}{puff(w * 0.55, h * 0.88, 1.6)}{puff(w * 0.1, h * 0.92, 1.2)}')
    return (f'<rect width="{w}" height="{h}" fill="#eef3fb"/><rect x="{w * 0.04}" y="{h * 0.08}" width="{w * 0.2}" height="{h * 0.22}" rx="10" fill="#cfe0f7" opacity="0.8"/>'
            f'<rect x="{w * 0.76}" y="{h * 0.1}" width="{w * 0.18}" height="{h * 0.18}" rx="10" fill="#cfe0f7" opacity="0.8"/><rect y="{floor_y}" width="{w}" height="{h - floor_y}" fill="#c9d6e8"/>')


def positions(n, layout, aspect_key):
    """[(x, y)] icon centres as percentages of the picture, for n items (1 to 4)."""
    if aspect_key == "1:1":
        table = {1: [(50, 50)], 2: [(50, 30), (50, 72)], 3: [(30, 28), (72, 42), (38, 76)], 4: [(28, 26), (72, 26), (28, 72), (72, 72)]}
        return table[n]
    if layout == "hub" and n >= 3:
        return [(50, 48), (17, 52), (83, 52)] if n == 3 else [(50, 44), (16, 50), (84, 50), (50, 78)]
    if layout == "triangle" and n == 3:
        return [(50, 28), (22, 68), (78, 68)]
    xs = {1: [50], 2: [30, 70], 3: [18, 50, 82], 4: [13, 38, 63, 88]}[n]
    return [(x, 52) for x in xs]


def _arrow(x1, y1, x2, y2, r, dashed=False, color=OUT):
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    sx, sy, ex, ey = x1 + ux * r, y1 + uy * r, x2 - ux * (r + 6), y2 - uy * (r + 6)
    head = f"{ex:.1f},{ey:.1f} {ex - ux * 30 - uy * 16:.1f},{ey - uy * 30 + ux * 16:.1f} {ex - ux * 30 + uy * 16:.1f},{ey - uy * 30 - ux * 16:.1f}"
    dash = ' stroke-dasharray="4 14"' if dashed else ""
    return (f'<path d="M{sx:.1f} {sy:.1f} L{ex - ux * 24:.1f} {ey - uy * 24:.1f}" stroke="{color}" stroke-width="12" stroke-linecap="round"{dash} fill="none"/>'
            f'<polygon points="{head}" fill="{color}" stroke="{color}" stroke-width="6" stroke-linejoin="round"/>')


def _sizes(n, aspect_key, w, h):
    base = min(w, h) * (0.37 if aspect_key == "1:1" else 0.5)
    return base * (0.84 if n == 4 else 1.0)


def _item_inner(item, cx, cy, size):
    scale = size / 200
    c = COLORS[item["color"]]
    shadow = f'<ellipse cx="{cx:.1f}" cy="{cy + size * 0.47:.1f}" rx="{size * 0.34:.1f}" ry="{size * 0.06:.1f}" fill="#000" opacity="0.13"/>'
    if item.get("many"):
        body = "".join(f'<g transform="translate({cx + dx * scale:.1f} {cy + dy * scale:.1f}) scale({scale * 0.72:.3f})">{icon(item["kind"])(c, item.get("mood", "neutral"))}</g>'
                       for dx, dy in ((-46, -22), (46, -22), (0, 24)))
    else:
        body = f'<g transform="translate({cx:.1f} {cy:.1f}) scale({scale:.3f})">{icon(item["kind"])(c, item.get("mood", "neutral"))}</g>'
    mark = ""
    if item.get("mark"):
        mark = f'<g transform="translate({cx + size * 0.34:.1f} {cy - size * 0.34:.1f}) scale({scale * 0.46:.3f})">{ICONS[item["mark"]](c)}</g>'
    return shadow + body + mark


def _wrap(inner, w, h):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">{inner}</svg>'


DARK_SETTINGS = ("night", "space")


def compose_layers(spec, aspect_key="16:9", canvas=None, anchor=None, big=1.0):
    """The scene as separate transparent layers, so the video can bring each icon in when the narrator reaches it:
    {"background": svg, "items": [svg per item], "links": [{"svg", "from", "to"}] (1-based item numbers),
     "centres": [(x, y) percent], "badges": [(x, y) percent: the top-left corner of each icon, so a badge never hides it]}
    `canvas` (width, height), `anchor` (x, y percent of the one icon) and `big` (a size factor) are for a background picture."""
    w, h = canvas or ((768, 768) if aspect_key == "1:1" else (1024, 512))
    items = spec["items"]
    pos = [anchor] if anchor else positions(len(items), spec.get("layout", "row"), aspect_key)
    size = _sizes(len(items), aspect_key, w, h) * big
    centres = [(w * x / 100, h * y / 100) for x, y in pos]
    return {
        "background": _wrap(background(spec.get("setting", "office"), w, h), w, h),
        "items": [_wrap(_item_inner(it, cx, cy, size), w, h) for it, (cx, cy) in zip(items, centres)],
        "links": [{"svg": _wrap(_arrow(*centres[l["from"] - 1], *centres[l["to"] - 1], size * 0.56, l.get("dashed", False),
                                                "#e2e8f0" if spec.get("setting") in DARK_SETTINGS else OUT), w, h), "from": l["from"], "to": l["to"]}
                  for l in spec.get("links", [])],
        "centres": [(round(x, 1), round(y, 1)) for x, y in pos],
        "badges": [(round((cx - size * 0.40) / w * 100, 1), round((cy - size * 0.42) / h * 100, 1)) for cx, cy in centres],
    }


def compose(spec, aspect_key="16:9"):
    """(svg text, [(x, y) of each item's badge, percent of the picture]): the whole scene as one picture (the layers drawn together)."""
    layered = compose_layers(spec, aspect_key)
    w, h = (768, 768) if aspect_key == "1:1" else (1024, 512)
    inner = lambda svg: svg[svg.index(">") + 1:svg.rindex("</svg>")]
    parts = [inner(layered["background"])] + [inner(l["svg"]) for l in layered["links"]] + [inner(i) for i in layered["items"]]
    return _wrap("".join(parts), w, h), layered["badges"]
