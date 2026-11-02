"""Title-page decorations of referat templates 101–200 (same rules as decor.py: millimetres on an
A4 page, shapes only, nothing under the text blocks except light tints)."""
from __future__ import annotations

import math
from typing import Dict


def layouts(p: Dict[str, str], v: int, rnd) -> Dict[str, str]:
    from services.referat.decor import _laurel, _leaf, _star
    a, a2, soft, ink = p["accent"], p["accent2"], p["soft"], p["ink"]
    L: Dict[str, str] = {}

    # ---- ribbons, bookmarks, paper
    L["ribbon"] = (f'<path d="M14 82 H40 L34 90 L40 98 H14Z" fill="{a2}"/><path d="M196 82 H170 L176 90 L170 98 H196Z" fill="{a2}"/>'
                   f'<rect x="30" y="78" width="150" height="20" fill="{a}"/>'
                   f'<path d="M30 98 L40 102 V98Z M180 98 L170 102 V98Z" fill="{ink}" opacity=".45"/>'
                   f'<rect x="36" y="87.4" width="138" height="0.6" fill="{soft}" opacity=".6"/>'
                   f'<rect x="10" y="10" width="190" height="277" fill="none" stroke="{a}" stroke-width="0.35"/>')
    L["bookmark"] = (f'<path d="M160 0 H184 V92 L172 82 L160 92Z" fill="{a}"/>'
                     f'<path d="M166 0 H178 V70 L172 64 L166 70Z" fill="{a2}" opacity=".55"/>'
                     f'<rect x="22" y="282" width="166" height="0.5" fill="{a}"/>')
    L["fold"] = (f'<path d="M158 0 H210 V52Z" fill="{soft}"/><path d="M158 0 L210 52 L170 40Z" fill="{a}" opacity=".9"/>'
                 f'<path d="M158 0 L170 40 L210 52" fill="none" stroke="{ink}" stroke-opacity=".15" stroke-width="0.6"/>'
                 f'<rect x="14" y="14" width="140" height="0.7" fill="{a}"/><rect x="14" y="14" width="0.7" height="268" fill="{a}"/>'
                 f'<rect x="14" y="282" width="182" height="0.7" fill="{a}"/><rect x="195.3" y="60" width="0.7" height="222" fill="{a}"/>')
    L["kraft"] = ('<rect width="210" height="297" fill="#EFE3CC"/>'
                  + "".join(f'<circle cx="{rnd.uniform(0, 210):.1f}" cy="{rnd.uniform(0, 297):.1f}" r="{rnd.uniform(.2, .6):.2f}" '
                            f'fill="#8B6B3E" opacity=".25"/>' for _ in range(160))
                  + f'<path d="M0 70 C60 64 140 76 210 68" stroke="{a}" stroke-width="0.9" fill="none"/>'
                  f'<path d="M150 62 l26 0 l8 8 l-8 8 l-26 0z" fill="#FFF8EA" stroke="{a}" stroke-width="0.5"/>'
                  f'<circle cx="155" cy="70" r="1.6" fill="none" stroke="{a}" stroke-width="0.5"/>'
                  f'<rect x="12" y="12" width="186" height="273" fill="none" stroke="#8B6B3E" stroke-width="0.4" stroke-dasharray="2 1.5"/>')
    L["parchment"] = (f'<rect width="210" height="297" fill="#F6ECD4"/>'
                      f'<rect width="210" height="297" fill="none" stroke="#B88A4A" stroke-width="14" opacity=".25" filter="url(#blur)"/>'
                      f'<rect x="16" y="16" width="178" height="265" fill="none" stroke="{a}" stroke-width="0.6"/>'
                      f'<path d="M80 100 H130" stroke="{a2}" stroke-width="0.5"/>' + _star(105, 100, 3, a, 0.5, fill=a + "55"))
    L["scroll"] = (f'<path d="M30 104 H180 V176 H30Z" fill="{soft}"/>'
                   f'<path d="M30 104 c-10 0 -10 10 0 10 M180 104 c10 0 10 10 0 10 M30 176 c-10 0 -10 -10 0 -10 M180 176 c10 0 10 -10 0 -10" '
                   f'fill="none" stroke="{a}" stroke-width="0.8"/>'
                   f'<rect x="24" y="100" width="6" height="80" rx="3" fill="{a}"/><rect x="180" y="100" width="6" height="80" rx="3" fill="{a}"/>'
                   f'<rect x="20" y="20" width="170" height="0.5" fill="{a2}"/>')
    L["envelope"] = ("".join(f'<rect x="{x}" y="0" width="7" height="5" fill="{a if (x // 10) % 2 else a2}" transform="skewX(-30)"/>'
                             for x in range(0, 380, 10))
                     + "".join(f'<rect x="{x}" y="292" width="7" height="5" fill="{a2 if (x // 10) % 2 else a}" transform="skewX(-30)"/>'
                               for x in range(160, 540, 10))
                     + "".join(f'<rect x="0" y="{y}" width="5" height="7" fill="{a if (y // 10) % 2 else a2}"/>' for y in range(10, 290, 10))
                     + "".join(f'<rect x="205" y="{y}" width="5" height="7" fill="{a2 if (y // 10) % 2 else a}"/>' for y in range(10, 290, 10))
                     + f'<rect x="156" y="16" width="34" height="40" fill="none" stroke="{a}" stroke-width="0.6" stroke-dasharray="1.4 1"/>'
                     f'<circle cx="166" cy="40" r="11" fill="none" stroke="{a2}" stroke-width="0.5"/>')
    L["ticket"] = (f'<rect x="20" y="40" width="170" height="240" rx="6" fill="{soft}"/>'
                   f'<circle cx="20" cy="190" r="7" fill="#ffffff"/><circle cx="190" cy="190" r="7" fill="#ffffff"/>'
                   f'<path d="M30 190 H180" stroke="{a}" stroke-width="0.6" stroke-dasharray="2 2"/>'
                   f'<rect x="20" y="40" width="170" height="10" rx="5" fill="{a}"/>'
                   + "".join(f'<rect x="{150 + i * 2.2:.1f}" y="262" width="{1 if i % 3 else 1.6}" height="12" fill="{ink}" opacity=".7"/>'
                             for i in range(14)))

    # ---- frames
    L["round_frame"] = (f'<rect x="12" y="12" width="186" height="273" rx="14" fill="none" stroke="{a}" stroke-width="3.2"/>'
                        f'<rect x="17.5" y="17.5" width="175" height="262" rx="10" fill="none" stroke="{a2}" stroke-width="0.5"/>')
    L["offset_frame"] = (f'<rect x="22" y="22" width="174" height="261" fill="{soft}"/>'
                         f'<rect x="14" y="14" width="174" height="261" fill="none" stroke="{a}" stroke-width="1.1"/>'
                         f'<rect x="14" y="14" width="22" height="22" fill="{a}"/>')
    L["corner_lines"] = "".join(
        f'<path d="M{x0} {y0 + sy * (24 + k * 5)} V{y0} H{x0 + sx * (24 + k * 5)}" fill="none" stroke="{a if k == 0 else a2}" '
        f'stroke-width="{1.2 if k == 0 else 0.4}" transform="translate({sx * k * 2.5} {sy * k * 2.5})"/>'
        for x0, y0, sx, sy in ((12, 12, 1, 1), (198, 12, -1, 1), (12, 285, 1, -1), (198, 285, -1, -1)) for k in range(3))
    L["columns"] = "".join(
        f'<rect x="{x}" y="40" width="14" height="230" fill="{soft}"/>'
        + "".join(f'<rect x="{x + 2 + i * 3.4:.1f}" y="46" width="1" height="218" fill="{a2}" opacity=".7"/>' for i in range(3))
        + f'<rect x="{x - 3}" y="32" width="20" height="8" fill="{a}"/><rect x="{x - 3}" y="270" width="20" height="8" fill="{a}"/>'
        for x in (10, 186)) + f'<path d="M7 28 H203 L105 12Z" fill="none" stroke="{a}" stroke-width="0.8"/>'
    L["diamond"] = (f'<rect x="55" y="90" width="100" height="100" fill="{soft}" transform="rotate(45 105 140)"/>'
                    f'<path d="M105 62 L183 140 L105 218 L27 140Z" fill="none" stroke="{a}" stroke-width="0.35" stroke-dasharray="1.2 1.6"/>'
                    f'<rect x="10" y="10" width="190" height="277" fill="none" stroke="{a2}" stroke-width="0.4"/>')
    L["label"] = (f'<path d="M40 104 H170 L182 116 L170 128 H40 L28 116Z" fill="{a}"/>'
                  f'<path d="M44 108 H168 L176 116 L168 124 H44 L36 116Z" fill="none" stroke="{soft}" stroke-width="0.5"/>'
                  f'<rect x="0" y="0" width="210" height="5" fill="{a2}"/><rect x="0" y="292" width="210" height="5" fill="{a2}"/>')

    # ---- geometric
    cl = []
    for i in range(7):
        cl.append(f'<circle cx="{rnd.uniform(120, 215):.1f}" cy="{rnd.uniform(225, 300):.1f}" r="{rnd.uniform(10, 34):.1f}" '
                  f'fill="{(a, a2, soft)[i % 3]}" opacity="{rnd.uniform(.35, .7):.2f}"/>')
    L["bubbles"] = "".join(cl) + "".join(
        f'<circle cx="{rnd.uniform(130, 205):.1f}" cy="{rnd.uniform(150, 215):.1f}" r="{rnd.uniform(1.5, 4):.1f}" fill="none" '
        f'stroke="{a2}" stroke-width="0.5"/>' for _ in range(9))
    L["dot_corners"] = "".join(
        f'<circle cx="{x0 + sx * i * 5}" cy="{y0 + sy * j * 5}" r="{max(0.3, 1.5 - (i + j) * 0.12):.2f}" fill="{a if (i + j) % 2 else a2}"/>'
        for x0, y0, sx, sy in ((198, 12, -1, 1), (198, 285, -1, -1)) for i in range(9) for j in range(9) if i + j < 10)
    L["zigzag"] = "".join(
        f'<path d="M0 {y} ' + " ".join(f"L{x + 5} {y + (4 if k % 2 == 0 else 0)} L{x + 10} {y}" for k, x in enumerate(range(0, 210, 10)))
        + f'" fill="none" stroke="{c}" stroke-width="{w}"/>'
        for y, c, w in ((10, a, 1.4), (16, a2, 0.6), (277, a2, 0.6), (283, a, 1.4)))
    L["chevrons"] = "".join(
        f'<path d="M8 {40 + i * 22} L22 {50 + i * 22} L36 {40 + i * 22}" fill="none" stroke="{a if i % 2 else a2}" stroke-width="3.2" '
        f'stroke-linejoin="round" opacity="{1 - i * 0.07:.2f}"/>' for i in range(11))
    L["memphis"] = (f'<path d="M14 30 q5 -6 10 0 t10 0 t10 0" fill="none" stroke="{a}" stroke-width="1.4"/>'
                    f'<polygon points="180,22 194,40 166,40" fill="{a2}"/><circle cx="186" cy="64" r="5" fill="none" stroke="{a}" stroke-width="1.2"/>'
                    f'<rect x="16" y="250" width="16" height="16" fill="{a}" transform="rotate(20 24 258)"/>'
                    f'<path d="M160 268 q5 -6 10 0 t10 0 t10 0" fill="none" stroke="{a2}" stroke-width="1.4"/>'
                    + "".join(f'<circle cx="{x}" cy="{y}" r="1" fill="{ink}"/>' for x, y in ((40, 60), (46, 66), (52, 60), (170, 230), (176, 236), (182, 230)))
                    + f'<path d="M190 120 l6 6 m0 -6 l-6 6" stroke="{a}" stroke-width="1.2"/><path d="M14 150 l6 6 m0 -6 l-6 6" stroke="{a2}" stroke-width="1.2"/>')
    L["swiss"] = ("".join(f'<rect x="{x}" y="0" width="0.25" height="297" fill="{ink}" opacity=".18"/>' for x in range(22, 200, 22))
                  + f'<rect x="22" y="70" width="44" height="30" fill="{a}"/>'
                  f'<rect x="154" y="256" width="34" height="22" fill="{a2}"/>'
                  f'<rect x="22" y="104" width="166" height="0.8" fill="{ink}"/>')
    L["steps"] = "".join(f'<rect x="{120 + i * 15}" y="{276 - (i + 1) * 13}" width="13" height="{(i + 1) * 13 + 21}" '
                         f'fill="{a if i == 5 else a2}" opacity="{0.35 + i * 0.11:.2f}"/>' for i in range(6)) + \
        f'<path d="M118 262 L210 196" stroke="{a}" stroke-width="0.9" stroke-dasharray="2 1.5"/>'
    pts = [(14 + i * 15, 260 - (rnd.uniform(0, 30) + i * 3.2)) for i in range(13)]
    L["line_chart"] = ("".join(f'<rect x="12" y="{y}" width="186" height="0.25" fill="{ink}" opacity=".2"/>' for y in range(232, 282, 10))
                       + f'<path d="M{pts[0][0]} {pts[0][1]:.1f} ' + " ".join(f"L{x} {y:.1f}" for x, y in pts[1:])
                       + f'" fill="none" stroke="{a}" stroke-width="1.3"/>'
                       + "".join(f'<circle cx="{x}" cy="{y:.1f}" r="1.3" fill="#fff" stroke="{a2}" stroke-width="0.7"/>' for x, y in pts[::3]))
    ang, pie = -90.0, []
    for share, col in ((.42, a), (.26, a2), (.18, soft), (.14, ink)):
        a0, a1 = math.radians(ang), math.radians(ang + share * 360)
        large = 1 if share > .5 else 0
        pie.append(f'<path d="M172 52 L{172 + 26 * math.cos(a0):.2f} {52 + 26 * math.sin(a0):.2f} A26 26 0 {large} 1 '
                   f'{172 + 26 * math.cos(a1):.2f} {52 + 26 * math.sin(a1):.2f}Z" fill="{col}" opacity=".9"/>')
        ang += share * 360
    L["pie"] = "".join(pie) + '<circle cx="172" cy="52" r="11" fill="#ffffff"/>' + \
        f'<rect x="22" y="284" width="166" height="0.6" fill="{a}"/>'
    L["pixels"] = "".join(f'<rect x="{x}" y="{y}" width="4" height="4" fill="{(a, a2)[(x + y) // 4 % 2]}"/>'
                          for x in range(8, 202, 4) for y in (8, 285) if (x // 4) % 3) + \
        "".join(f'<rect x="{x}" y="{y}" width="4" height="4" fill="{(a, a2)[(y // 4) % 2]}"/>' for x in (8, 198) for y in range(12, 285, 4) if (y // 4) % 3)
    L["rings"] = "".join(f'<circle cx="{60 + i * 22}" cy="{268 + (i % 2) * 6}" r="11" fill="none" stroke="{(a, a2)[i % 2]}" stroke-width="1.6"/>'
                         for i in range(5))
    flow = []
    for i in range(12):
        y = 230 + i * 4
        flow.append(f'<path d="M0 {y} C60 {y - 30} 120 {y + 30} 210 {y - 12}" fill="none" stroke="{a if i % 3 == 0 else a2}" '
                    f'stroke-width="{0.9 if i % 3 == 0 else 0.4}" opacity="{0.9 - i * 0.05:.2f}"/>')
    L["flow"] = "".join(flow)
    blobs = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity=".55" filter="url(#blur)"/>'
                    for x, y, r, c in ((30, 40, 40, a2), (190, 90, 46, soft), (40, 260, 52, soft), (180, 270, 40, a2)))
    L["mesh"] = f'<rect width="210" height="297" fill="#ffffff"/>{blobs}'

    # ---- science and school
    L["circuit"] = "".join(
        f'<path d="{d}" fill="none" stroke="{a2}" stroke-width="0.7"/>' for d in (
            "M0 30 H30 L40 40 H70", "M0 44 H22 L30 52 V70", "M180 0 V24 L170 34 V54", "M196 0 V40 H210",
            "M0 262 H40 L52 250 H80", "M210 250 H170 L160 260 V297", "M150 297 V276 H130")) + \
        "".join(f'<circle cx="{x}" cy="{y}" r="1.8" fill="#fff" stroke="{a}" stroke-width="0.8"/>'
                for x, y in ((70, 40), (30, 70), (170, 54), (80, 250), (130, 276), (196, 40)))
    dna = []
    for i in range(26):
        y = 20 + i * 10
        x1 = 22 + 9 * math.sin(i * 0.6)
        x2 = 22 - 9 * math.sin(i * 0.6)
        dna.append(f'<path d="M{x1:.1f} {y} L{x2:.1f} {y}" stroke="{soft if abs(x1 - x2) > 4 else a2}" stroke-width="1"/>')
        dna.append(f'<circle cx="{x1:.1f}" cy="{y}" r="1.4" fill="{a}"/><circle cx="{x2:.1f}" cy="{y}" r="1.4" fill="{a2}"/>')
    L["dna"] = "".join(dna)
    L["atom"] = ("".join(f'<ellipse cx="172" cy="56" rx="30" ry="10" fill="none" stroke="{a if k == 0 else a2}" stroke-width="0.8" '
                         f'transform="rotate({k * 60} 172 56)"/>' for k in range(3))
                 + f'<circle cx="172" cy="56" r="4.5" fill="{a}"/><circle cx="202" cy="56" r="1.8" fill="{a2}"/>'
                 f'<rect x="22" y="282" width="166" height="0.6" fill="{a}"/>')
    topo = []
    for k in range(7):
        r = 14 + k * 9
        topo.append(f'<path d="M{172 - r} 297 C{172 - r} {240 - r * .6:.1f} {172 + r * .6:.1f} {230 - r * .8:.1f} {210 + r * .3:.1f} {250 - r * .9:.1f}" '
                    f'fill="none" stroke="{a if k % 3 == 0 else a2}" stroke-width="{0.7 if k % 3 == 0 else 0.35}" opacity=".8"/>')
    L["contours"] = "".join(topo)
    rose = []
    for k in range(8):
        ang = math.radians(k * 45)
        ln = 22 if k % 2 == 0 else 12
        x, y = 172 + ln * math.sin(ang), 250 - ln * math.cos(ang)
        rose.append(f'<path d="M172 250 L{x:.1f} {y:.1f}" stroke="{a if k % 2 == 0 else a2}" stroke-width="{1.4 if k % 2 == 0 else 0.6}"/>')
    L["compass"] = (f'<circle cx="172" cy="250" r="26" fill="none" stroke="{a2}" stroke-width="0.5"/>'
                    f'<circle cx="172" cy="250" r="20" fill="none" stroke="{a}" stroke-width="0.3" stroke-dasharray="1 1.5"/>'
                    + "".join(rose) + f'<polygon points="172,226 175,250 172,254 169,250" fill="{a}"/>'
                    f'<rect x="12" y="12" width="186" height="273" fill="none" stroke="{a}" stroke-width="0.35"/>')
    L["globe"] = (f'<circle cx="182" cy="40" r="42" fill="{soft}"/>'
                  + "".join(f'<ellipse cx="182" cy="40" rx="{42 * abs(math.cos(math.radians(k * 30))):.1f}" ry="42" fill="none" '
                            f'stroke="{a2}" stroke-width="0.4"/>' for k in range(1, 6))
                  + "".join(f'<path d="M{182 - 42 * math.cos(math.asin(t)):.1f} {40 + 42 * t:.1f} H{182 + 42 * math.cos(math.asin(t)):.1f}" '
                            f'stroke="{a2}" stroke-width="0.4"/>' for t in (-.6, -.3, 0, .3, .6))
                  + f'<circle cx="182" cy="40" r="42" fill="none" stroke="{a}" stroke-width="0.9"/>')
    L["puzzle"] = "".join(
        f'<path d="M{x} {y} h10 a4 4 0 1 1 8 0 h10 v10 a4 4 0 1 0 0 8 v10 h-28z" fill="{c}" opacity=".85"/>'
        for x, y, c in ((0, 0, a), (28, 0, a2), (0, 28, soft), (182, 269, a), (154, 269, a2), (182, 241, soft)))
    L["speech"] = (f'<path d="M150 20 h44 a6 6 0 0 1 6 6 v20 a6 6 0 0 1 -6 6 h-30 l-8 8 v-8 h-6 a6 6 0 0 1 -6 -6 v-20 a6 6 0 0 1 6 -6z" fill="{a}"/>'
                   f'<path d="M150 250 h40 a6 6 0 0 1 6 6 v16 a6 6 0 0 1 -6 6 h-8 v8 l-8 -8 h-24 a6 6 0 0 1 -6 -6 v-16 a6 6 0 0 1 6 -6z" fill="{a2}"/>'
                   + "".join(f'<circle cx="{164 + i * 8}" cy="36" r="1.6" fill="#fff"/>' for i in range(3))
                   + '<rect x="158" y="258" width="26" height="1.5" rx=".7" fill="#fff"/><rect x="158" y="264" width="18" height="1.5" rx=".7" fill="#fff"/>')
    L["pencil"] = (f'<g transform="rotate(-8 105 270)"><rect x="30" y="264" width="130" height="10" fill="{a2}"/>'
                   f'<rect x="30" y="264" width="130" height="3.3" fill="#ffffff" opacity=".25"/>'
                   f'<rect x="22" y="264" width="8" height="10" fill="{a}"/><rect x="14" y="264" width="8" height="10" fill="#F9A8D4"/>'
                   f'<polygon points="160,264 176,269 160,274" fill="#F3D9B1"/><polygon points="171,267.5 176,269 171,270.5" fill="{ink}"/></g>'
                   f'<rect x="22" y="24" width="166" height="0.5" fill="{a}"/>')
    L["books"] = "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="9" rx="1" fill="{c}"/><rect x="{x + 3}" y="{y + 3.5}" width="{w - 10}" height="0.8" fill="#fff" opacity=".6"/>'
        for x, y, w, c in ((14, 274, 62, a), (18, 265, 54, a2), (12, 256, 58, ink), (20, 247, 48, a))) + \
        f'<rect x="14" y="282.5" width="182" height="0.8" fill="{a}"/>'
    L["cap"] = (f'<polygon points="105,62 140,74 105,86 70,74" fill="{a}"/>'
                f'<path d="M84 79 V90 C94 98 116 98 126 90 V79 L105 86Z" fill="{a}" opacity=".85"/>'
                f'<path d="M140 74 V92" stroke="{a2}" stroke-width="0.9"/><circle cx="140" cy="94" r="2" fill="{a2}"/>'
                + _laurel(105, 82, 26, a2, -1) + _laurel(105, 82, 26, a2, 1)
                + f'<rect x="10" y="10" width="190" height="277" fill="none" stroke="{a}" stroke-width="0.4"/>')
    L["piano"] = ('<rect x="0" y="266" width="210" height="31" fill="#ffffff"/>'
                  + "".join(f'<rect x="{x}" y="266" width="10" height="31" fill="none" stroke="{ink}" stroke-width="0.3"/>' for x in range(0, 210, 10))
                  + "".join(f'<rect x="{x + 7}" y="266" width="6" height="19" fill="{a}"/>' for x in range(0, 210, 10) if (x // 10) % 7 not in (2, 6))
                  + f'<rect x="0" y="263" width="210" height="3" fill="{a2}"/>')
    L["film"] = "".join(
        f'<rect x="0" y="{y}" width="210" height="18" fill="{ink}"/>'
        + "".join(f'<rect x="{x}" y="{y + 3}" width="5" height="4" rx="1" fill="#ffffff"/><rect x="{x}" y="{y + 11}" width="5" height="4" rx="1" fill="#ffffff"/>'
                  for x in range(4, 210, 10))
        for y in (0, 279)) + f'<rect x="0" y="18" width="210" height="1.2" fill="{a}"/><rect x="0" y="277.8" width="210" height="1.2" fill="{a}"/>'
    L["bricks"] = "".join(f'<rect x="{x + (8 if r % 2 else 0)}" y="{258 + r * 8}" width="15" height="7" fill="{(a, a2)[(x // 16 + r) % 2]}" opacity="{.55 + .15 * (r % 3):.2f}"/>'
                          for r in range(5) for x in range(-16, 210, 16))

    # ---- national and oriental
    ikat = []
    for i in range(14):
        y = i * 22
        ikat.append(f'<path d="M14 {y} C26 {y + 5} 26 {y + 17} 14 {y + 22} C2 {y + 17} 2 {y + 5} 14 {y}Z" fill="{a if i % 2 else a2}"/>')
        ikat.append(f'<path d="M14 {y + 6} C19 {y + 9} 19 {y + 13} 14 {y + 16} C9 {y + 13} 9 {y + 9} 14 {y + 6}Z" fill="{soft}"/>')
    L["ikat"] = f'<rect x="0" y="0" width="28" height="297" fill="{ink}" opacity=".08"/>' + "".join(ikat) + \
        f'<rect x="30" y="0" width="0.8" height="297" fill="{a}"/>'

    def rosette(cx, cy, r, c1, c2):
        out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c1}"/>', f'<circle cx="{cx}" cy="{cy}" r="{r * .55:.1f}" fill="{c2}"/>',
               f'<circle cx="{cx}" cy="{cy}" r="{r * .22:.1f}" fill="{c1}"/>']
        for k in range(10):
            ang = math.radians(k * 36)
            x, y = cx + r * 1.25 * math.cos(ang), cy + r * 1.25 * math.sin(ang)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * .2:.1f}" fill="{c2}"/>')
        return "".join(out)
    L["suzani"] = (rosette(18, 18, 13, a, a2) + rosette(192, 279, 13, a, a2) + rosette(192, 18, 7, a2, a) + rosette(18, 279, 7, a2, a)
                   + _leaf(40, 40, 10, 45, a2, .8) + _leaf(170, 257, 10, 225, a2, .8))
    atlas = []
    for i in range(30):
        x = i * 7
        atlas.append(f'<path d="M{x} 0 C{x + 4} 10 {x - 4} 20 {x} 30 C{x + 4} 40 {x - 4} 50 {x} 58 V0Z" fill="{(a, a2, soft, ink)[i % 4]}" '
                     f'opacity="{.85 if i % 4 != 3 else .5}"/>')
        atlas.append(f'<rect x="{x}" y="0" width="7" height="58" fill="{(a, a2, soft, ink)[i % 4]}" opacity=".55"/>')
    L["atlas"] = "".join(atlas) + f'<rect x="0" y="58" width="210" height="1.6" fill="{a}"/>'
    tiles = "".join(_star(x, y, 5, a, 0.5, fill=a2 + "66") for x in range(15, 210, 18) for y in (12, 285))
    L["tiles"] = f'<rect x="0" y="0" width="210" height="24" fill="{soft}"/><rect x="0" y="273" width="210" height="24" fill="{soft}"/>' + tiles + \
        f'<rect x="0" y="24" width="210" height="0.8" fill="{a}"/><rect x="0" y="272.2" width="210" height="0.8" fill="{a}"/>'
    domes = []
    for x, w, h in ((10, 30, 30), (42, 22, 46), (70, 40, 24), (114, 20, 56), (138, 34, 32), (176, 26, 40)):
        domes.append(f'<rect x="{x}" y="{297 - h}" width="{w}" height="{h}" fill="{a}"/>')
        domes.append(f'<path d="M{x} {297 - h} Q{x + w / 2} {297 - h - w * 0.9:.1f} {x + w} {297 - h}Z" fill="{a2}"/>')
        domes.append(f'<rect x="{x + w / 2 - 2:.1f}" y="{297 - h + 8}" width="4" height="7" rx="2" fill="{soft}"/>')
    L["domes"] = "".join(domes)

    # ---- dark pages (white text)
    stars = "".join(f'<circle cx="{rnd.uniform(0, 210):.1f}" cy="{rnd.uniform(0, 297):.1f}" r="{rnd.uniform(.15, .55):.2f}" '
                    f'fill="#ffffff" opacity="{rnd.uniform(.3, .9):.2f}"/>' for _ in range(140))
    L["night_sky"] = (f'<rect width="210" height="297" fill="{a}"/><rect width="210" height="297" fill="url(#gr)" opacity=".7"/>{stars}'
                      f'<circle cx="34" cy="252" r="13" fill="{a2}"/><circle cx="40" cy="247" r="11" fill="{a}"/>')
    L["neon"] = (f'<rect width="210" height="297" fill="#0B0B16"/>'
                 f'<rect x="14" y="14" width="182" height="269" rx="8" fill="none" stroke="{a2}" stroke-width="2.4" opacity=".35" filter="url(#blur)"/>'
                 f'<rect x="14" y="14" width="182" height="269" rx="8" fill="none" stroke="{a2}" stroke-width="0.9"/>'
                 f'<rect x="20" y="20" width="170" height="257" rx="6" fill="none" stroke="{a}" stroke-width="0.5"/>')
    L["aurora"] = (f'<rect width="210" height="297" fill="#081226"/>'
                   f'<path d="M-20 70 C40 30 90 110 230 50 L230 120 C120 160 60 90 -20 140Z" fill="{a2}" opacity=".45" filter="url(#blur)"/>'
                   f'<path d="M-20 110 C60 80 120 150 230 100 L230 150 C140 190 70 130 -20 170Z" fill="{a}" opacity=".55" filter="url(#blur)"/>'
                   + "".join(f'<circle cx="{rnd.uniform(0, 210):.1f}" cy="{rnd.uniform(0, 297):.1f}" r=".35" fill="#fff" opacity=".7"/>'
                             for _ in range(60)))
    L["stitch"] = (f'<rect x="14" y="14" width="182" height="269" rx="10" fill="none" stroke="{a}" stroke-width="0.7" stroke-dasharray="3 2"/>'
                   f'<rect x="10" y="10" width="190" height="277" rx="13" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                   + "".join(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{a2}"/><circle cx="{x - 1}" cy="{y - 1}" r=".55" fill="#fff"/>'
                             f'<circle cx="{x + 1}" cy="{y + 1}" r=".55" fill="#fff"/>' for x, y in ((24, 24), (186, 24), (24, 273), (186, 273))))
    return L
