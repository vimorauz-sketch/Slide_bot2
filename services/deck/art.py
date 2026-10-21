"""
Theme accent art: deterministic SVG illustrations used whenever no photo is available
(no API key, nothing found, or offline). Each theme has its own visual language so a
deck without photos still looks designed rather than empty. The slide's icon is drawn
into the composition, which ties the picture to the slide's subject.
"""
from __future__ import annotations

import base64
import math
import random
import re
from typing import Callable, Dict

from services.deck import icons


def _icon(name: str, hint: str, x: float, y: float, size: float, color: str, sw: float = 1.5, extra: str = "") -> str:
    inner = icons.inner_markup(name, hint)
    return (f'<svg x="{x - size / 2:.1f}" y="{y - size / 2:.1f}" width="{size:.1f}" height="{size:.1f}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" {extra}>{inner}</svg>')


def _wrap(w: int, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid slice"><defs>{defs}</defs>{body}</svg>')


# --------------------------------------------------------------------- 01
def circuit(w, h, c, icon, hint, rnd):
    cx, cy = w * c["_fx"], h * c["_fy"]
    s = min(w, h)
    defs = (f'<radialGradient id="bg" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="{c["bg2"]}"/><stop offset="1" stop-color="{c["bg"]}"/></radialGradient>'
            f'<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{s * 0.012:.1f}" result="b"/>'
            f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<radialGradient id="halo" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="{c["primary"]}" stop-opacity=".35"/><stop offset="1" stop-color="{c["primary"]}" stop-opacity="0"/></radialGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="url(#bg)"/>']
    step = s / 9
    for i in range(int(w / step) + 2):
        out.append(f'<line x1="{i * step:.1f}" y1="0" x2="{i * step:.1f}" y2="{h}" stroke="{c["primary"]}" stroke-opacity=".08"/>')
    for j in range(int(h / step) + 2):
        out.append(f'<line x1="0" y1="{j * step:.1f}" x2="{w}" y2="{j * step:.1f}" stroke="{c["primary"]}" stroke-opacity=".08"/>')
    traces = []
    for k in range(9):
        ang = 2 * math.pi * k / 9 + rnd.uniform(-.2, .2)
        r0 = s * 0.27
        x, y = cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)
        pts = [(x, y)]
        for _ in range(3):
            if rnd.random() < .5:
                x += math.copysign(rnd.uniform(.08, .2) * s, math.cos(ang))
            else:
                y += math.copysign(rnd.uniform(.08, .2) * s, math.sin(ang))
            pts.append((x, y))
        d = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f} {py:.1f}" for i, (px, py) in enumerate(pts))
        col = c["primary"] if k % 3 else c["secondary"]
        traces.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{s * .005:.1f}" stroke-opacity=".85"/>'
                      f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s * .011:.1f}" fill="{c["bg"]}" stroke="{col}" stroke-width="{s * .005:.1f}"/>')
    out.append(f'<g filter="url(#glow)">{"".join(traces)}</g>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{s * .42:.1f}" fill="url(#halo)"/>')
    out.append('<!--B-->')
    r = s * 0.2
    hexp = " ".join(f"{cx + r * math.cos(math.pi / 6 + i * math.pi / 3):.1f},{cy + r * math.sin(math.pi / 6 + i * math.pi / 3):.1f}" for i in range(6))
    out.append(f'<polygon points="{hexp}" fill="{c["bg"]}" fill-opacity=".85" stroke="{c["primary"]}" stroke-width="{s * .006:.1f}" filter="url(#glow)"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 1.28:.1f}" fill="none" stroke="{c["primary"]}" stroke-opacity=".5" stroke-width="{s * .003:.1f}" stroke-dasharray="{s * .01:.1f} {s * .016:.1f}"/>')
    out.append(f'<g filter="url(#glow)">{_icon(icon, hint, cx, cy, r * 1.0, c["primary"], 1.4)}</g>')
    out.append('<!--/B-->')
    for _ in range(26):
        out.append(f'<circle cx="{rnd.uniform(0, w):.1f}" cy="{rnd.uniform(0, h):.1f}" r="{rnd.uniform(1, 3) * s / 700:.1f}" fill="{c["primary"]}" fill-opacity="{rnd.uniform(.2, .7):.2f}"/>')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 02
def academic(w, h, c, icon, hint, rnd):
    cx, cy = w * (c["_fx"] + .05), h * c["_fy"]
    s = min(w, h)
    defs = f'<pattern id="dots" width="{s / 24:.1f}" height="{s / 24:.1f}" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="{s / 520:.1f}" fill="{c["primary"]}" fill-opacity=".22"/></pattern>'
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>', f'<rect width="{w}" height="{h}" fill="url(#dots)"/>']
    for i, rr in enumerate([.46, .36, .26]):
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * rr:.1f}" fill="none" stroke="{c["primary"]}" stroke-opacity="{.16 + i * .08:.2f}" stroke-width="{s * .003:.1f}"/>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .17:.1f}" fill="{c["surface"]}" stroke="{c["primary"]}" stroke-width="{s * .005:.1f}"/>')
    out.append('<!--/B-->')
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5 + .3
        x, y = cx + s * .36 * math.cos(a), cy + s * .36 * math.sin(a)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s * .022:.1f}" fill="{c["primary"] if k % 2 == 0 else c["secondary"]}"/>')
    out.append(f'<line x1="{cx - s * .46:.1f}" y1="{cy:.1f}" x2="{cx + s * .46:.1f}" y2="{cy:.1f}" stroke="{c["primary"]}" stroke-opacity=".18" stroke-width="{s * .002:.1f}"/>')
    out.append(f'<line x1="{cx:.1f}" y1="{cy - s * .46:.1f}" x2="{cx:.1f}" y2="{cy + s * .46:.1f}" stroke="{c["primary"]}" stroke-opacity=".18" stroke-width="{s * .002:.1f}"/>')
    out.append('<!--B-->')
    out.append(_icon(icon, hint, cx, cy, s * .17, c["primary"], 1.3))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 03
