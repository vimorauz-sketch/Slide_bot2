"""SVG charts and diagram geometry, coloured through the theme's CSS variables."""
from __future__ import annotations

import math
from html import escape
from typing import Any, Dict, List


def _nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _fmt(v: float, unit: str = "") -> str:
    if abs(v - round(v)) < 1e-9:
        s = f"{int(round(v)):,}".replace(",", " ")
    else:
        s = f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{s}{unit}" if unit in ("%",) else (f"{s} {unit}".strip() if unit else s)


def chart_svg(chart: Dict[str, Any]) -> str:
    ctype = chart.get("type", "column")
    if ctype in ("donut", "pie"):
        return _donut(chart, hole=ctype == "donut")
    if ctype == "line":
        return _line(chart)
    if ctype == "bar":
        return _hbar(chart)
    return _column(chart)


def _column(chart: Dict[str, Any]) -> str:
    W, H = 1000, 560
    left, right, top, bottom = 70, 20, 40, 70
    labels: List[str] = chart["labels"]
    series = chart["series"]
    unit = chart.get("unit", "")
    vmax = _nice_max(max((max(s["values"]) for s in series), default=1))
    pw, ph = W - left - right, H - top - bottom
    n, k = len(labels), len(series)
    group = pw / max(n, 1)
    bw = min(90, group * 0.64 / k)
    out = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">']
    for i in range(5):
        y = top + ph * i / 4
        val = vmax * (1 - i / 4)
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text x="{left - 14}" y="{y + 7:.1f}" text-anchor="end">{escape(_fmt(val))}</text>')
    for gi, lab in enumerate(labels):
        gx = left + group * gi + (group - bw * k) / 2
        for si, s in enumerate(series):
            v = s["values"][gi]
            h = ph * (v / vmax) if vmax else 0
            x = gx + si * bw
            y = top + ph - h
            out.append(f'<rect x="{x + 3:.1f}" y="{y:.1f}" width="{bw - 6:.1f}" height="{h:.1f}" rx="8" fill="var(--c{si + 1})"/>')
            if k == 1:
                out.append(f'<text class="val" x="{x + bw / 2:.1f}" y="{y - 12:.1f}" text-anchor="middle">{escape(_fmt(v, unit))}</text>')
        out.append(f'<text x="{left + group * gi + group / 2:.1f}" y="{H - bottom + 38}" text-anchor="middle">{escape(lab)}</text>')
    out.append(f'<line class="axis" x1="{left}" x2="{W - right}" y1="{top + ph}" y2="{top + ph}"/>')
    out.append("</svg>")
    return "".join(out)


def _hbar(chart: Dict[str, Any]) -> str:
    W, H = 1000, 560
    labels, series, unit = chart["labels"], chart["series"], chart.get("unit", "")
    left, right, top, bottom = 230, 90, 20, 20
    vmax = _nice_max(max((max(s["values"]) for s in series), default=1))
    n, k = len(labels), len(series)
    row = (H - top - bottom) / max(n, 1)
    bh = min(56, row * 0.7 / k)
    out = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">']
    for gi, lab in enumerate(labels):
        gy = top + row * gi + (row - bh * k) / 2
        out.append(f'<text x="{left - 20}" y="{top + row * gi + row / 2 + 7:.1f}" text-anchor="end">{escape(lab)}</text>')
        for si, s in enumerate(series):
            v = s["values"][gi]
            w = (W - left - right) * (v / vmax) if vmax else 0
            y = gy + si * bh
            out.append(f'<rect x="{left}" y="{y + 3:.1f}" width="{max(w, 4):.1f}" height="{bh - 6:.1f}" rx="8" fill="var(--c{si + 1})"/>')
            out.append(f'<text class="val" x="{left + w + 12:.1f}" y="{y + bh / 2 + 8:.1f}">{escape(_fmt(v, unit))}</text>')
    out.append("</svg>")
    return "".join(out)


