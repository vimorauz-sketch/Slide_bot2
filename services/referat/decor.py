"""Title-page decorations of the referat templates: one SVG in millimetres (A4, 210 × 297)."""
from __future__ import annotations

import math
from typing import Dict

W, H = 210, 297


def _svg(body: str, defs: str = "") -> str:
    return (f'<svg class="decor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'preserveAspectRatio="none"><defs>{defs}</defs>{body}</svg>')


def _star(cx, cy, r, color, sw=0.45, fill="none"):
    pts = []
    for i in range(16):
        a = math.pi / 8 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.62
        pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}" stroke="{color}" stroke-width="{sw}"/>'


def _girih_corner(x, y, sx, sy, c1, c2):
    """An Uzbek-style corner: a star in a rosette, tendrils along both edges."""
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


def cover_svg(layout: str, p: Dict[str, str]) -> str:
    a, a2, soft, ink = p["accent"], p["accent2"], p["soft"], p["ink"]
    if layout == "frame":
        return _svg(f'<rect x="10" y="10" width="190" height="277" fill="none" stroke="{a}" stroke-width="0.9"/>'
                    f'<rect x="12.5" y="12.5" width="185" height="272" fill="none" stroke="{a}" stroke-width="0.25"/>')
    if layout == "double":
        sq = "".join(f'<rect x="{x - 2.2}" y="{y - 2.2}" width="4.4" height="4.4" fill="{a2}"/>'
                     for x, y in ((9, 9), (201, 9), (9, 288), (201, 288)))
        return _svg(f'<rect x="9" y="9" width="192" height="279" fill="none" stroke="{a}" stroke-width="1.8"/>'
                    f'<rect x="12.5" y="12.5" width="185" height="272" fill="none" stroke="{a2}" stroke-width="0.4"/>{sq}')
    if layout == "ornament":
        body = (f'<rect x="11" y="11" width="188" height="275" fill="none" stroke="{a}" stroke-width="0.5"/>'
                + _girih_corner(8, 8, 1, 1, a, a2) + _girih_corner(202, 8, -1, 1, a, a2)
                + _girih_corner(8, 289, 1, -1, a, a2) + _girih_corner(202, 289, -1, -1, a, a2)
                + _star(105, 92, 4.5, a2, 0.5, fill=a2 + "55")
                + f'<path d="M80 92 H97 M113 92 H130" stroke="{a2}" stroke-width="0.5"/>')
        return _svg(body)
    if layout == "band":
        return _svg(f'<rect x="0" y="0" width="46" height="297" fill="{a}"/>'
                    f'<rect x="48.5" y="0" width="1.3" height="297" fill="{a2}"/>'
                    + "".join(f'<circle cx="23" cy="{40 + i * 9}" r="1.1" fill="{soft}" opacity=".55"/>' for i in range(6)))
    if layout == "header":
        return _svg(f'<rect x="0" y="0" width="210" height="92" fill="{a}"/>'
                    f'<path d="M0 92 L210 92 L210 98 Q105 108 0 98Z" fill="{a}" opacity=".35"/>'
                    f'<rect x="0" y="287" width="210" height="10" fill="{a}"/>'
                    f'<rect x="0" y="284.5" width="210" height="1.2" fill="{a2}"/>')
    if layout == "corners":
        return _svg(f'<polygon points="0,0 78,0 0,78" fill="{a}"/><polygon points="0,0 52,0 0,52" fill="{a2}"/>'
                    f'<polygon points="0,0 26,0 0,26" fill="{soft}"/>'
                    f'<polygon points="210,297 132,297 210,219" fill="{a}"/><polygon points="210,297 158,297 210,245" fill="{a2}"/>'
                    f'<polygon points="210,297 184,297 210,271" fill="{soft}"/>')
    if layout == "minimal":
        return _svg(f'<rect x="28" y="24" width="154" height="0.5" fill="{ink}"/>'
                    f'<rect x="28" y="118" width="16" height="16" fill="{a}"/>'
                    f'<rect x="28" y="272" width="154" height="0.5" fill="{ink}"/>')
    if layout == "wave":
        return _svg(f'<path d="M0 240 C50 220 90 262 140 246 C175 235 195 232 210 236 V297 H0Z" fill="{soft}"/>'
                    f'<path d="M0 255 C45 238 95 278 150 260 C180 250 198 252 210 256 V297 H0Z" fill="{a2}" opacity=".75"/>'
                    f'<path d="M0 270 C55 256 100 292 160 276 C186 269 200 270 210 273 V297 H0Z" fill="{a}"/>'
                    f'<path d="M0 0 H210 V18 C160 30 110 6 60 20 C35 27 15 24 0 20Z" fill="{soft}"/>')
    if layout == "photo":
        return _svg(f'<rect x="0" y="0" width="210" height="34" fill="{a}" opacity=".9"/>'
                    f'<rect x="0" y="34" width="210" height="0.8" fill="{a2}"/>'
                    f'<rect x="0" y="128" width="210" height="2.2" fill="{a}"/>'
                    f'<rect x="0" y="130.2" width="210" height="0.8" fill="{a2}"/>'
                    f'<rect x="0" y="289" width="210" height="8" fill="{a}"/>')
    if layout == "dots":
        dots = []
        for i in range(36):
            x = 12 + i * (186 / 35)
            dots.append(f'<circle cx="{x:.2f}" cy="12" r="1.15" fill="{a if i % 2 else a2}"/>')
            dots.append(f'<circle cx="{x:.2f}" cy="285" r="1.15" fill="{a if i % 2 else a2}"/>')
        for i in range(1, 53):
            y = 12 + i * (273 / 53)
            dots.append(f'<circle cx="12" cy="{y:.2f}" r="1.15" fill="{a if i % 2 else a2}"/>')
            dots.append(f'<circle cx="198" cy="{y:.2f}" r="1.15" fill="{a if i % 2 else a2}"/>')
        return _svg("".join(dots))
    if layout == "diagonal":
        return _svg(f'<polygon points="120,0 210,0 210,96" fill="{a}"/><polygon points="150,0 210,0 210,62" fill="{a2}"/>'
                    f'<polygon points="0,232 0,297 96,297" fill="{a}"/><polygon points="0,262 0,297 52,297" fill="{a2}"/>'
                    f'<path d="M112 0 L210 104" stroke="{a}" stroke-width="0.6"/>')
    if layout == "emblem":
        cx, cy = 105, 104
        return _svg(f'<rect x="11" y="11" width="188" height="275" fill="none" stroke="{a}" stroke-width="0.35"/>'
                    f'<circle cx="{cx}" cy="{cy}" r="15" fill="{soft}" stroke="{a}" stroke-width="0.8"/>'
                    f'<circle cx="{cx}" cy="{cy}" r="12" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                    + _star(cx, cy, 7, a, 0.6, fill=a2 + "66")
                    + _laurel(cx, cy, 20, a2, -1) + _laurel(cx, cy, 20, a2, 1))
    if layout == "split":
        return _svg(f'<rect x="146" y="0" width="64" height="297" fill="{a}"/>'
                    f'<rect x="141" y="0" width="1.5" height="297" fill="{a2}"/>'
                    + "".join(f'<rect x="{156 + i * 9}" y="20" width="4" height="4" fill="{soft}" opacity=".5"/>' for i in range(5)))
    if layout == "arch":
        return _svg(f'<path d="M24 280 V96 A81 81 0 0 1 186 96 V280 Z" fill="none" stroke="{a}" stroke-width="1.2"/>'
                    f'<path d="M29 275 V97 A76 76 0 0 1 181 97 V275 Z" fill="none" stroke="{a2}" stroke-width="0.4"/>'
                    + _star(105, 34, 5, a2, 0.5, fill=a2 + "55"))
    return _svg("")
