"""Pictures of the font library for the bot's font picker (a page of fonts, each written in itself)."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from services.deck import fonts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "storage", "gallery_cache", "fonts_v1")
PAGE = 8
SAMPLE = {"title": "Fotosintez jarayoni", "body": "Taqdimot matni shunday ko‘rinadi, 2026"}

W, ROW, PAD = 1080, 118, 26
BG, CARD, INK, MUTED, ACCENT = (244, 245, 250), (255, 255, 255), (22, 24, 40), (120, 126, 150), (110, 123, 255)


def category_fonts(category: str) -> List[dict]:
    """(index in the whole library, entry) of one category; "all" = every font."""
    return [dict(e, index=i) for i, e in enumerate(fonts.library_fonts()) if category in ("all", e["category"])]


def pages(category: str) -> int:
    return max(1, (len(category_fonts(category)) + PAGE - 1) // PAGE)


def page_fonts(category: str, page: int) -> List[dict]:
    items = category_fonts(category)
    return items[page * PAGE:(page + 1) * PAGE]


@lru_cache(maxsize=4)
def _label_font(size: int):
    path = (fonts.font_paths("g:inter") or [None])[0]
    try:
        f = ImageFont.truetype(path, size)
        _set_weight(f, 600)
        return f
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _set_weight(f, weight: int) -> None:
    try:
        axes = f.get_variation_axes()
    except Exception:  # noqa: BLE001 - not a variable font
        return
    vals = []
    for a in axes:
        name = a.get("name", b"")
        name = name.decode() if isinstance(name, bytes) else str(name)
        if name.lower().startswith("weight") or name.lower() == "wght":
            vals.append(max(a["minimum"], min(a["maximum"], weight)))
        else:
            vals.append(a.get("default", a["minimum"]))
    try:
        f.set_variation_by_axes(vals)
    except Exception:  # noqa: BLE001
        pass


def _sample_font(entry: dict, role: str, size: int):
    files = entry["files"]
    want = 700 if role == "title" else 400
    if files[0].get("variable"):
        path = fonts.font_paths(entry["key"])[0]
    else:
        f = min(files, key=lambda x: abs(int(x["weight"]) - want))
        path = os.path.join(os.path.dirname(fonts.font_paths(entry["key"])[0]), f["file"])
    font = ImageFont.truetype(path, size)
    _set_weight(font, want)
    return font


def _fit(draw, text, entry, role, max_w, size):
    while size > 18:
        f = _sample_font(entry, role, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 3
    return _sample_font(entry, role, size)


def sheet(category: str, page: int, role: str) -> Optional[str]:
    items = page_fonts(category, page)
    if not items:
        return None
    out = os.path.join(CACHE, f"{role}_{category}_{page}.jpg")
    if os.path.exists(out):
        return out
    h = PAD + len(items) * (ROW + 12) + PAD - 12
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    label, badge_f = _label_font(22), _label_font(18)
    text = SAMPLE[role]
    for k, e in enumerate(items):
        y = PAD + k * (ROW + 12)
        d.rounded_rectangle((PAD, y, W - PAD, y + ROW), radius=22, fill=CARD)
        n = str(page * PAGE + k + 1)
        d.ellipse((PAD + 20, y + 33, PAD + 72, y + 85), fill=ACCENT)
        tw = d.textlength(n, font=label)
        d.text((PAD + 46 - tw / 2, y + 45), n, font=label, fill=(255, 255, 255))
        d.text((PAD + 96, y + 14), e["name"], font=label, fill=MUTED)
        if e.get("cyrillic"):
            x0 = PAD + 96 + d.textlength(e["name"], font=label) + 12
            d.rounded_rectangle((x0, y + 15, x0 + 40, y + 41), radius=8, fill=(232, 236, 255))
            d.text((x0 + 8, y + 17), "RU", font=badge_f, fill=ACCENT)
        try:
            f = _fit(d, text, e, role, W - PAD * 2 - 130, 50 if role == "title" else 40)
            d.text((PAD + 96, y + 46), text, font=f, fill=INK)
        except Exception:  # noqa: BLE001 - one broken font must not break the page
            d.text((PAD + 96, y + 52), text, font=label, fill=INK)
    os.makedirs(CACHE, exist_ok=True)
    img.save(out, quality=88)
    return out
