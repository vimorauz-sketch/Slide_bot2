"""Title-page decorations of the referat templates: one SVG in millimetres (A4, 210 × 297).

Every layout draws only shapes (the text is laid over it by the HTML and the Word file); the
second variant of a layout is drawn mirrored (asymmetric layouts) or with its colours swapped."""
from __future__ import annotations

import math
import random
from typing import Dict

W, H = 210, 297


def _svg(body: str, defs: str = "") -> str:
    return (f'<svg class="decor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'preserveAspectRatio="none"><defs>{defs}</defs>{body}</svg>')


def _star(cx, cy, r, color, sw=0.45, fill="none", points=8):
    pts = []
    for i in range(points * 2):
        a = math.pi / points * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.62
        pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{color}" stroke-width="{sw}"/>'


def _girih_corner(x, y, sx, sy, c1, c2):
    g = [f'<g transform="translate({x},{y}) scale({sx},{sy})">',
         _star(13, 13, 9, c1, 0.6), _star(13, 13, 5, c2, 0.5, fill=c2 + "33"),
         f'<circle cx="13" cy="13" r="11.5" fill="none" stroke="{c1}" stroke-width="0.35"/>']
    for k in range(3):
        d = 27 + k * 10
        g.append(f'<path d="M{d} 6 q4 -5 8 0 q-4 5 -8 0z" fill="{c2}" opacity="{0.85 - k * 0.2:.2f}"/>')
        g.append(f'<path d="M6 {d} q-5 4 0 8 q5 -4 0 -8z" fill="{c2}" opacity="{0.85 - k * 0.2:.2f}"/>')
    g.append(f'<path d="M24 3 H62 M3 24 V62" stroke="{c1}" stroke-width="0.4"/>')
    g.append("</g>")
    return "".join(g)


def _laurel(cx, cy, r, color, side):
    out = []
    for i in range(9):
        a = math.radians(200 + i * 14) if side < 0 else math.radians(-20 - i * 14)
        x, y = cx + r * math.cos(a), cy - r * math.sin(a)
        rot = math.degrees(a) + (90 if side < 0 else -90)
        out.append(f'<ellipse cx="{x:.2f}" cy="{y:.2f}" rx="1.6" ry="3.6" fill="{color}" '
                   f'transform="rotate({rot:.1f} {x:.2f} {y:.2f})"/>')
    return "".join(out)


def _leaf(x, y, size, angle, color, opacity=1.0):
    return (f'<g transform="translate({x:.1f},{y:.1f}) rotate({angle:.0f}) scale({size / 20:.3f})" opacity="{opacity:.2f}">'
            f'<path d="M0 0 C6 -8 18 -8 24 0 C18 8 6 8 0 0Z" fill="{color}"/>'
            f'<path d="M1 0 H22" stroke="#ffffff" stroke-opacity=".45" stroke-width="0.8"/></g>')


def _wobble(x0, y0, x1, y1, rnd, amp=0.6):
    pts = []
    n = 24
    for i in range(n + 1):
        t = i / n
        pts.append(f"{x0 + (x1 - x0) * t + rnd.uniform(-amp, amp):.2f},{y0 + (y1 - y0) * t + rnd.uniform(-amp, amp):.2f}")
    return "M" + " L".join(pts)


# ---------------------------------------------------------------------- layouts
def _layouts(p: Dict[str, str], v: int):
    a, a2, soft, ink = p["accent"], p["accent2"], p["soft"], p["ink"]
    rnd = random.Random(f"{a}{v}")
    L = {}

    L["frame"] = (f'<rect x="10" y="10" width="190" height="277" fill="none" stroke="{a}" stroke-width="0.9"/>'
                  f'<rect x="12.5" y="12.5" width="185" height="272" fill="none" stroke="{a}" stroke-width="0.25"/>'
                  + (f'<rect x="10" y="10" width="190" height="6" fill="{a}"/>' if v else ""))
    sq = "".join(f'<rect x="{x - 2.2}" y="{y - 2.2}" width="4.4" height="4.4" fill="{a2}"/>'
                 for x, y in ((9, 9), (201, 9), (9, 288), (201, 288)))
    L["double"] = (f'<rect x="9" y="9" width="192" height="279" fill="none" stroke="{a}" stroke-width="1.8"/>'
                   f'<rect x="12.5" y="12.5" width="185" height="272" fill="none" stroke="{a2}" stroke-width="0.4"/>{sq}')
    L["ornament"] = (f'<rect x="11" y="11" width="188" height="275" fill="none" stroke="{a}" stroke-width="0.5"/>'
                     + _girih_corner(8, 8, 1, 1, a, a2) + _girih_corner(202, 8, -1, 1, a, a2)
                     + _girih_corner(8, 289, 1, -1, a, a2) + _girih_corner(202, 289, -1, -1, a, a2)
                     + _star(105, 92, 4.5, a2, 0.5, fill=a2 + "55")
                     + f'<path d="M80 92 H97 M113 92 H130" stroke="{a2}" stroke-width="0.5"/>')
    L["band"] = (f'<rect x="0" y="0" width="46" height="297" fill="{a}"/>'
                 f'<rect x="48.5" y="0" width="1.3" height="297" fill="{a2}"/>'
                 + "".join(f'<circle cx="23" cy="{40 + i * 9}" r="1.1" fill="{soft}" opacity=".55"/>' for i in range(6)))
    L["header"] = (f'<rect x="0" y="0" width="210" height="92" fill="{a}"/>'
                   f'<path d="M0 92 L210 92 L210 98 Q105 108 0 98Z" fill="{a}" opacity=".35"/>'
                   f'<rect x="0" y="287" width="210" height="10" fill="{a}"/>'
                   f'<rect x="0" y="284.5" width="210" height="1.2" fill="{a2}"/>')
    L["corners"] = (f'<polygon points="0,0 78,0 0,78" fill="{a}"/><polygon points="0,0 52,0 0,52" fill="{a2}"/>'
                    f'<polygon points="0,0 26,0 0,26" fill="{soft}"/>'
                    f'<polygon points="210,297 132,297 210,219" fill="{a}"/><polygon points="210,297 158,297 210,245" fill="{a2}"/>'
                    f'<polygon points="210,297 184,297 210,271" fill="{soft}"/>')
    L["minimal"] = (f'<rect x="28" y="24" width="154" height="0.5" fill="{ink}"/>'
                    f'<rect x="28" y="118" width="16" height="16" fill="{a}"/>'
                    f'<rect x="28" y="272" width="154" height="0.5" fill="{ink}"/>')
    L["wave"] = (f'<path d="M0 240 C50 220 90 262 140 246 C175 235 195 232 210 236 V297 H0Z" fill="{soft}"/>'
                 f'<path d="M0 255 C45 238 95 278 150 260 C180 250 198 252 210 256 V297 H0Z" fill="{a2}" opacity=".75"/>'
                 f'<path d="M0 270 C55 256 100 292 160 276 C186 269 200 270 210 273 V297 H0Z" fill="{a}"/>'
                 f'<path d="M0 0 H210 V18 C160 30 110 6 60 20 C35 27 15 24 0 20Z" fill="{soft}"/>')
    L["photo"] = (f'<rect x="0" y="0" width="210" height="34" fill="{a}" opacity=".9"/>'
                  f'<rect x="0" y="34" width="210" height="0.8" fill="{a2}"/>'
                  f'<rect x="0" y="128" width="210" height="2.2" fill="{a}"/>'
                  f'<rect x="0" y="130.2" width="210" height="0.8" fill="{a2}"/>'
                  f'<rect x="0" y="289" width="210" height="8" fill="{a}"/>')
    dots = []
    for i in range(36):
        x = 12 + i * (186 / 35)
        dots.append(f'<circle cx="{x:.2f}" cy="12" r="1.15" fill="{a if i % 2 else a2}"/>')
        dots.append(f'<circle cx="{x:.2f}" cy="285" r="1.15" fill="{a if i % 2 else a2}"/>')
    for i in range(1, 53):
        y = 12 + i * (273 / 53)
        dots.append(f'<circle cx="12" cy="{y:.2f}" r="1.15" fill="{a if i % 2 else a2}"/>')
        dots.append(f'<circle cx="198" cy="{y:.2f}" r="1.15" fill="{a if i % 2 else a2}"/>')
    L["dots"] = "".join(dots)
    L["diagonal"] = (f'<polygon points="120,0 210,0 210,96" fill="{a}"/><polygon points="150,0 210,0 210,62" fill="{a2}"/>'
                     f'<polygon points="0,232 0,297 96,297" fill="{a}"/><polygon points="0,262 0,297 52,297" fill="{a2}"/>'
                     f'<path d="M112 0 L210 104" stroke="{a}" stroke-width="0.6"/>')
    cx, cy = 105, 104
    L["emblem"] = (f'<rect x="11" y="11" width="188" height="275" fill="none" stroke="{a}" stroke-width="0.35"/>'
                   f'<circle cx="{cx}" cy="{cy}" r="15" fill="{soft}" stroke="{a}" stroke-width="0.8"/>'
                   f'<circle cx="{cx}" cy="{cy}" r="12" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                   + _star(cx, cy, 7, a, 0.6, fill=a2 + "66") + _laurel(cx, cy, 20, a2, -1) + _laurel(cx, cy, 20, a2, 1))
    L["split"] = (f'<rect x="146" y="0" width="64" height="297" fill="{a}"/>'
                  f'<rect x="141" y="0" width="1.5" height="297" fill="{a2}"/>'
                  + "".join(f'<rect x="{156 + i * 9}" y="20" width="4" height="4" fill="{soft}" opacity=".5"/>' for i in range(5)))
    L["arch"] = (f'<path d="M24 280 V96 A81 81 0 0 1 186 96 V280 Z" fill="none" stroke="{a}" stroke-width="1.2"/>'
                 f'<path d="M29 275 V97 A76 76 0 0 1 181 97 V275 Z" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                 + _star(105, 34, 5, a2, 0.5, fill=a2 + "55"))

    # ---- full-colour pages (white text)
    L["dark_full"] = (f'<rect width="210" height="297" fill="{a}"/>'
                      f'<rect x="12" y="12" width="186" height="273" fill="none" stroke="{a2}" stroke-width="0.6"/>'
                      f'<rect x="15" y="15" width="180" height="267" fill="none" stroke="{a2}" stroke-width="0.25" opacity=".7"/>'
                      + "".join(f'<circle cx="{105 + dx}" cy="100" r="0.9" fill="{a2}"/>' for dx in (-8, 0, 8)))
    L["gradient"] = ('<rect width="210" height="297" fill="url(#gr)"/>'
                     f'<circle cx="{180 if not v else 30}" cy="40" r="70" fill="#ffffff" opacity=".07"/>'
                     f'<circle cx="{20 if not v else 190}" cy="270" r="90" fill="#ffffff" opacity=".06"/>')
    grid = "".join(f'<path d="M{x} 0 V297" stroke="{a2}" stroke-width="{0.3 if x % 30 == 0 else 0.12}" opacity=".45"/>'
                   for x in range(0, 211, 10))
    grid += "".join(f'<path d="M0 {y} H210" stroke="{a2}" stroke-width="{0.3 if y % 30 == 0 else 0.12}" opacity=".45"/>'
                    for y in range(0, 298, 10))
    L["blueprint"] = (f'<rect width="210" height="297" fill="{a}"/>{grid}'
                      f'<rect x="14" y="14" width="182" height="269" fill="none" stroke="#ffffff" stroke-width="0.6"/>'
                      f'<circle cx="170" cy="250" r="16" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                      f'<path d="M150 250 H190 M170 230 V270" stroke="{a2}" stroke-width="0.3"/>'
                      f'<rect x="130" y="262" width="66" height="21" fill="none" stroke="#ffffff" stroke-width="0.4"/>')
    chalk = "".join(f'<path d="{_wobble(*seg, rnd)}" fill="none" stroke="{a2}" stroke-width="0.7" opacity=".85" stroke-linecap="round"/>'
                    for seg in ((14, 14, 196, 14), (196, 14, 196, 283), (196, 283, 14, 283), (14, 283, 14, 14)))
    smudges = "".join(f'<ellipse cx="{rnd.uniform(20, 190):.0f}" cy="{rnd.uniform(20, 280):.0f}" rx="{rnd.uniform(8, 24):.0f}" '
                      f'ry="{rnd.uniform(3, 8):.0f}" fill="#ffffff" opacity=".035"/>' for _ in range(14))
    L["chalk"] = (f'<rect width="210" height="297" fill="{a}"/>{smudges}{chalk}'
                  f'<rect x="0" y="287" width="210" height="10" fill="#7a5230"/>'
                  f'<rect x="60" y="284" width="16" height="3" rx="1" fill="#f8f8f0"/>')

    # ---- paper
    lines = "".join(f'<path d="M0 {y:.1f} H210" stroke="{a2}" stroke-width="0.25" opacity=".55"/>' for y in [30 + i * 8 for i in range(34)])
    holes = "".join(f'<circle cx="12" cy="{y}" r="2.8" fill="#e9e9ee" stroke="#cfcfd8" stroke-width="0.3"/>' for y in (60, 148, 236))
    L["notebook"] = (f'<rect width="210" height="297" fill="#FFFEF8"/>{lines}'
                     f'<path d="M32 0 V297" stroke="#E11D48" stroke-width="0.5" opacity=".7"/>{holes}')
    L["graph"] = ("".join(f'<path d="M{x} 0 V297" stroke="{a2}" stroke-width="{0.28 if x % 25 == 0 else 0.1}" opacity=".5"/>'
                          for x in range(0, 211, 5))
                  + "".join(f'<path d="M0 {y} H210" stroke="{a2}" stroke-width="{0.28 if y % 25 == 0 else 0.1}" opacity=".5"/>'
                            for y in range(0, 298, 5))
                  + f'<rect x="18" y="18" width="174" height="261" fill="#ffffff" opacity=".82"/>'
                    f'<rect x="18" y="18" width="174" height="261" fill="none" stroke="{a}" stroke-width="0.6"/>')

    # ---- geometric
    L["circle_big"] = (f'<circle cx="175" cy="70" r="95" fill="{soft}"/>'
                       f'<circle cx="175" cy="70" r="70" fill="none" stroke="{a2}" stroke-width="0.8"/>'
                       f'<circle cx="175" cy="70" r="38" fill="{a}"/>'
                       f'<circle cx="30" cy="282" r="40" fill="{soft}"/>')
    arcs = "".join(f'<circle cx="0" cy="297" r="{30 + i * 10}" fill="none" stroke="{a if i % 2 else a2}" '
                   f'stroke-width="{2.4 - i * 0.25:.2f}" opacity="{0.9 - i * 0.08:.2f}"/>' for i in range(7))
    L["arcs"] = arcs + f'<circle cx="0" cy="297" r="22" fill="{a}"/>'

    def hexagon(x, y, r, fill, op):
        pts = " ".join(f"{x + r * math.cos(math.radians(60 * k + 30)):.2f},{y + r * math.sin(math.radians(60 * k + 30)):.2f}" for k in range(6))
        return f'<polygon points="{pts}" fill="{fill}" opacity="{op:.2f}" stroke="#ffffff" stroke-width="0.6"/>'
    hexes = []
    for row in range(4):
        for col in range(9):
            x = col * 24.2 + (12.1 if row % 2 else 0)
            y = row * 21
            hexes.append(hexagon(x, y, 14, a if (row + col) % 3 else a2, 0.95 - row * 0.2))
    L["hexagons"] = "".join(hexes) + f'<rect x="0" y="287" width="210" height="10" fill="{a}"/>'
    tri = []
    for row in range(4):
        for col in range(12):
            x0, y0 = col * 18, row * 14
            c = [a, a2, soft][(row * 7 + col * 3 + rnd.randint(0, 2)) % 3]
            op = 1 - row * 0.2
            tri.append(f'<polygon points="{x0},{y0} {x0 + 18},{y0} {x0 + 9},{y0 + 14}" fill="{c}" opacity="{op:.2f}"/>')
            tri.append(f'<polygon points="{x0 + 9},{y0 + 14} {x0 + 18},{y0} {x0 + 27},{y0 + 14}" fill="{[a2, a, soft][(row + col) % 3]}" opacity="{op:.2f}"/>')
    L["triangles"] = "".join(tri)
    L["stripes_h"] = "".join(f'<rect x="0" y="{i * 9}" width="210" height="9" fill="{c}"/>'
                             for i, c in enumerate((a, a2, soft, a2, a))) + \
        f'<rect x="0" y="286" width="210" height="11" fill="{a}"/>'
    L["stripes_v"] = "".join(f'<rect x="{x}" y="0" width="{w}" height="297" fill="{c}"/>'
                             for x, w, c in ((0, 14, a), (16, 6, a2), (24, 3, a), (29, 1.5, a2), (33, 0.6, a)))
    L["sash"] = (f'<polygon points="120,0 160,0 210,50 210,90" fill="{a}"/>'
                 f'<polygon points="165,0 175,0 210,35 210,45" fill="{a2}"/>'
                 f'<rect x="20" y="20" width="170" height="257" fill="none" stroke="{a}" stroke-width="0.3"/>')
    spine = "".join(f'<rect x="0" y="{y}" width="40" height="1.6" fill="{a2}"/>' for y in (30, 34, 262, 266))
    L["book"] = (f'<rect x="0" y="0" width="40" height="297" fill="{a}"/>'
                 f'<rect x="40" y="0" width="3" height="297" fill="#000000" opacity=".18"/>{spine}'
                 f'<rect x="10" y="120" width="20" height="56" fill="none" stroke="{a2}" stroke-width="0.5"/>')
    gu = []
    for k in range(3):
        amp, off = 2.2, 13 + k * 1.6
        top = "M" + " L".join(f"{x:.1f},{off + amp * math.sin(x / 3.2 + k):.2f}" for x in range(off.__int__(), 211 - int(off)))
        bot = "M" + " L".join(f"{x:.1f},{297 - off + amp * math.sin(x / 3.2 + k):.2f}" for x in range(int(off), 211 - int(off)))
        lft = "M" + " L".join(f"{off + amp * math.sin(y / 3.2 + k):.2f},{y:.1f}" for y in range(int(off), 298 - int(off)))
        rgt = "M" + " L".join(f"{210 - off + amp * math.sin(y / 3.2 + k):.2f},{y:.1f}" for y in range(int(off), 298 - int(off)))
        c = a if k != 1 else a2
        gu.append("".join(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="0.3"/>' for d in (top, bot, lft, rgt)))
    L["certificate"] = "".join(gu) + _star(105, 270, 7, a2, 0.6, fill=a2 + "44", points=12)
    lace = []
    for x in range(14, 197, 7):
        lace.append(f'<path d="M{x} 14 a3.5 3.5 0 0 1 7 0" fill="none" stroke="{a}" stroke-width="0.5"/>')
        lace.append(f'<path d="M{x} 283 a3.5 3.5 0 0 0 7 0" fill="none" stroke="{a}" stroke-width="0.5"/>')
    for y in range(14, 280, 7):
        lace.append(f'<path d="M14 {y} a3.5 3.5 0 0 0 0 7" fill="none" stroke="{a}" stroke-width="0.5"/>')
        lace.append(f'<path d="M196 {y} a3.5 3.5 0 0 1 0 7" fill="none" stroke="{a}" stroke-width="0.5"/>')
    L["lace"] = "".join(lace) + f'<rect x="18" y="18" width="174" height="261" fill="none" stroke="{a2}" stroke-width="0.3"/>'
    fan = "".join(f'<path d="M105 50 L{105 + 60 * math.cos(math.radians(200 + i * 14)):.1f} {50 + 60 * math.sin(math.radians(200 + i * 14)):.1f}" '
                  f'stroke="{a2}" stroke-width="0.5"/>' for i in range(11))
    L["art_deco"] = (f'<rect width="210" height="297" fill="{soft}"/>'
                     f'<path d="M45 50 A60 60 0 0 1 165 50 Z" fill="{a}"/>{fan}'
                     f'<path d="M60 50 A45 45 0 0 1 150 50" fill="none" stroke="{a2}" stroke-width="0.8"/>'
                     f'<rect x="12" y="12" width="186" height="273" fill="none" stroke="{a}" stroke-width="0.8"/>'
                     f'<rect x="16" y="16" width="178" height="265" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                     f'<path d="M16 270 H194" stroke="{a2}" stroke-width="0.4"/>')
    L["bauhaus"] = (f'<circle cx="168" cy="240" r="40" fill="{a}"/>'
                    f'<rect x="120" y="190" width="45" height="45" fill="{a2}"/>'
                    f'<polygon points="150,297 210,297 210,230" fill="{ink}"/>'
                    f'<rect x="22" y="14" width="40" height="3" fill="{a}"/>'
                    f'<circle cx="190" cy="30" r="8" fill="{a2}"/>')
    leaves = []
    for (x, y, base) in ((0, 0, 30), (210, 0, 150), (0, 297, -30), (210, 297, 210)):
        for k in range(7):
            ang = base + rnd.uniform(-35, 35)
            leaves.append(_leaf(x + rnd.uniform(-6, 6), y + rnd.uniform(-6, 6), rnd.uniform(26, 44), ang,
                                [a, a2, a][k % 3], rnd.uniform(.55, .95)))
    L["botanical"] = "".join(leaves)
    blobs = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity="{o}"/>'
                    for x, y, r, c, o in ((20, 20, 55, a2, .18), (50, 0, 35, a, .12), (190, 280, 60, a2, .2),
                                          (160, 297, 38, a, .14), (200, 120, 25, a2, .1), (0, 200, 30, a, .08)))
    L["watercolor"] = f'<g filter="url(#blur)">{blobs}</g>'
    L["mountains"] = (f'<path d="M0 230 L40 196 L70 220 L110 178 L150 214 L180 192 L210 210 V297 H0Z" fill="{a2}" opacity=".55"/>'
                      f'<path d="M0 250 L30 228 L65 252 L100 216 L140 248 L175 226 L210 244 V297 H0Z" fill="{a}" opacity=".85"/>'
                      f'<path d="M0 270 L50 254 L90 268 L130 250 L170 266 L210 256 V297 H0Z" fill="{a}"/>'
                      f'<circle cx="160" cy="60" r="16" fill="{a2}" opacity=".5"/>')
    sky = []
    x = 0
    while x < 210:
        w = rnd.randint(9, 20)
        h = rnd.randint(25, 75)
        sky.append(f'<rect x="{x}" y="{297 - h}" width="{w}" height="{h}" fill="{a}" opacity="{rnd.uniform(.75, 1):.2f}"/>')
        for wy in range(297 - h + 5, 290, 7):
            for wx in range(x + 2, x + w - 2, 4):
                if rnd.random() < .45:
                    sky.append(f'<rect x="{wx}" y="{wy}" width="1.6" height="2.4" fill="{a2}" opacity=".7"/>')
        x += w + 1
    L["skyline"] = "".join(sky)
    rays = "".join(f'<path d="M105 297 L{105 + 400 * math.cos(math.radians(190 + i * 8)):.1f} {297 + 400 * math.sin(math.radians(190 + i * 8)):.1f} '
                   f'L{105 + 400 * math.cos(math.radians(194 + i * 8)):.1f} {297 + 400 * math.sin(math.radians(194 + i * 8)):.1f}Z" fill="{a2}" opacity=".12"/>'
                   for i in range(20))
    L["sunrays"] = rays + f'<circle cx="105" cy="297" r="46" fill="{a2}" opacity=".7"/><circle cx="105" cy="297" r="30" fill="{a}"/>'
    ht = []
    for i in range(14):
        for j in range(18):
            r = max(0, 2.6 - (i + j) * 0.12)
            if r > 0.15:
                ht.append(f'<circle cx="{210 - i * 6.2:.1f}" cy="{j * 6.2:.1f}" r="{r:.2f}" fill="{a}"/>')
    L["halftone"] = "".join(ht) + f'<rect x="0" y="282" width="210" height="15" fill="{a2}"/>'
    L["waves_top"] = (f'<path d="M0 0 H210 V60 C170 76 140 44 100 58 C60 72 30 54 0 64Z" fill="{a}"/>'
                      f'<path d="M0 64 C30 54 60 72 100 58 C140 44 170 76 210 60 V68 C170 84 140 52 100 66 C60 80 30 62 0 72Z" fill="{a2}" opacity=".7"/>'
                      f'<path d="M0 282 C60 276 140 290 210 280 V297 H0Z" fill="{soft}"/>')
    L["tab_frame"] = (f'<path d="M14 24 H74 L82 14 H196 V283 H14Z" fill="none" stroke="{a}" stroke-width="0.9"/>'
                      f'<path d="M14 24 H74 L82 14 H196" fill="none" stroke="{a2}" stroke-width="3" opacity=".6"/>'
                      f'<rect x="18" y="16" width="52" height="6" rx="1.5" fill="{a}"/>')
    L["card"] = (f'<rect width="210" height="297" fill="{a}"/>'
                 f'<rect x="24" y="34" width="162" height="236" rx="6" fill="#ffffff"/>'
                 f'<rect x="24" y="34" width="162" height="5" rx="2" fill="{a2}"/>'
                 + "".join(f'<circle cx="{30 + i * 7}" cy="{20}" r="1.4" fill="{a2}"/>' for i in range(22)))
    L["side_photo"] = (f'<rect x="82" y="0" width="2" height="297" fill="{a2}"/>'
                       f'<rect x="84" y="0" width="126" height="10" fill="{a}"/>')
    L["bottom_photo"] = (f'<rect x="0" y="168" width="210" height="2.5" fill="{a}"/>'
                         f'<rect x="0" y="0" width="210" height="8" fill="{a}"/>')
    L["circle_photo"] = (f'<circle cx="105" cy="108" r="47" fill="none" stroke="{a}" stroke-width="1.6"/>'
                         f'<circle cx="105" cy="108" r="51" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                         f'<rect x="0" y="287" width="210" height="10" fill="{a}"/>')
    L["magazine"] = (f'<rect x="0" y="0" width="210" height="10" fill="{a}"/>'
                     f'<rect x="20" y="66" width="170" height="2.2" fill="{a}"/>'
                     f'<rect x="20" y="70" width="60" height="0.8" fill="{a2}"/>'
                     f'<rect x="150" y="240" width="40" height="40" fill="{a2}"/>'
                     f'<rect x="0" y="287" width="210" height="10" fill="{ink}"/>')
    tl = f'<path d="M30 20 V277" stroke="{a}" stroke-width="0.8"/>'
    tl += "".join(f'<circle cx="30" cy="{y}" r="{3 if k % 2 else 2}" fill="{a2 if k % 2 else a}"/>'
                  for k, y in enumerate((40, 112, 150, 206, 260)))
    L["timeline"] = tl
    br = []
    for x, y, sx, sy in ((14, 14, 1, 1), (196, 14, -1, 1), (14, 283, 1, -1), (196, 283, -1, -1)):
        br.append(f'<path d="M{x} {y + 30 * sy} V{y} H{x + 30 * sx}" fill="none" stroke="{a}" stroke-width="2.4"/>')
        br.append(f'<path d="M{x + 5 * sx} {y + 20 * sy} V{y + 5 * sy} H{x + 20 * sx}" fill="none" stroke="{a2}" stroke-width="0.6"/>')
    L["brackets"] = "".join(br)
    L["double_band"] = (f'<rect x="0" y="0" width="210" height="16" fill="{a}"/><rect x="0" y="17.5" width="210" height="1.2" fill="{a2}"/>'
                        f'<rect x="0" y="281" width="210" height="16" fill="{a}"/><rect x="0" y="278.3" width="210" height="1.2" fill="{a2}"/>')
    gb = [f'<rect x="0" y="0" width="210" height="40" fill="{a}"/>']
    for i in range(12):
        gb.append(_star(9 + i * 17.5, 20, 7, a2, 0.6, fill="none"))
        gb.append(_star(9 + i * 17.5, 20, 3.5, a2, 0.4, fill=a2 + "88"))
    gb.append(f'<rect x="0" y="40" width="210" height="1.4" fill="{a2}"/><rect x="0" y="289" width="210" height="8" fill="{a}"/>')
    L["girih_band"] = "".join(gb)
    mo = []
    for i in range(8):
        for j in range(8):
            if i + j < 9 and rnd.random() < .8:
                c = [a, a2, soft][rnd.randint(0, 2)]
                mo.append(f'<rect x="{210 - (i + 1) * 9}" y="{297 - (j + 1) * 9}" width="8" height="8" fill="{c}" opacity="{1 - (i + j) * .08:.2f}"/>')
    L["mosaic"] = "".join(mo) + f'<rect x="22" y="14" width="24" height="3" fill="{a}"/>'
    ox, oy = 168, 66
    orb = "".join(f'<ellipse cx="{ox}" cy="{oy}" rx="{r}" ry="{r * .38:.1f}" fill="none" stroke="{a if k % 2 else a2}" '
                  f'stroke-width="0.5" transform="rotate(-25 {ox} {oy})"/>' for k, r in enumerate((20, 32, 44, 56)))
    orb += f'<circle cx="{ox}" cy="{oy}" r="9" fill="{a}"/>'
    orb += "".join(f'<circle cx="{ox + r * math.cos(t):.1f}" cy="{oy + r * .38 * math.sin(t):.1f}" r="2" fill="{a2}" '
                   f'transform="rotate(-25 {ox} {oy})"/>' for r, t in ((20, 1), (32, 3.6), (44, 5), (56, 2.2)))
    L["orbits"] = orb
    nodes = [(30, 230), (52, 248), (48, 272), (72, 262), (78, 238), (98, 250), (22, 258), (60, 218)]
    mol = "".join(f'<path d="M{nodes[i][0]} {nodes[i][1]} L{nodes[j][0]} {nodes[j][1]}" stroke="{a2}" stroke-width="0.8"/>'
                  for i, j in ((0, 1), (1, 2), (1, 3), (3, 4), (4, 5), (0, 6), (0, 7), (4, 7), (2, 6)))
    mol += "".join(f'<circle cx="{x}" cy="{y}" r="{4 if k % 3 == 0 else 2.6}" fill="{a if k % 2 else a2}"/>' for k, (x, y) in enumerate(nodes))
    L["molecule"] = (mol + mol.replace("<path", '<path transform="translate(210,-127.2) scale(-0.6,0.6)"')
                     .replace("<circle", '<circle transform="translate(210,-127.2) scale(-0.6,0.6)"'))
    L["stamp"] = (f'<rect x="14" y="14" width="182" height="269" fill="none" stroke="{a}" stroke-width="0.8" stroke-dasharray="3 2"/>'
                  f'<circle cx="165" cy="238" r="20" fill="none" stroke="{a2}" stroke-width="1.2"/>'
                  f'<circle cx="165" cy="238" r="15" fill="none" stroke="{a2}" stroke-width="0.4" stroke-dasharray="1 1"/>'
                  + _star(165, 238, 7, a2, 0.6, fill=a2 + "55", points=5))
    L["diag_split"] = (f'<polygon points="0,297 210,297 210,210 0,262" fill="{a}"/>'
                       f'<polygon points="0,262 210,210 210,204 0,256" fill="{a2}"/>')
    return L


def cover_svg(layout: str, p: Dict[str, str], variant: int = 0, mirror: bool = False) -> str:
    """Decoration of one title page. mirror: the layout's mirrored variant."""
    pal = dict(p)
    from services.referat.designs import LAYOUTS
    g = LAYOUTS.get(layout, {})
    if variant % 2 and not mirror:  # symmetric layouts: the second variant swaps the two colours
        text_on_colour = g.get("tone") != "dark" or g.get("city_tone") == "light" or layout in ("card", "notebook")
        if not text_on_colour:
            pal["accent"], pal["accent2"] = p["accent2"], p["accent"]
    body = _layouts(pal, variant).get(layout, "")
    defs = (f'<linearGradient id="gr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["accent"]}"/>'
            f'<stop offset="1" stop-color="{p["ink"]}"/></linearGradient>'
            '<filter id="blur"><feGaussianBlur stdDeviation="4"/></filter>')
    if mirror:
        body = f'<g transform="translate(210,0) scale(-1,1)">{body}</g>'
    return _svg(body, defs)