def aurora(w, h, c, icon, hint, rnd):
    s = min(w, h)
    defs = f'<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{s * .09:.1f}"/></filter>'
    cols = [c["primary"], c["secondary"], c["accent"], c.get("extra", c["primary"])]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>', '<g filter="url(#blur)">']
    for i, col in enumerate(cols):
        out.append(f'<ellipse cx="{w * rnd.uniform(.15, .85):.1f}" cy="{h * rnd.uniform(.15, .85):.1f}" rx="{s * rnd.uniform(.3, .45):.1f}" '
                   f'ry="{s * rnd.uniform(.22, .36):.1f}" fill="{col}" fill-opacity=".85"/>')
    out.append("</g>")
    cx, cy, r = w * c["_fx"], h * c["_fy"], s * .2
    out.append('<!--B-->')
    out.append(f'<rect x="{cx - r:.1f}" y="{cy - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" rx="{r * .32:.1f}" fill="#ffffff" fill-opacity=".14" stroke="#ffffff" stroke-opacity=".45" stroke-width="{s * .004:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.05, "#ffffff", 1.4))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 04
def editorial(w, h, c, icon, hint, rnd):
    s = min(w, h)
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    out.append(f'<circle cx="{w * .62:.1f}" cy="{h * .42:.1f}" r="{s * .34:.1f}" fill="{c["secondary"]}" fill-opacity=".9"/>')
    out.append(f'<path d="M{w * .18:.1f} {h:.1f} A{s * .36:.1f} {s * .36:.1f} 0 0 1 {w * .18 + s * .72:.1f} {h:.1f} Z" fill="{c["primary"]}"/>')
    for i in range(4):
        rr = s * (.42 + i * .05)
        out.append(f'<circle cx="{w * .62:.1f}" cy="{h * .42:.1f}" r="{rr:.1f}" fill="none" stroke="{c["accent"]}" stroke-opacity="{.55 - i * .1:.2f}" stroke-width="{s * .0025:.1f}"/>')
    out.append(f'<line x1="{w * .08:.1f}" y1="{h * .14:.1f}" x2="{w * .42:.1f}" y2="{h * .14:.1f}" stroke="{c["primary"]}" stroke-width="{s * .003:.1f}"/>')
    out.append('<!--B-->')
    out.append(_icon(icon, hint, w * .62, h * .42, s * .22, c["bg"], 1.2))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 05
def botanical(w, h, c, icon, hint, rnd):
    s = min(w, h)
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>',
           f'<circle cx="{w * .72:.1f}" cy="{h * .3:.1f}" r="{s * .22:.1f}" fill="{c["accent"]}" fill-opacity=".22"/>']
    greens = [c["primary"], c["secondary"], c["accent"], c["primary"]]
    for i in range(11):
        x, y = rnd.uniform(-.1, 1.1) * w, rnd.uniform(.25, 1.15) * h
        L = s * rnd.uniform(.28, .55)
        ang = rnd.uniform(-160, -20)
        col = greens[i % 4]
        leaf = (f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.1f})">'
                f'<path d="M0 0 C {L * .3:.1f} {-L * .22:.1f}, {L * .75:.1f} {-L * .2:.1f}, {L:.1f} 0 C {L * .75:.1f} {L * .2:.1f}, {L * .3:.1f} {L * .22:.1f}, 0 0 Z" '
                f'fill="{col}" fill-opacity="{rnd.uniform(.55, .95):.2f}"/>'
                f'<path d="M0 0 L{L * .92:.1f} 0" stroke="{c["bg2"]}" stroke-opacity=".5" stroke-width="{s * .004:.1f}"/></g>')
        out.append(leaf)
    cx, cy, r = w * c["_fx"], h * (c["_fy"] - .04), s * .15
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{c["surface"]}" fill-opacity=".95"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.1, c["primary"], 1.5))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 06
def corporate(w, h, c, icon, hint, rnd):
    s = min(w, h)
    defs = (f'<linearGradient id="col" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["secondary"]}"/><stop offset="1" stop-color="{c["primary"]}"/></linearGradient>'
            f'<linearGradient id="sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["bg2"]}"/><stop offset="1" stop-color="{c["surface"]}"/></linearGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="url(#sky)"/>']
    n = 7
    bw = w / (n + 1.5)
    base = h * .92
    pts = []
    for i in range(n):
        bh = h * (.18 + .62 * (i + 1) / n * rnd.uniform(.85, 1.05))
        x = bw * (.75 + i)
        out.append(f'<rect x="{x:.1f}" y="{base - bh:.1f}" width="{bw * .7:.1f}" height="{bh:.1f}" rx="{bw * .12:.1f}" fill="url(#col)" fill-opacity="{.35 + .65 * i / n:.2f}"/>')
        pts.append((x + bw * .35, base - bh - h * .05))
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
    out.append(f'<path d="{d}" fill="none" stroke="{c["accent"]}" stroke-width="{s * .009:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="{s * .018:.1f}" fill="{c["accent"]}"/>')
    bx, by, r = w * .3, h * .27, s * .12
    out.append('<!--B-->')
    out.append(f'<rect x="{bx - r:.1f}" y="{by - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" rx="{r * .3:.1f}" fill="{c["surface"]}" stroke="{c["primary"]}" stroke-opacity=".15"/>')
    out.append(_icon(icon, hint, bx, by, r * 1.1, c["primary"], 1.6))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 07
