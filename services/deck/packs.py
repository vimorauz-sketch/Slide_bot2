"""
Decoration packs: themed ornaments drawn on every slide of a template (tropical leaves, flowers,
network lines, gold ribbons, clouds...). Covers get a rich composition; content slides get the same
motif kept to the slide edges (left strip, right strip below the sticker corner, top and bottom
bands) so it never runs into text.

pack_svg(name, palette, kind) returns a full-slide (1920x1080) SVG; kind is "cover", "content" or
"statement". Everything is drawn from the template palette.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Dict

W, H = 1920, 1080


def _mix(a: str, b: str, t: float) -> str:
    ca = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(round(ca[i] * (1 - t) + cb[i] * t) for i in range(3))


def _lum(h: str) -> float:
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def _wrap(body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'preserveAspectRatio="none">{body}</svg>')


# ------------------------------------------------------------------ shapes
def _leaf(x, y, size, angle, fill, vein, slits=True):
    """Monstera-like leaf pointing along `angle` (degrees), stem at (x, y)."""
    s = size
    d = (f"M0 0 C{s * .15:.1f} {-s * .45:.1f} {s * .62:.1f} {-s * .55:.1f} {s:.1f} 0 "
         f"C{s * .62:.1f} {s * .55:.1f} {s * .15:.1f} {s * .45:.1f} 0 0Z")
    out = [f'<g transform="translate({x:.1f} {y:.1f}) rotate({angle:.1f})"><path d="{d}" fill="{fill}"/>',
           f'<path d="M0 0 L{s * .95:.1f} 0" stroke="{vein}" stroke-width="{s * .025:.1f}" fill="none"/>']
    for k in range(1, 6):
        px = s * k / 6.5
        out.append(f'<path d="M{px:.1f} 0 L{px + s * .14:.1f} {-s * .2:.1f} M{px:.1f} 0 L{px + s * .14:.1f} {s * .2:.1f}" '
                   f'stroke="{vein}" stroke-width="{s * .015:.1f}" fill="none" opacity=".8"/>')
    if slits:
        for k in (2, 4):
            px = s * k / 6
            out.append(f'<path d="M{px:.1f} {-s * .36:.1f} L{px + s * .06:.1f} {-s * .16:.1f}" stroke="{vein}" stroke-width="{s * .04:.1f}" stroke-linecap="round"/>')
    out.append("</g>")
    return "".join(out)


def _frond(x, y, length, angle, color, n=14, rnd=None):
    """Palm frond: curved stem with thin leaflets."""
    out = [f'<g transform="translate({x:.1f} {y:.1f}) rotate({angle:.1f})">',
           f'<path d="M0 0 Q{length * .5:.1f} {-length * .12:.1f} {length:.1f} 0" stroke="{color}" stroke-width="{length * .018:.1f}" fill="none"/>']
    for k in range(1, n):
        t = k / n
        px, py = length * t, -length * .12 * 4 * t * (1 - t) * .5
        ll = length * .32 * (1 - t * .7)
        for sgn in (-1, 1):
            out.append(f'<path d="M{px:.1f} {py:.1f} q{ll * .35:.1f} {sgn * ll * .25:.1f} {ll * .8:.1f} {sgn * ll * .55:.1f} '
                       f'q{-ll * .35:.1f} {-sgn * ll * .15:.1f} {-ll * .8:.1f} {-sgn * ll * .55:.1f}Z" fill="{color}"/>')
    out.append("</g>")
    return "".join(out)


def _flower(x, y, r, petal, center, n=5, rot=0):
    out = [f'<g transform="translate({x:.1f} {y:.1f}) rotate({rot:.1f})">']
    for k in range(n):
        a = 360 * k / n
        out.append(f'<ellipse cx="0" cy="{-r * .55:.1f}" rx="{r * .38:.1f}" ry="{r * .6:.1f}" fill="{petal}" transform="rotate({a:.1f})"/>')
    out.append(f'<circle r="{r * .3:.1f}" fill="{center}"/></g>')
    return "".join(out)


def _cloud(x, y, s, fill, opacity=1):
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.2f})" fill="{fill}" opacity="{opacity}">'
            '<circle cx="0" cy="0" r="40"/><circle cx="45" cy="-18" r="52"/><circle cx="100" cy="-4" r="42"/>'
            '<circle cx="140" cy="10" r="30"/><rect x="-10" y="0" width="160" height="40" rx="20"/></g>')


# ------------------------------------------------------------------ edge helpers for content slides
def _edges(rnd, n=6):
    """Random anchor points along the safe edges of a content slide."""
    pts = []
    for _ in range(n):
        side = rnd.choice(["L", "L", "R", "B", "T"])
        if side == "L":
            pts.append((rnd.uniform(-20, 70), rnd.uniform(140, 1000)))
        elif side == "R":
            pts.append((rnd.uniform(1850, 1940), rnd.uniform(300, 1000)))
        elif side == "T":
            pts.append((rnd.uniform(400, 1500), rnd.uniform(-30, 30)))
        else:
            pts.append((rnd.uniform(500, 1600), rnd.uniform(1062, 1100)))
    return pts


# ------------------------------------------------------------------ packs
def tropic(c, kind, rnd):
    g1, g2, g3 = c["primary"], c["secondary"], _mix(c["primary"], c["ink"], .35)
    vein = _mix(c["primary"], "#FFFFFF", .35)
    out = []
    if kind == "cover":
        for k in range(5):
            out.append(_leaf(W + 40, -40 + k * 30, rnd.uniform(300, 420), 140 + k * 14 + rnd.uniform(-6, 6), [g1, g2, g3][k % 3], vein))
        out.append(_frond(W + 30, 260, 520, 170, g3))
        for k in range(4):
            out.append(_leaf(-40, H + 30, rnd.uniform(260, 360), -20 - k * 18, [g2, g1, g3][k % 3], vein))
    else:
        out.append(_leaf(-30, -30, 170, 38, g1, vein))
        out.append(_leaf(-40, 60, 140, 12, g2, vein))
        out.append(_frond(-20, H + 20, 300, -42, g3))
        out.append(_leaf(W + 30, H + 30, 170, 205, g2, vein))
        out.append(_leaf(W + 20, H - 120, 120, 185, g1, vein))
    return "".join(out)


def floral(c, kind, rnd):
    petals = [c["primary"], c["accent"], _mix(c["secondary"], "#FFFFFF", .3), _mix(c["primary"], "#FFFFFF", .45)]
    leaf = c["secondary"]
    out = []
    corners = [(0, 0, 1, 1), (W, H, -1, -1)] if kind != "cover" else [(0, 0, 1, 1), (W, 0, -1, 1), (W, H, -1, -1), (0, H, 1, -1)]
    scale = 1.0 if kind == "cover" else .6
    for (cx, cy, sx, sy) in corners:
        for k in range(7):
            a = math.radians(rnd.uniform(0, 90))
            rr = rnd.uniform(40, 230) * scale
            x, y = cx + sx * rr * math.cos(a), cy + sy * rr * math.sin(a)
            out.append(_leaf(x, y, rnd.uniform(70, 130) * scale, math.degrees(math.atan2(sy * math.sin(a), sx * math.cos(a))) + rnd.uniform(-30, 30), leaf, _mix(leaf, "#FFFFFF", .3), slits=False))
        for k in range(5):
            a = math.radians(rnd.uniform(5, 85))
            rr = rnd.uniform(30, 190) * scale
            out.append(_flower(cx + sx * rr * math.cos(a), cy + sy * rr * math.sin(a), rnd.uniform(34, 62) * scale, petals[k % 4], c["accent"] if k % 4 else "#FFFFFF", rot=rnd.uniform(0, 70)))
    return "".join(out)


def plexus(c, kind, rnd):
    col = c["primary"]
    if kind == "cover":
        pts = [(rnd.uniform(1050, 1900), rnd.uniform(20, 1060)) for _ in range(46)]
    else:
        pts = [(rnd.uniform(5, 100), rnd.uniform(130, 1050)) for _ in range(16)] + [(rnd.uniform(1835, 1915), rnd.uniform(300, 1050)) for _ in range(14)]
    out = []
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            d = math.hypot(x2 - x1, y2 - y1)
            if d < (210 if kind == "cover" else 170):
                out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col}" stroke-opacity="{.55 - d / 500:.2f}" stroke-width="1.6"/>')
    for x, y in pts:
        r = rnd.choice([3, 4, 5, 7, 9])
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{c["text"] if r > 6 else col}" fill-opacity=".8"/>')
    return "".join(out)


def shards(c, kind, rnd):
    cols = [c["primary"], c["secondary"], _mix(c["primary"], "#FFFFFF", .4), _mix(c["secondary"], c["ink"], .3), c["accent"]]
    out = []
    regions = [((-40, 520), (-40, 380)), ((1400, 1960), (700, 1120))] if kind == "cover" else [((-30, 110), (-30, 260)), ((1830, 1950), (880, 1110))]
    for (xr, yr) in regions:
        for _ in range(26 if kind == "cover" else 8):
            x, y = rnd.uniform(*xr), rnd.uniform(*yr)
            s = rnd.uniform(40, 140) * (1 if kind == "cover" else .6)
            pts = " ".join(f"{x + s * math.cos(a):.0f},{y + s * math.sin(a):.0f}" for a in (rnd.uniform(0, 6.28), rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)))
            out.append(f'<polygon points="{pts}" fill="{rnd.choice(cols)}" fill-opacity="{rnd.uniform(.45, .9):.2f}"/>')
    return "".join(out)


def gold(c, kind, rnd):
    g1, g2 = "#E9C46A", "#B8862B"
    defs = f'<defs><linearGradient id="gd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{g1}"/><stop offset=".5" stop-color="#FFF1C4"/><stop offset="1" stop-color="{g2}"/></linearGradient></defs>'
    out = [defs]
    if kind == "cover":
        for k in range(9):
            o = k * 26
            out.append(f'<path d="M{1100 + o} {H + 20} C{1400 + o} {700 - o * .5} {1700} {650 + o} {W + 40} {260 + o}" fill="none" stroke="url(#gd)" stroke-width="{2 + (k % 3) * 2}" opacity="{.95 - k * .06:.2f}"/>')
        out.append(f'<path d="M-40 {120} C200 160 300 40 560 -30" fill="none" stroke="url(#gd)" stroke-width="5"/>')
        out.append(f'<path d="M-40 {160} C240 200 360 70 620 -30" fill="none" stroke="url(#gd)" stroke-width="2"/>')
    else:
        for k in range(4):
            out.append(f'<path d="M1500 {H + 10} C1700 {1000 - k * 14} 1820 {900 - k * 30} {W + 20} {760 - k * 50}" fill="none" stroke="url(#gd)" stroke-width="{2 + k % 2 * 2}" opacity=".9"/>')
        out.append(f'<path d="M-20 {300} C40 260 50 140 30 -20" fill="none" stroke="url(#gd)" stroke-width="3"/>')
    return "".join(out)


def clouds(c, kind, rnd):
    white = "#FFFFFF"
    out = []
    if kind == "cover":
        out.append(f'<rect x="0" y="{H - 140}" width="{W}" height="140" fill="{white}" opacity=".9"/>')
        for k in range(12):
            out.append(_cloud(-120 + k * 180 + rnd.uniform(-30, 30), H - 150 + rnd.uniform(-40, 30), rnd.uniform(.9, 1.5), white, .95))
        for k in range(5):
            out.append(_cloud(rnd.uniform(1100, 1800), rnd.uniform(60, 500), rnd.uniform(.5, .9), white, .8))
        out.append(f'<path d="M1500 160 l120 -40 l-50 110 l-20 -40 Z" fill="{c["accent"]}"/><path d="M1490 160 q-200 40 -320 -20" fill="none" stroke="{c["accent"]}" stroke-width="3" stroke-dasharray="10 12"/>')
    else:
        for k in range(10):
            out.append(_cloud(-80 + k * 210 + rnd.uniform(-20, 20), H + 14 + rnd.uniform(-8, 10), rnd.uniform(.55, .8), _mix(c["bg"], white, .25) if _lum(c["bg"]) < .4 else white, .95))
        out.append(_cloud(1830, 340, .45, _mix(c["primary"], white, .7), .9))
    return "".join(out)


def waves(c, kind, rnd):
    cols = [c["primary"], c["secondary"], _mix(c["primary"], "#FFFFFF", .5)]
    out = []
    if kind == "cover":
        out.append(f'<path d="M0 {H} V1020 C140 1000 260 1050 420 1035 C560 1022 640 1060 760 {H}Z" fill="{cols[2]}" opacity=".7"/>')
        out.append(f'<path d="M0 {H} V1045 C120 1030 220 1066 360 1056 C460 1050 520 1070 580 {H}Z" fill="{cols[0]}"/>')
        out.append(f'<path d="M{W} {H} H1150 C1240 980 1120 900 1280 800 C1420 720 1580 800 1720 700 C1820 640 1880 660 {W} 650Z" fill="{cols[2]}" opacity=".7"/>')
        out.append(f'<path d="M{W} {H} H1380 C1440 1010 1380 940 1500 880 C1610 830 1720 890 1820 820 C1870 790 1900 790 {W} 780Z" fill="{cols[1]}"/>')
        out.append(f'<path d="M{W} 0 V200 C1860 230 1800 160 1720 170 C1660 178 1620 120 1600 0Z" fill="{cols[0]}" opacity=".85"/>')
    else:
        out.append(f'<path d="M0 0 H110 C95 30 110 55 70 70 C40 80 15 72 0 76Z" fill="{cols[0]}"/>')
        out.append(f'<path d="M0 {H} V1000 C60 990 110 1030 170 1020 C220 1012 250 1050 270 {H}Z" fill="{cols[2]}" opacity=".7"/>')
        out.append(f'<path d="M{W} {H} H1790 C1820 1050 1800 1000 1860 980 C1890 970 1905 960 {W} 950Z" fill="{cols[1]}"/>')
    return "".join(out)


def bars(c, kind, rnd):
    cols = [c["primary"], c["secondary"], c["accent"], _mix(c["primary"], "#FFFFFF", .45)]
    out = []
    if kind == "cover":
        for k in range(5):
            x = 1180 + k * 150
            out.append(f'<polygon points="{x},-10 {x + 120},-10 {x - 260},{H + 10} {x - 380},{H + 10}" fill="{cols[k % 4]}" opacity="{.85 if k % 2 else .55}"/>')
    else:
        for k in range(3):
            x = 20 + k * 46
            out.append(f'<polygon points="{x},-10 {x + 34},-10 {x - 60},{230} {x - 94},{230}" fill="{cols[k % 4]}"/>')
        for k in range(3):
            x = W + 40 - k * 46
            out.append(f'<polygon points="{x},{H + 10} {x - 34},{H + 10} {x + 60},{H - 220} {x + 94},{H - 220}" fill="{cols[(k + 1) % 4]}"/>')
    return "".join(out)


def brush(c, kind, rnd):
    def stroke(x, y, length, thick, angle, color, op):
        pts_top = [(t * length, -thick / 2 + rnd.uniform(-thick * .12, thick * .12)) for t in [i / 10 for i in range(11)]]
        pts_bot = [(t * length, thick / 2 + rnd.uniform(-thick * .12, thick * .12)) for t in [i / 10 for i in range(10, -1, -1)]]
        d = "M" + " L".join(f"{px:.0f} {py:.0f}" for px, py in pts_top + pts_bot) + "Z"
        bristles = "".join(f'<path d="M{length * .1:.0f} {-thick / 2 + thick * k / 6:.0f} L{length * rnd.uniform(.85, 1.05):.0f} {-thick / 2 + thick * k / 6:.0f}" stroke="{color}" stroke-width="2" opacity=".5"/>' for k in range(1, 6))
        return f'<g transform="translate({x:.0f} {y:.0f}) rotate({angle:.1f})" opacity="{op}"><path d="{d}" fill="{color}"/>{bristles}</g>'
    out = []
    if kind == "cover":
        out.append(stroke(1150, 140, 900, 150, -8, c["primary"], .9))
        out.append(stroke(1300, 330, 700, 70, -6, c["accent"], .85))
        out.append(stroke(-60, 1000, 800, 110, -4, c["secondary"], .8))
    else:
        out.append(stroke(-40, 30, 160, 40, 70, c["primary"], .85))
        out.append(stroke(1700, 1070, 320, 36, -6, c["accent"], .85))
    return "".join(out)


def doodles(c, kind, rnd):
    col = c["text"]
    acc = [c["primary"], c["accent"], c["secondary"]]
    items = []
    pts = ([(rnd.uniform(1050, 1880), rnd.uniform(40, 1040)) for _ in range(16)] + [(rnd.uniform(40, 700), rnd.uniform(960, 1050)) for _ in range(5)]) if kind == "cover" else _edges(rnd, 9)
    for k, (x, y) in enumerate(pts):
        s = rnd.uniform(.7, 1.3) * (1 if kind == "cover" else .75)
        t = k % 6
        clr = acc[k % 3]
        if t == 0:
            d = "M0 -26 L7 -8 L26 -8 L11 4 L17 24 L0 12 L-17 24 L-11 4 L-26 -8 L-7 -8Z"
            items.append(f'<path d="{d}" fill="{clr}" stroke="{col}" stroke-width="2.5" transform="translate({x:.0f} {y:.0f}) scale({s:.2f}) rotate({rnd.uniform(-20, 20):.0f})"/>')
        elif t == 1:
            items.append(f'<path d="M-30 0 q10 -16 20 0 t20 0 t20 0" fill="none" stroke="{clr}" stroke-width="5" stroke-linecap="round" transform="translate({x:.0f} {y:.0f}) scale({s:.2f})"/>')
        elif t == 2:
            items.append(f'<path d="M0 0 m-20 0 a20 20 0 1 0 40 0 a14 14 0 1 0 -28 0 a8 8 0 1 0 16 0" fill="none" stroke="{col}" stroke-width="3" transform="translate({x:.0f} {y:.0f}) scale({s:.2f})"/>')
        elif t == 3:
            items.append(f'<path d="M0 8 C-24 -10 -12 -28 0 -14 C12 -28 24 -10 0 8Z" fill="{clr}" stroke="{col}" stroke-width="2.5" transform="translate({x:.0f} {y:.0f}) scale({s * 1.3:.2f})"/>')
        elif t == 4:
            items.append(f'<path d="M-24 10 L18 -10 M18 -10 L4 -12 M18 -10 L12 2" fill="none" stroke="{col}" stroke-width="3.5" stroke-linecap="round" transform="translate({x:.0f} {y:.0f}) scale({s:.2f})"/>')
        else:
            items.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{10 * s:.0f}" fill="none" stroke="{clr}" stroke-width="4"/>')
    return "".join(items)


def medical(c, kind, rnd):
    col = c["primary"]
    out = []
    pts = [(rnd.uniform(1100, 1880), rnd.uniform(40, 1040)) for _ in range(18)] if kind == "cover" else _edges(rnd, 8)
    for x, y in pts:
        s = rnd.uniform(14, 34) * (1 if kind == "cover" else .7)
        out.append(f'<path d="M{x - s / 3:.0f} {y - s:.0f} h{2 * s / 3:.0f} v{2 * s / 3:.0f} h{2 * s / 3:.0f} v{2 * s / 3:.0f} h{-2 * s / 3:.0f} v{2 * s / 3:.0f} h{-2 * s / 3:.0f} v{-2 * s / 3:.0f} h{-2 * s / 3:.0f} v{-2 * s / 3:.0f} h{2 * s / 3:.0f}Z" '
                   f'fill="{rnd.choice([col, c["secondary"], _mix(col, "#FFFFFF", .5)])}" opacity="{rnd.uniform(.45, .9):.2f}"/>')
    y0 = H - 46 if kind != "cover" else 820
    x0 = 1200 if kind == "cover" else 1500
    out.append(f'<path d="M{x0} {y0} h120 l30 -60 l40 120 l30 -90 l20 30 h{W - x0 - 240}" fill="none" stroke="{c["secondary"]}" stroke-width="5" stroke-linejoin="round" opacity=".8"/>')
    return "".join(out)


def confetti(c, kind, rnd):
    cols = [c["primary"], c["secondary"], c["accent"], _mix(c["primary"], "#FFFFFF", .4)]
    out = []
    n = 90 if kind == "cover" else 34
    for _ in range(n):
        if kind == "cover":
            x, y = rnd.uniform(0, W), rnd.choice([rnd.uniform(0, 160), rnd.uniform(940, H), rnd.uniform(0, H)])
            if 120 < x < 1150 and 200 < y < 900:
                continue
        else:
            x, y = rnd.choice(_edges(rnd, 1))
        col = rnd.choice(cols)
        r = rnd.uniform(5, 13)
        if rnd.random() < .5:
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{r * 2.2:.0f}" height="{r * .9:.0f}" rx="3" fill="{col}" transform="rotate({rnd.uniform(0, 180):.0f} {x:.0f} {y:.0f})"/>')
        else:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{col}"/>')
    return "".join(out)


def halfcircles(c, kind, rnd):
    out = []
    if kind == "cover":
        out.append(f'<circle cx="{W - 120}" cy="-80" r="380" fill="{c["primary"]}"/>')
        out.append(f'<circle cx="{W - 120}" cy="-80" r="460" fill="none" stroke="{c["accent"]}" stroke-width="10"/>')
        out.append(f'<circle cx="80" cy="{H + 60}" r="230" fill="{c["secondary"]}"/>')
        out.append(f'<circle cx="300" cy="{H - 10}" r="60" fill="{c["accent"]}"/>')
    else:
        out.append(f'<circle cx="-20" cy="-20" r="110" fill="{c["primary"]}"/>')
        out.append(f'<circle cx="-20" cy="-20" r="140" fill="none" stroke="{c["accent"]}" stroke-width="5"/>')
        out.append(f'<circle cx="{W + 30}" cy="{H + 30}" r="120" fill="{c["secondary"]}"/>')
    return "".join(out)


def ribbon(c, kind, rnd):
    out = []
    if kind == "cover":
        out.append(f'<polygon points="{W - 760},-10 {W - 520},-10 {W + 10},520 {W + 10},760" fill="{c["primary"]}"/>')
        out.append(f'<polygon points="{W - 470},-10 {W - 400},-10 {W + 10},400 {W + 10},470" fill="{c["accent"]}"/>')
        out.append(f'<polygon points="-10,{H - 420} 360,{H + 10} 180,{H + 10} -10,{H - 200}" fill="{c["secondary"]}"/>')
    else:
        out.append(f'<polygon points="-10,180 -10,40 110,-10 250,-10" fill="{c["primary"]}"/>')
        out.append(f'<polygon points="-10,260 -10,215 300,-10 345,-10" fill="{c["accent"]}"/>')
    return "".join(out)


def ornate(c, kind, rnd):
    col = c["accent"]
    ins = 26 if kind != "cover" else 40
    out = [f'<rect x="{ins}" y="{ins}" width="{W - 2 * ins}" height="{H - 2 * ins}" fill="none" stroke="{col}" stroke-width="3"/>',
           f'<rect x="{ins + 10}" y="{ins + 10}" width="{W - 2 * ins - 20}" height="{H - 2 * ins - 20}" fill="none" stroke="{col}" stroke-width="1.2"/>']
    for (x, y, sx, sy) in ((ins, ins, 1, 1), (W - ins, ins, -1, 1), (W - ins, H - ins, -1, -1), (ins, H - ins, 1, -1)):
        out.append(f'<g transform="translate({x} {y}) scale({sx} {sy})"><path d="M0 0 h70 M0 0 v70 M10 10 C40 10 50 30 50 50 C30 50 10 40 10 10Z" fill="{col}" stroke="{col}" stroke-width="2"/>'
                   f'<circle cx="62" cy="62" r="6" fill="{col}"/></g>')
    return "".join(out)


def bubbles(c, kind, rnd):
    cols = [c["primary"], c["secondary"], c["accent"]]
    out = []
    pts = [(rnd.uniform(1150, 1900), rnd.uniform(0, H)) for _ in range(26)] if kind == "cover" else _edges(rnd, 10)
    for k, (x, y) in enumerate(pts):
        r = rnd.uniform(10, 70) * (1 if kind == "cover" else .5)
        if k % 3 == 0:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="none" stroke="{cols[k % 3]}" stroke-width="4" opacity=".7"/>')
        else:
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{cols[k % 3]}" opacity="{rnd.uniform(.35, .8):.2f}"/>')
            out.append(f'<circle cx="{x - r * .35:.0f}" cy="{y - r * .35:.0f}" r="{r * .22:.0f}" fill="#FFFFFF" opacity=".5"/>')
    return "".join(out)


PACKS: Dict[str, Callable] = {
    "tropic": tropic, "floral": floral, "plexus": plexus, "shards": shards, "gold": gold, "clouds": clouds,
    "waves": waves, "bars": bars, "brush": brush, "doodles": doodles, "medical": medical, "confetti": confetti,
    "halfcircles": halfcircles, "ribbon": ribbon, "ornate": ornate, "bubbles": bubbles,
}

# packs that suit each tone (light/cream/dark/vivid)
PACK_TONES = {
    "tropic": "light cream dark vivid", "floral": "light cream", "plexus": "light dark vivid", "shards": "light cream dark vivid",
    "gold": "dark cream vivid", "clouds": "light vivid", "waves": "light cream dark vivid", "bars": "light cream dark vivid",
    "brush": "light cream vivid", "doodles": "light cream", "medical": "light", "confetti": "light cream vivid",
    "halfcircles": "light cream dark vivid", "ribbon": "light cream dark vivid", "ornate": "cream dark", "bubbles": "light dark vivid",
}


def pack_svg(name: str, palette: Dict[str, str], kind: str = "content", seed: int = 0) -> str:
    fn = PACKS.get(name)
    if not fn:
        return ""
    c = dict(palette)
    c.setdefault("ink", "#111111")
    mirror = kind == "cover-mirror"
    kind = "cover" if mirror else kind
    rnd = random.Random(f"{name}-{kind}-{seed}")
    body = fn(c, kind, rnd)
    if mirror:  # cover text sits on the right: put the composition on the left
        body = f'<g transform="translate({W} 0) scale(-1 1)">{body}</g>'
    return _wrap(body)
