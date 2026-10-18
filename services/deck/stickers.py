"""
Subject stickers for slides.

Every deck gets illustrations that match its subject (biology -> leaf, DNA, microscope...;
maths -> compass, ruler, pi...), drawn in the template's own sticker style and colours. The same
drawing looks very different as a die-cut sticker, a chunky 3D toy, a risograph print, a line
drawing, glass, a doodle, a badge or a flat icon, so 200 templates never share one look.
"""
from __future__ import annotations

import re
from typing import Dict, List

from services.deck.sticker_art import ART, SUBJECTS

STYLES = ["diecut", "chunky", "riso", "line", "glass", "badge", "doodle", "flat", "mono"]
_ROLE = re.compile(r"\$([PSATULDG])")


def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def _mix(a: str, b: str, t: float) -> str:
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(ca[i] * (1 - t) + cb[i] * t for i in range(3)))


def _roles(p: Dict[str, str]) -> Dict[str, str]:
    dark = "#1E2230"
    return {"P": p["primary"], "S": p["secondary"], "A": p["accent"], "T": _mix(p["primary"], "#FFFFFF", .62),
            "U": _mix(p["secondary"], "#FFFFFF", .62), "L": "#FFFFFF", "D": dark, "G": "#C9CFDA"}


def _paint(body: str, roles: Dict[str, str]) -> str:
    return _ROLE.sub(lambda m: roles[m.group(1)], body)


def _wrap(inner: str, size: int) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-12 -12 124 124" width="{size}" height="{size}" '
            f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>')


def render(name: str, palette: Dict[str, str], style: str = "diecut", size: int = 160) -> str:
    """One sticker as a standalone SVG string."""
    body = ART.get(name) or ART["star"]
    r = _roles(palette)
    D = r["D"]
    if style == "line":
        r = {**r, "P": r["T"], "S": r["U"], "G": "#FFFFFF"}
    elif style == "mono":
        r = {**r, "S": _mix(palette["primary"], D, .35), "A": _mix(palette["primary"], "#FFFFFF", .35), "U": r["T"], "G": r["T"]}
    art = _paint(body, r)
    flat_fills = _paint(body, {k: D for k in r})
    nofill = re.sub(r'fill="#[0-9A-Fa-f]{6}"', 'fill="none"', art)

    if style == "diecut":
        inner = (f'<g transform="translate(3 5)" fill="{D}" stroke="{D}" stroke-width="14" opacity=".22">{flat_fills}</g>'
                 f'<g fill="#FFFFFF" stroke="#FFFFFF" stroke-width="14">{_paint(body, {k: "#FFFFFF" for k in r})}</g>'
                 f'<g stroke="{D}" stroke-width="3">{art}</g>')
    elif style == "chunky":
        inner = (f'<g transform="translate(5 7)" stroke="{D}" stroke-width="4">{flat_fills}</g>'
                 f'<g stroke="{D}" stroke-width="4">{art}</g>')
    elif style == "riso":
        inner = (f'<g transform="translate(4 3)" stroke="none" opacity=".92">{art}</g>'
                 f'<g stroke="{D}" stroke-width="2.4">{nofill}</g>')
    elif style == "line":
        inner = f'<g stroke="{D}" stroke-width="3.2">{art}</g>'
    elif style == "glass":
        inner = (f'<g transform="translate(0 6)" fill="{D}" stroke="none" opacity=".16">{flat_fills}</g>'
                 f'<g stroke="#FFFFFF" stroke-width="2.4" opacity=".93">{art}</g>'
                 '<ellipse cx="34" cy="26" rx="26" ry="11" fill="#FFFFFF" opacity=".28" transform="rotate(-24 34 26)"/>')
    elif style == "badge":
        inner = (f'<circle cx="50" cy="50" r="58" fill="{r["T"]}" stroke="{D}" stroke-width="3"/>'
                 f'<circle cx="50" cy="50" r="51" fill="none" stroke="{palette["primary"]}" stroke-width="2.5" stroke-dasharray="4 5"/>'
                 f'<g transform="translate(50 50) scale(.7) translate(-50 -50)" stroke="{D}" stroke-width="3.4">{art}</g>')
    elif style == "doodle":
        inner = (f'<g transform="translate(2.5 2) rotate(-2 50 50)" stroke="none">{art}</g>'
                 f'<g stroke="{D}" stroke-width="2.2">{nofill}</g>'
                 f'<g stroke="{D}" stroke-width="1.3" transform="translate(-1.4 1.1) rotate(1.4 50 50)" opacity=".75">{nofill}</g>')
    elif style == "mono":
        inner = f'<g stroke="{D}" stroke-width="3">{art}</g>'
    else:  # flat
        inner = f'<g stroke="{_mix(palette["primary"], D, .55)}" stroke-width="2">{art}</g>'
    return _wrap(inner, size)


def detect_subject(content: Dict) -> str:
    ts = content.get("title_slide", {}) or {}
    text = " ".join(str(x) for x in (ts.get("subject", ""), ts.get("subject", ""), ts.get("title", ""),
                                     (content.get("meta") or {}).get("subject", ""))).lower()
    best, score = "general", 0
    for key, (words, _) in SUBJECTS.items():
        n = sum(text.count(w) for w in words)
        if n > score:
            best, score = key, n
    return best


def subject_stickers(subject: str) -> List[str]:
    return list(SUBJECTS.get(subject, SUBJECTS["general"])[1])


def pick(subject: str, index: int, offset: int = 0) -> str:
    names = subject_stickers(subject)
    return names[(index + offset) % len(names)]