def neon(w, h, c, icon, hint, rnd):
    s = min(w, h)
    defs = (f'<linearGradient id="g1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["primary"]}"/><stop offset=".5" stop-color="{c["secondary"]}"/><stop offset="1" stop-color="{c["accent"]}"/></linearGradient>'
            f'<linearGradient id="g2" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["accent"]}"/><stop offset="1" stop-color="{c["secondary"]}"/></linearGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>']
    t = s * .2
    out.append(f'<path d="M{w * .05:.1f} {-h * .05:.1f} L{w * .95:.1f} {h * 1.05:.1f}" stroke="url(#g1)" stroke-width="{t:.1f}" stroke-linecap="round"/>')
    out.append(f'<path d="M{w * .95:.1f} {-h * .05:.1f} L{w * .05:.1f} {h * 1.05:.1f}" stroke="url(#g2)" stroke-width="{t:.1f}" stroke-linecap="round" stroke-opacity=".9"/>')
    cx, cy, r = w * c["_fx"], h * c["_fy"], s * .16
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{c["bg"]}" stroke="{c["primary"]}" stroke-width="{s * .012:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.05, c["primary"], 1.8))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 08
def medical(w, h, c, icon, hint, rnd):
    s = min(w, h)
    defs = (f'<linearGradient id="wv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{c["secondary"]}" stop-opacity=".55"/><stop offset="1" stop-color="{c["accent"]}" stop-opacity=".25"/></linearGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    for i in range(3):
        y0 = h * (.68 + i * .09)
        amp = h * .05
        d = f"M0 {y0:.1f} C {w * .25:.1f} {y0 - amp:.1f}, {w * .5:.1f} {y0 + amp:.1f}, {w:.1f} {y0 - amp * .6:.1f} L{w} {h} L0 {h} Z"
        out.append(f'<path d="{d}" fill="url(#wv)" fill-opacity="{.5 + i * .2:.2f}"/>')
    cx, cy, r = w * c["_fx"], h * (c["_fy"] - .1), s * .17
    pulse = f"M{w * .05:.1f} {cy:.1f} L{cx - r * 1.6:.1f} {cy:.1f} L{cx - r * 1.35:.1f} {cy - r * .5:.1f} L{cx - r * 1.15:.1f} {cy + r * .45:.1f} L{cx - r * 1.0:.1f} {cy:.1f}"
    out.append(f'<path d="{pulse}" fill="none" stroke="{c["secondary"]}" stroke-width="{s * .007:.1f}" stroke-linejoin="round" stroke-linecap="round"/>')
    out.append(f'<path d="M{cx + r:.1f} {cy:.1f} L{w * .95:.1f} {cy:.1f}" stroke="{c["secondary"]}" stroke-width="{s * .007:.1f}" stroke-linecap="round"/>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{c["surface"]}" stroke="{c["accent"]}" stroke-width="{s * .008:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.05, c["primary"], 1.4))
    out.append('<!--/B-->')
    for _ in range(6):
        x, y, k = rnd.uniform(.08, .92) * w, rnd.uniform(.06, .5) * h, s * .018
        out.append(f'<path d="M{x - k:.1f} {y:.1f}H{x + k:.1f}M{x:.1f} {y - k:.1f}V{y + k:.1f}" stroke="{c["accent"]}" stroke-width="{s * .006:.1f}" stroke-linecap="round" stroke-opacity=".7"/>')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 09
def _star8(cx, cy, r):
    pts = []
    for i in range(16):
        rr = r if i % 2 == 0 else r * .62
        a = -math.pi / 2 + i * math.pi / 8
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)


def ikat(w, h, c, icon, hint, rnd):
    s = min(w, h)
    t = s / 3.2
    out = [f'<rect width="{w}" height="{h}" fill="{c["primary"]}"/>']
    tiles = []
    for i in range(-1, int(w / t) + 2):
        for j in range(-1, int(h / t) + 2):
            x, y = i * t + (t / 2 if j % 2 else 0), j * t * .86
            tiles.append(f'<polygon points="{_star8(x, y, t * .42)}" fill="none" stroke="{c["accent"]}" stroke-opacity=".38" stroke-width="{s * .003:.1f}"/>')
    out.append("".join(tiles))
    cx, cy = w * c["_fx"], h * c["_fy"]
    out.append('<!--B-->')
    out.append(f'<polygon points="{_star8(cx, cy, s * .3)}" fill="{c["secondary"]}" stroke="{c["accent"]}" stroke-width="{s * .006:.1f}"/>')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .15:.1f}" fill="{c["bg2"]}" stroke="{c["accent"]}" stroke-width="{s * .005:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .16, c["primary"], 1.4))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 10