def _line(chart: Dict[str, Any]) -> str:
    W, H = 1000, 560
    left, right, top, bottom = 70, 40, 40, 70
    labels, series, unit = chart["labels"], chart["series"], chart.get("unit", "")
    vals = [v for s in series for v in s["values"]]
    vmax = _nice_max(max(vals, default=1))
    pw, ph = W - left - right, H - top - bottom
    n = len(labels)
    step = pw / max(n - 1, 1)
    out = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">']
    out.append('<defs>' + "".join(
        f'<linearGradient id="lg{si}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--c{si + 1})" stop-opacity=".28"/>'
        f'<stop offset="1" stop-color="var(--c{si + 1})" stop-opacity="0"/></linearGradient>' for si in range(len(series))) + '</defs>')
    for i in range(5):
        y = top + ph * i / 4
        out.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text x="{left - 14}" y="{y + 7:.1f}" text-anchor="end">{escape(_fmt(vmax * (1 - i / 4)))}</text>')
    for i, lab in enumerate(labels):
        out.append(f'<text x="{left + step * i:.1f}" y="{H - bottom + 38}" text-anchor="middle">{escape(lab)}</text>')
    for si, s in enumerate(series):
        pts = [(left + step * i, top + ph - ph * (v / vmax)) for i, v in enumerate(s["values"])]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
        if len(series) == 1:
            area = path + f" L{pts[-1][0]:.1f} {top + ph} L{pts[0][0]:.1f} {top + ph} Z"
            out.append(f'<path d="{area}" fill="url(#lg{si})"/>')
        out.append(f'<path d="{path}" fill="none" stroke="var(--c{si + 1})" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, (x, y) in enumerate(pts):
            last = i == len(pts) - 1
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{11 if last else 7}" fill="var(--c{si + 1})" stroke="var(--card-bg, #fff)" stroke-width="4"/>')
            if len(series) == 1:
                out.append(f'<text class="val" x="{x:.1f}" y="{y - 22:.1f}" text-anchor="middle">{escape(_fmt(s["values"][i], unit))}</text>')
    out.append(f'<line class="axis" x1="{left}" x2="{W - right}" y1="{top + ph}" y2="{top + ph}"/>')
    out.append("</svg>")
    return "".join(out)


def _donut(chart: Dict[str, Any], hole: bool) -> str:
    W, H = 1000, 560
    labels = chart["labels"]
    vals = chart["series"][0]["values"] if chart["series"] else []
    chart.get("unit", "")
    total = sum(v for v in vals if v > 0) or 1
    cx, cy, r = 280, 280, 240
    r_in = 140 if hole else 0
    out = [f'<svg class="chart-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">']
    a0 = -math.pi / 2
    for i, v in enumerate(vals):
        frac = max(v, 0) / total
        a1 = a0 + frac * 2 * math.pi
        large = 1 if frac > 0.5 else 0
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1 - 1e-6), cy + r * math.sin(a1 - 1e-6)
        if hole:
            xi0, yi0 = cx + r_in * math.cos(a1 - 1e-6), cy + r_in * math.sin(a1 - 1e-6)
            xi1, yi1 = cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)
            d = (f"M{x0:.1f} {y0:.1f} A{r} {r} 0 {large} 1 {x1:.1f} {y1:.1f} L{xi0:.1f} {yi0:.1f} "
                 f"A{r_in} {r_in} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z")
        else:
            d = f"M{cx} {cy} L{x0:.1f} {y0:.1f} A{r} {r} 0 {large} 1 {x1:.1f} {y1:.1f} Z"
        out.append(f'<path d="{d}" fill="var(--c{i % 6 + 1})" stroke="var(--card-bg, #fff)" stroke-width="5"/>')
        a0 = a1
    if hole and vals:
        top_i = max(range(len(vals)), key=lambda i: vals[i])
        pct = round(100 * vals[top_i] / total)
        out.append(f'<text class="big" x="{cx}" y="{cy + 14}" text-anchor="middle">{pct}%</text>')
        out.append(f'<text x="{cx}" y="{cy + 56}" text-anchor="middle">{escape(labels[top_i][:18])}</text>')
    ly = cy - (len(labels) * 64) / 2 + 20
    for i, lab in enumerate(labels):
        y = ly + i * 64
        pct = round(100 * max(vals[i], 0) / total) if i < len(vals) else 0
        out.append(f'<rect x="590" y="{y - 20:.1f}" width="26" height="26" rx="7" fill="var(--c{i % 6 + 1})"/>')
        out.append(f'<text x="634" y="{y:.1f}" style="fill:var(--text)">{escape(lab)}</text>')
        out.append(f'<text class="val" x="{W - 20}" y="{y:.1f}" text-anchor="end">{pct}%</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- cycle
def cycle_geometry(n: int) -> Dict[str, Any]:
    cx, cy, R = 380, 350, 270
    nodes = []
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * i / n
        nodes.append({"x": cx + R * math.cos(a), "y": cy + R * math.sin(a), "a": a})
    return {"cx": cx, "cy": cy, "R": R, "inner": 150, "nodes": nodes, "center_fs": 34 if n <= 4 else 30}


def cycle_svg(n: int) -> str:
    g = cycle_geometry(n)
    cx, cy, R = g["cx"], g["cy"], g["R"]
    node_r = 46
    out = ['<svg class="cycle-svg" viewBox="0 0 760 700">',
           '<defs><marker id="cyc-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
           '<path d="M0 0L10 5L0 10z" fill="var(--primary)"/></marker></defs>',
           f'<circle class="ring" cx="{cx}" cy="{cy}" r="{R}"/>',
           f'<circle class="center-fill" cx="{cx}" cy="{cy}" r="{g["inner"]}"/>']
    gap = (node_r + 16) / R  # radians kept clear around each node
    for i in range(n):
        a0 = g["nodes"][i]["a"] + gap
        a1 = g["nodes"][(i + 1) % n]["a"] - gap
        if a1 < a0:
            a1 += 2 * math.pi
        x0, y0 = cx + R * math.cos(a0), cy + R * math.sin(a0)
        x1, y1 = cx + R * math.cos(a1), cy + R * math.sin(a1)
        large = 1 if (a1 - a0) > math.pi else 0
        out.append(f'<path class="arc" d="M{x0:.1f} {y0:.1f} A{R} {R} 0 {large} 1 {x1:.1f} {y1:.1f}" marker-end="url(#cyc-arrow)"/>')
    for i, nd in enumerate(g["nodes"]):
        out.append(f'<circle class="node" cx="{nd["x"]:.1f}" cy="{nd["y"]:.1f}" r="{node_r}"/>')
        out.append(f'<text class="node-num" x="{nd["x"]:.1f}" y="{nd["y"]:.1f}">{i + 1}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- pyramid
def pyramid_geometry(n: int) -> List[Dict[str, Any]]:
    total_h = 640
    gap = 10
    h = (total_h - gap * (n - 1)) / n
    base_w = 800
    levels = []
    for i in range(n):
        # Each level is a trapezoid slice of one big triangle.
        top_w = base_w * (i / n)
        bot_w = base_w * ((i + 1) / n)
        inset = (bot_w - top_w) / 2 / bot_w * 100 if bot_w else 0
        levels.append({
            "w": round(bot_w), "h": round(h),
            "l": round(inset, 2), "r": round(100 - inset, 2),
            "fill": f"color-mix(in srgb, var(--primary) {100 - i * (60 // max(n - 1, 1))}%, var(--pyr-to))",
        })
    return levels