def glossy3d(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cols = [c["primary"], c["accent"], c["secondary"]]
    defs = "".join(
        f'<radialGradient id="sp{i}" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#ffffff" stop-opacity=".95"/>'
        f'<stop offset=".18" stop-color="{col}"/><stop offset="1" stop-color="{c["bg"]}"/></radialGradient>' for i, col in enumerate(cols))
    defs += (f'<linearGradient id="rib" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c["secondary"]}"/><stop offset=".5" stop-color="{c["primary"]}"/>'
             f'<stop offset="1" stop-color="{c["accent"]}"/></linearGradient>'
             f'<radialGradient id="bgg" cx="60%" cy="40%" r="80%"><stop offset="0" stop-color="{c["bg2"]}"/><stop offset="1" stop-color="{c["bg"]}"/></radialGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="url(#bgg)"/>']
    cx, cy = w * c["_fx"], h * c["_fy"]
    for k in range(3):
        out.append(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{s * (.46 - k * .05):.1f}" ry="{s * (.16 + k * .03):.1f}" fill="none" stroke="url(#rib)" '
                   f'stroke-width="{s * (.05 - k * .012):.1f}" stroke-opacity="{.9 - k * .25:.2f}" transform="rotate({-24 + k * 18} {cx:.1f} {cy:.1f})"/>')
    for i, (fx, fy, fr) in enumerate([(.22, .24, .09), (.8, .72, .12), (.82, .2, .05)]):
        out.append(f'<circle cx="{w * fx:.1f}" cy="{h * fy:.1f}" r="{s * fr:.1f}" fill="url(#sp{i % 3})"/>')
    r = s * .15
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#ffffff" fill-opacity=".1" stroke="#ffffff" stroke-opacity=".5" stroke-width="{s * .004:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.05, "#ffffff", 1.4))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 11 swiss
def swiss(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    out.append(f'<circle cx="{w * .72:.1f}" cy="{h * .28:.1f}" r="{s * .30:.1f}" fill="{c["primary"]}"/>')
    out.append(f'<rect x="{w * .08:.1f}" y="{h * .58:.1f}" width="{w * .5:.1f}" height="{h * .5:.1f}" fill="{c["text"]}"/>')
    out.append(f'<rect x="{w * .52:.1f}" y="{h * .66:.1f}" width="{s * .18:.1f}" height="{s * .18:.1f}" fill="{c["accent"]}"/>')
    for i in range(6):
        y = h * (.08 + i * .035)
        out.append(f'<line x1="{w * .08:.1f}" y1="{y:.1f}" x2="{w * .42:.1f}" y2="{y:.1f}" stroke="{c["text"]}" stroke-width="{s * .006:.1f}"/>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .14:.1f}" fill="{c["surface"]}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .15, c["text"], 1.6))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 12 blobs (pastel)
def _blob(cx, cy, r, rnd, n=7):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * rnd.uniform(.78, 1.18)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d = f"M{(pts[0][0] + pts[-1][0]) / 2:.1f} {(pts[0][1] + pts[-1][1]) / 2:.1f} "
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        d += f"Q{p0[0]:.1f} {p0[1]:.1f} {(p0[0] + p1[0]) / 2:.1f} {(p0[1] + p1[1]) / 2:.1f} "
    return d + "Z"


def blobs(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    cols = [c["primary"], c["secondary"], c["accent"]]
    for i in range(5):
        out.append(f'<path d="{_blob(w * rnd.uniform(.1, .9), h * rnd.uniform(.1, .9), s * rnd.uniform(.16, .3), rnd)}" '
                   f'fill="{cols[i % 3]}" fill-opacity="{rnd.uniform(.35, .7):.2f}"/>')
    for _ in range(7):
        x, y, k = w * rnd.uniform(.05, .95), h * rnd.uniform(.05, .95), s * rnd.uniform(.02, .04)
        star = " ".join(f"{x + (k if i % 2 == 0 else k * .45) * math.cos(-math.pi / 2 + i * math.pi / 5):.1f},"
                        f"{y + (k if i % 2 == 0 else k * .45) * math.sin(-math.pi / 2 + i * math.pi / 5):.1f}" for i in range(10))
        out.append(f'<polygon points="{star}" fill="{c["accent"]}" stroke="{c["text"]}" stroke-width="{s * .004:.1f}" stroke-linejoin="round"/>')
    out.append('<!--B-->')
    out.append(f'<path d="{_blob(cx, cy, s * .2, rnd, 9)}" fill="{c["surface"]}" stroke="{c["text"]}" stroke-width="{s * .008:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .2, c["text"], 1.8))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 13 chalk
def chalk(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    defs = (f'<filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" result="n"/>'
            f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{s * .006:.1f}"/></filter>'
            f'<radialGradient id="board" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="{c["bg2"]}"/><stop offset="1" stop-color="{c["bg"]}"/></radialGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="url(#board)"/>', '<g filter="url(#rough)" fill="none" stroke-linecap="round">']
    for _ in range(5):
        x, y = w * rnd.uniform(.05, .8), h * rnd.uniform(.05, .9)
        out.append(f'<path d="M{x:.1f} {y:.1f} q{s * .1:.1f} {-s * .06:.1f} {s * .2:.1f} 0 t{s * .2:.1f} 0" stroke="{c["text"]}" stroke-opacity=".35" stroke-width="{s * .006:.1f}"/>')
    out.append(f'<circle cx="{w * .82:.1f}" cy="{h * .18:.1f}" r="{s * .08:.1f}" stroke="{c["accent"]}" stroke-width="{s * .007:.1f}" stroke-dasharray="{s * .03:.1f} {s * .015:.1f}"/>')
    out.append(f'<text x="{w * .1:.1f}" y="{h * .88:.1f}" fill="{c["text"]}" fill-opacity=".35" font-size="{s * .07:.1f}" font-family="Caveat, cursive">a² + b² = c²</text>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .2:.1f}" stroke="{c["primary"]}" stroke-width="{s * .01:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .22, c["text"], 1.3))
    out.append('<!--/B-->')
    out.append('</g>')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 14 doodle (notebook)
def doodle(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    gap = s * .05
    out = [f'<rect width="{w}" height="{h}" fill="{c["surface"]}"/>']
    y = gap * 2
    while y < h:
        out.append(f'<line x1="0" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" stroke="{c["secondary"]}" stroke-opacity=".35" stroke-width="{s * .002:.1f}"/>')
        y += gap
    out.append(f'<line x1="{w * .12:.1f}" y1="0" x2="{w * .12:.1f}" y2="{h}" stroke="{c["accent"]}" stroke-opacity=".7" stroke-width="{s * .003:.1f}"/>')
    for _ in range(4):
        x0, y0 = w * rnd.uniform(.2, .85), h * rnd.uniform(.1, .9)
        out.append(f'<path d="M{x0:.1f} {y0:.1f} c{s * .03:.1f} {-s * .05:.1f} {s * .08:.1f} {s * .05:.1f} {s * .11:.1f} 0 s{s * .08:.1f} {s * .05:.1f} {s * .11:.1f} 0" '
                   f'fill="none" stroke="{c["primary"]}" stroke-opacity=".45" stroke-width="{s * .005:.1f}" stroke-linecap="round"/>')
    out.append('<!--B-->')
    out.append(f'<rect x="{cx - s * .2:.1f}" y="{cy - s * .2:.1f}" width="{s * .4:.1f}" height="{s * .4:.1f}" fill="{c["accent"]}" fill-opacity=".85" transform="rotate(-4 {cx:.1f} {cy:.1f})"/>')
    out.append(f'<rect x="{cx - s * .07:.1f}" y="{cy - s * .23:.1f}" width="{s * .14:.1f}" height="{s * .05:.1f}" fill="{c["bg2"]}" fill-opacity=".8" transform="rotate(3 {cx:.1f} {cy:.1f})"/>')
    out.append(_icon(icon, hint, cx, cy, s * .22, c["text"], 1.6))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 15 blueprint
def blueprint(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    line = c["text"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>']
    for k, op in ((s / 40, .10), (s / 8, .22)):
        x = 0.0
        while x < w:
            out.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{h}" stroke="{line}" stroke-opacity="{op}" stroke-width="1"/>')
            x += k
        y = 0.0
        while y < h:
            out.append(f'<line x1="0" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" stroke="{line}" stroke-opacity="{op}" stroke-width="1"/>')
            y += k
    r = s * .26
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{line}" stroke-width="{s * .003:.1f}" stroke-dasharray="{s * .02:.1f} {s * .01:.1f}"/>')
    out.append(f'<line x1="{cx - r * 1.4:.1f}" y1="{cy:.1f}" x2="{cx + r * 1.4:.1f}" y2="{cy:.1f}" stroke="{line}" stroke-opacity=".6" stroke-width="1.5"/>')
    out.append(f'<line x1="{cx:.1f}" y1="{cy - r * 1.4:.1f}" x2="{cx:.1f}" y2="{cy + r * 1.4:.1f}" stroke="{line}" stroke-opacity=".6" stroke-width="1.5"/>')
    yy = cy + r * 1.25
    out.append(f'<path d="M{cx - r:.1f} {yy:.1f} H{cx + r:.1f} M{cx - r:.1f} {yy - 10:.1f} v20 M{cx + r:.1f} {yy - 10:.1f} v20" stroke="{c["accent"]}" stroke-width="2" fill="none"/>')
    out.append(f'<text x="{cx:.1f}" y="{yy - 14:.1f}" text-anchor="middle" fill="{c["accent"]}" font-size="{s * .035:.1f}" font-family="JetBrains Mono, monospace">{int(r * 2)} mm</text>')
    out.append('<!--B-->')
    out.append(_icon(icon, hint, cx, cy, r * 1.1, line, 1.1))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 16 magazine
def magazine(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["primary"]}"/>']
    wide = w > h * 1.3
    split, nx, ny = (.64, .73, .93) if wide else (.55, .06, .32)
    out.append(f'<rect x="{w * split:.1f}" y="0" width="{w * (1 - split):.1f}" height="{h}" fill="{c["text"]}"/>')
    out.append(f'<circle cx="{w * split:.1f}" cy="{h * .66:.1f}" r="{s * .28:.1f}" fill="{c["accent"]}"/>')
    out.append(f'<text x="{w * nx:.1f}" y="{h * ny:.1f}" fill="{c.get("on_primary", "#FFFFFF")}" fill-opacity=".9" font-size="{s * .30:.1f}" font-family="Yeseva One, serif">№</text>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .15:.1f}" fill="{c["surface"]}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .16, c["text"], 1.5))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 17 mesh (glass light)
def mesh(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    defs = f'<filter id="mb" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{s * .1:.1f}"/></filter>'
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>', '<g filter="url(#mb)">']
    for col in (c["primary"], c["secondary"], c["accent"], c["secondary"]):
        out.append(f'<ellipse cx="{w * rnd.uniform(.1, .9):.1f}" cy="{h * rnd.uniform(.1, .9):.1f}" rx="{s * rnd.uniform(.3, .45):.1f}" ry="{s * rnd.uniform(.25, .4):.1f}" fill="{col}" fill-opacity=".55"/>')
    out.append('</g><!--B-->')
    r = s * .2
    out.append(f'<rect x="{cx - r:.1f}" y="{cy - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" rx="{r * .35:.1f}" fill="#ffffff" fill-opacity=".55" stroke="#ffffff" stroke-width="{s * .005:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, r * 1.05, c["primary"], 1.5))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 18 retro sunset
def retro(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    sun_y = h * .62
    cols = [c["accent"], c["secondary"], c["primary"], c["text"]]
    for i, col in enumerate(cols):
        r = s * (.62 - i * .12)
        out.append(f'<path d="M{w / 2 - r:.1f} {sun_y:.1f} A{r:.1f} {r:.1f} 0 0 1 {w / 2 + r:.1f} {sun_y:.1f} Z" fill="{col}"/>')
    for i in range(5):
        y = sun_y + i * s * .045
        out.append(f'<rect x="0" y="{y:.1f}" width="{w}" height="{s * (.012 + i * .004):.1f}" fill="{c["bg2"]}"/>')
    out.append(f'<rect x="0" y="{sun_y:.1f}" width="{w}" height="{h - sun_y:.1f}" fill="{c["primary"]}" fill-opacity=".9"/>')
    for i in range(4):
        y = sun_y + (h - sun_y) * (i + 1) / 5
        out.append(f'<rect x="0" y="{y:.1f}" width="{w}" height="{s * .02:.1f}" fill="{c["accent"]}" fill-opacity=".8"/>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy - s * .12:.1f}" r="{s * .13:.1f}" fill="{c["surface"]}" stroke="{c["text"]}" stroke-width="{s * .008:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy - s * .12, s * .14, c["text"], 1.7))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out))


# --------------------------------------------------------------------- 19 ink (zen)
def ink(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    defs = (f'<filter id="wash"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="{rnd.randint(1, 99)}"/>'
            f'<feDisplacementMap in="SourceGraphic" scale="{s * .05:.1f}"/><feGaussianBlur stdDeviation="{s * .004:.1f}"/></filter>')
    out = [f'<rect width="{w}" height="{h}" fill="{c["surface"]}"/>', '<g filter="url(#wash)">']
    for i, op in enumerate((.18, .3, .5)):
        y0 = h * (.62 + i * .1)
        pts = " ".join(f"{w * k / 8:.1f},{y0 - h * rnd.uniform(.02, .16):.1f}" for k in range(9))
        fill = c["primary"] if i == 2 else c["text"]
        out.append(f'<polygon points="0,{h} {pts} {w},{h}" fill="{fill}" fill-opacity="{op + (.15 if i == 2 else 0):.2f}"/>')
    out.append('</g>')
    r = s * .26
    out.append(f'<circle cx="{cx:.1f}" cy="{cy - s * .08:.1f}" r="{r:.1f}" fill="none" stroke="{c["text"]}" stroke-width="{s * .03:.1f}" '
               f'stroke-dasharray="{2 * math.pi * r * .86:.1f} {2 * math.pi * r:.1f}" stroke-linecap="round" filter="url(#wash)" opacity=".85"/>')
    out.append(f'<rect x="{w * .78:.1f}" y="{h * .1:.1f}" width="{s * .09:.1f}" height="{s * .09:.1f}" rx="{s * .01:.1f}" fill="{c["primary"]}"/>')
    out.append('<!--B-->')
    out.append(_icon(icon, hint, cx, cy - s * .08, r * .9, c["text"], 1.2))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# --------------------------------------------------------------------- 20 cosmos
def cosmos(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    defs = (f'<radialGradient id="neb" cx="30%" cy="30%" r="80%"><stop offset="0" stop-color="{c["secondary"]}" stop-opacity=".5"/>'
            f'<stop offset=".5" stop-color="{c["primary"]}" stop-opacity=".18"/><stop offset="1" stop-color="{c["bg"]}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="pl" cx="35%" cy="30%" r="80%"><stop offset="0" stop-color="#ffffff" stop-opacity=".9"/><stop offset=".25" stop-color="{c["accent"]}"/>'
            f'<stop offset="1" stop-color="{c["bg"]}"/></radialGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>', f'<rect width="{w}" height="{h}" fill="url(#neb)"/>']
    for _ in range(90):
        out.append(f'<circle cx="{rnd.uniform(0, w):.1f}" cy="{rnd.uniform(0, h):.1f}" r="{rnd.uniform(.6, 2.4) * s / 900:.2f}" fill="#ffffff" fill-opacity="{rnd.uniform(.3, 1):.2f}"/>')
    px, py, pr = w * .72, h * .7, s * .22
    out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{pr:.1f}" fill="url(#pl)"/>')
    out.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="{pr * 1.7:.1f}" ry="{pr * .35:.1f}" fill="none" stroke="{c["primary"]}" stroke-width="{s * .012:.1f}" transform="rotate(-18 {px:.1f} {py:.1f})" opacity=".85"/>')
    out.append('<!--B-->')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * .14:.1f}" fill="{c["bg"]}" fill-opacity=".6" stroke="{c["primary"]}" stroke-width="{s * .006:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, s * .15, "#ffffff", 1.4))
    out.append('<!--/B-->')
    return _wrap(w, h, "".join(out), defs)


# ===================================================================== extra styles (generated templates)
def _badge_disk(c, cx, cy, s, icon, hint, fill=None, fg=None, ring=None, r=.15):
    fill = fill or c["surface"]
    fg = fg or c["text"]
    out = ['<!--B-->', f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * r:.1f}" fill="{fill}"/>']
    if ring:
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * (r + .025):.1f}" fill="none" stroke="{ring}" stroke-width="{s * .006:.1f}"/>')
    out.append(_icon(icon, hint, cx, cy, s * r * 1.05, fg, 1.5))
    out.append('<!--/B-->')
    return "".join(out)


def bauhaus(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cols = [c["primary"], c["secondary"], c["accent"], c["text"], c["bg2"]]
    n = 4 if w < h * 1.3 else 7
    t = w / n
    rows = int(h / t) + 1
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    for j in range(rows):
        for i in range(n):
            x, y = i * t, j * t
            a, b = rnd.sample(cols, 2)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{t:.1f}" height="{t:.1f}" fill="{a}"/>')
            k = rnd.randint(0, 4)
            if k == 0:
                out.append(f'<path d="M{x:.1f} {y:.1f} h{t:.1f} a{t:.1f} {t:.1f} 0 0 1 -{t:.1f} {t:.1f} Z" fill="{b}"/>')
            elif k == 1:
                out.append(f'<circle cx="{x + t / 2:.1f}" cy="{y + t / 2:.1f}" r="{t * .38:.1f}" fill="{b}"/>')
            elif k == 2:
                out.append(f'<path d="M{x:.1f} {y + t:.1f} a{t / 2:.1f} {t / 2:.1f} 0 0 1 {t:.1f} 0 Z" fill="{b}"/>')
            elif k == 3:
                out.append(f'<path d="M{x:.1f} {y:.1f} L{x + t:.1f} {y + t:.1f} L{x:.1f} {y + t:.1f} Z" fill="{b}"/>')
    out.append(_badge_disk(c, w * c["_fx"], h * c["_fy"], s, icon, hint, ring=c["text"]))
    return _wrap(w, h, "".join(out))


def stripes(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cols = [c["primary"], c["secondary"], c["accent"], c["bg2"]]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>', f'<g transform="rotate(-32 {w / 2:.1f} {h / 2:.1f})">']
    band = s * .16
    k = 0
    y = -h
    while y < h * 2:
        bw = band * rnd.choice([.5, 1, 1, 1.6])
        out.append(f'<rect x="{-w:.1f}" y="{y:.1f}" width="{w * 3:.1f}" height="{bw:.1f}" fill="{cols[k % 4]}"/>')
        y += bw + band * .35
        k += 1
    out.append('</g>')
    out.append(_badge_disk(c, w * c["_fx"], h * c["_fy"], s, icon, hint, fill=c["bg"], fg=c["text"]))
    return _wrap(w, h, "".join(out))


def rings(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    for i in range(14, 0, -1):
        r = s * .07 * i
        col = [c["primary"], c["secondary"], c["accent"]][i % 3]
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="{.10 + (14 - i) * .035:.2f}"/>')
    for _ in range(18):
        a = rnd.uniform(0, 2 * math.pi)
        rr = s * rnd.uniform(.25, .9)
        out.append(f'<circle cx="{cx + rr * math.cos(a):.1f}" cy="{cy + rr * math.sin(a):.1f}" r="{s * rnd.uniform(.006, .016):.1f}" fill="{c["text"]}" fill-opacity=".5"/>')
    out.append(_badge_disk(c, cx, cy, s, icon, hint))
    return _wrap(w, h, "".join(out))


def waves(w, h, c, icon, hint, rnd):
    s = min(w, h)
    defs = (f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c["bg2"]}"/>'
            f'<stop offset="1" stop-color="{c["bg"]}"/></linearGradient>')
    out = [f'<rect width="{w}" height="{h}" fill="url(#sky)"/>']
    out.append(f'<circle cx="{w * .72:.1f}" cy="{h * .3:.1f}" r="{s * .16:.1f}" fill="{c["accent"]}"/>')
    cols = [c["secondary"], c["primary"], c["text"]]
    for i in range(5):
        base = h * (.48 + i * .11)
        amp = s * rnd.uniform(.03, .07)
        ph = rnd.uniform(0, 6)
        freq = rnd.choice([2, 3, 4])
        pts = [f"M0 {h}"]
        for k in range(61):
            x = w * k / 60
            pts.append(f"L{x:.1f} {base + amp * math.sin(ph + k / 60 * math.pi * freq):.1f}")
        pts.append(f"L{w} {h} Z")
        out.append(f'<path d="{" ".join(pts)}" fill="{cols[i % 3]}" fill-opacity="{.35 + i * .13:.2f}"/>')
    out.append(_badge_disk(c, w * c["_fx"], h * c["_fy"] - s * .05, s, icon, hint))
    return _wrap(w, h, "".join(out), defs)


def lowpoly(w, h, c, icon, hint, rnd):
    s = min(w, h)
    nx, ny = 9, 6
    pts = [[(w * i / (nx - 1) + (rnd.uniform(-.35, .35) * w / nx if 0 < i < nx - 1 else 0),
             h * j / (ny - 1) + (rnd.uniform(-.35, .35) * h / ny if 0 < j < ny - 1 else 0)) for i in range(nx)] for j in range(ny)]
    cols = [c["primary"], c["secondary"], c["bg2"], c["accent"]]
    out = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, cc, d = pts[j][i], pts[j][i + 1], pts[j + 1][i], pts[j + 1][i + 1]
            for tri in ((a, b, d), (a, d, cc)):
                mx = sum(p[0] for p in tri) / 3 / w
                my = sum(p[1] for p in tri) / 3 / h
                col = cols[int((mx * 2 + my * 1.5 + rnd.uniform(0, .6)) * 1.3) % 4]
                op = .55 + .45 * rnd.random()
                out.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in tri)}" fill="{col}" fill-opacity="{op:.2f}" stroke="{col}" stroke-width="1"/>')
    out.insert(0, f'<rect width="{w}" height="{h}" fill="{c["bg"]}"/>')
    out.append(_badge_disk(c, w * c["_fx"], h * c["_fy"], s, icon, hint))
    return _wrap(w, h, "".join(out))


def halftone(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    step = s / 16
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    for j in range(int(h / step) + 2):
        for i in range(int(w / step) + 2):
            x, y = i * step + (step / 2 if j % 2 else 0), j * step
            d = math.hypot(x - cx, y - cy) / (s * .9)
            r = max(0, step * .46 * (1 - d))
            if r > .8:
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c["primary"] if (i + j) % 7 else c["secondary"]}"/>')
    out.append(_badge_disk(c, cx, cy, s, icon, hint, fill=c["accent"], fg=c["text"]))
    return _wrap(w, h, "".join(out))


def confetti(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cols = [c["primary"], c["secondary"], c["accent"], c["text"]]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    for k in range(70):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        col = cols[k % 4]
        sz = s * rnd.uniform(.015, .04)
        t = k % 5
        rot = rnd.uniform(0, 180)
        if t == 0:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{sz:.1f}" fill="{col}"/>')
        elif t == 1:
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{sz * 2:.1f}" height="{sz * .8:.1f}" rx="{sz * .3:.1f}" fill="{col}" transform="rotate({rot:.0f} {x:.1f} {y:.1f})"/>')
        elif t == 2:
            out.append(f'<path d="M{x:.1f} {y:.1f} l{sz:.1f} {-sz * 1.7:.1f} l{sz:.1f} {sz * 1.7:.1f} Z" fill="{col}" transform="rotate({rot:.0f} {x:.1f} {y:.1f})"/>')
        elif t == 3:
            out.append(f'<path d="M{x:.1f} {y:.1f} q{sz:.1f} {-sz:.1f} {sz * 2:.1f} 0 t{sz * 2:.1f} 0 t{sz * 2:.1f} 0" fill="none" stroke="{col}" stroke-width="{sz * .4:.1f}" stroke-linecap="round" transform="rotate({rot:.0f} {x:.1f} {y:.1f})"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{sz:.1f}" fill="none" stroke="{col}" stroke-width="{sz * .35:.1f}"/>')
    out.append(_badge_disk(c, w * c["_fx"], h * c["_fy"], s, icon, hint, fill=c["surface"], fg=c["primary"], ring=c["primary"]))
    return _wrap(w, h, "".join(out))


def isometric(w, h, c, icon, hint, rnd):
    s = min(w, h)
    a = s * .09
    dx, dy = a * math.cos(math.pi / 6), a * .5
    top, left, right = c["secondary"], c["primary"], c.get("ink", c["text"])
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    cx0, cy0 = w * c["_fx"], h * c["_fy"]
    cubes = []
    for i in range(-5, 6):
        for j in range(-5, 6):
            hgt = rnd.choice([0, 0, 1, 1, 2, 3])
            if hgt == 0 or (abs(i) < 2 and abs(j) < 2):
                continue
            cubes.append((i + j, i, j, hgt))
    for _, i, j, hgt in sorted(cubes):
        x = cx0 + (i - j) * dx
        y = cy0 + (i + j) * dy
        for z in range(hgt):
            yy = y - z * a
            out.append(f'<path d="M{x:.1f} {yy:.1f} l{dx:.1f} {-dy:.1f} l{-dx:.1f} {-dy:.1f} l{-dx:.1f} {dy:.1f} Z" fill="{top}"/>')
            out.append(f'<path d="M{x:.1f} {yy:.1f} l{-dx:.1f} {-dy:.1f} v{a:.1f} l{dx:.1f} {dy:.1f} Z" fill="{left}"/>')
            out.append(f'<path d="M{x:.1f} {yy:.1f} l{dx:.1f} {-dy:.1f} v{a:.1f} l{-dx:.1f} {dy:.1f} Z" fill="{right}" fill-opacity=".85"/>')
    out.append(_badge_disk(c, cx0, cy0 - a * .5, s, icon, hint, fill=c["accent"], fg=c["text"], r=.13))
    return _wrap(w, h, "".join(out))


def sunburst(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * (c["_fy"] + .1)
    out = [f'<rect width="{w}" height="{h}" fill="{c["primary"]}"/>']
    n = 28
    R = max(w, h) * 1.6
    for k in range(n):
        if k % 2:
            continue
        a1, a2 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        out.append(f'<path d="M{cx:.1f} {cy:.1f} L{cx + R * math.cos(a1):.1f} {cy + R * math.sin(a1):.1f} L{cx + R * math.cos(a2):.1f} {cy + R * math.sin(a2):.1f} Z" fill="{c["secondary"]}" fill-opacity=".55"/>')
    for i, col in enumerate([c["accent"], c["bg2"], c["accent"]]):
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s * (.32 - i * .07):.1f}" fill="{col}" fill-opacity="{.35 + i * .3:.2f}"/>')
    out.append(_badge_disk(c, cx, cy, s, icon, hint, fill=c["surface"], fg=c["primary"], r=.13))
    return _wrap(w, h, "".join(out))


def papercut(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cols = [c["bg2"], c["secondary"], c["primary"], c.get("ink", c["text"])]
    out = [f'<rect width="{w}" height="{h}" fill="{c["accent"]}"/>']
    for i in range(4):
        base = h * (.2 + i * .2)
        pts = [f"M{-10} {h + 10}"]
        for k in range(13):
            pts.append(f"L{w * k / 12:.1f} {base + s * rnd.uniform(-.09, .09):.1f}")
        pts.append(f"L{w + 10} {h + 10} Z")
        d = " ".join(pts)
        out.append(f'<path d="{d}" fill="#000" fill-opacity=".18" transform="translate(0 {-s * .018:.1f})"/>')
        out.append(f'<path d="{d}" fill="{cols[i]}"/>')
    out.append(_badge_disk(c, w * c["_fx"], h * (c["_fy"] - .08), s, icon, hint))
    return _wrap(w, h, "".join(out))


def topo(w, h, c, icon, hint, rnd):
    s = min(w, h)
    cx, cy = w * c["_fx"], h * c["_fy"]
    out = [f'<rect width="{w}" height="{h}" fill="{c["bg2"]}"/>']
    ph = [rnd.uniform(0, 6) for _ in range(3)]
    for i in range(1, 22):
        r0 = s * .06 * i
        pts = []
        for k in range(73):
            a = 2 * math.pi * k / 72
            r = r0 * (1 + .12 * math.sin(3 * a + ph[0]) + .07 * math.sin(5 * a + ph[1] + i * .2) + .05 * math.sin(2 * a + ph[2]))
            pts.append(f"{'M' if k == 0 else 'L'}{cx + r * math.cos(a):.1f} {cy + r * math.sin(a) * .8:.1f}")
        col = c["primary"] if i % 4 else c["secondary"]
        out.append(f'<path d="{" ".join(pts)} Z" fill="none" stroke="{col}" stroke-opacity="{.75 - i * .025:.2f}" stroke-width="{s * (.004 if i % 4 else .007):.1f}"/>')
    out.append(_badge_disk(c, cx, cy, s, icon, hint, fill=c["primary"], fg=c["on_primary"] if "on_primary" in c else "#fff", r=.12))
    return _wrap(w, h, "".join(out))


STYLES: Dict[str, Callable] = {
    "circuit": circuit, "academic": academic, "aurora": aurora, "editorial": editorial, "botanical": botanical,
    "corporate": corporate, "neon": neon, "medical": medical, "ikat": ikat, "glossy3d": glossy3d,
    "swiss": swiss, "blobs": blobs, "chalk": chalk, "doodle": doodle, "blueprint": blueprint, "magazine": magazine,
    "mesh": mesh, "retro": retro, "ink": ink, "cosmos": cosmos,
    "bauhaus": bauhaus, "stripes": stripes, "rings": rings, "waves": waves, "lowpoly": lowpoly, "halftone": halftone,
    "confetti": confetti, "isometric": isometric, "sunburst": sunburst, "papercut": papercut, "topo": topo,
}


def render_art(style: str, palette: Dict[str, str], icon: str, hint: str, w: int, h: int, seed: int = 0,
               badge: bool = True, overlay: str = "") -> str:
    fn = STYLES.get(style, academic)
    rnd = random.Random(f"{style}-{seed}-{icon}")
    c = dict(palette)
    # On full-slide art the text sits on the left/bottom, so the focal point moves right.
    c["_fx"], c["_fy"] = (0.76, 0.40) if w / max(h, 1) > 1.4 else (0.5, 0.5)
    svg = fn(int(w), int(h), c, icon, hint, rnd)
    if not badge or overlay:  # centred text sits on top / a sticker replaces the icon badge
        svg = re.sub(r"<!--B-->.*?<!--/B-->", "", svg, flags=re.S)
    if overlay and badge:
        size = min(w, h) * .50
        x, y = w * c["_fx"] - size / 2, h * c["_fy"] - size / 2
        sticker = re.sub(r'^<svg ', f'<svg x="{x:.1f}" y="{y:.1f}" ', overlay, count=1)
        sticker = re.sub(r'width="\d+" height="\d+"', f'width="{size:.1f}" height="{size:.1f}"', sticker, count=1)
        svg = svg[:svg.rfind("</svg>")] + sticker + "</svg>"
    return svg


def art_data_uri(style: str, palette: Dict[str, str], icon: str, hint: str, w: int, h: int, seed: int = 0,
                 badge: bool = True, overlay: str = "") -> str:
    svg = render_art(style, palette, icon, hint, w, h, seed, badge, overlay)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
