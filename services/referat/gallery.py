"""Pictures of the referat templates: the title page and an inner page of a sample referat
(for the Mini App and the inline gallery in the bot). Bundled pictures in webapp/referat/thumbs
are used when they exist; others are drawn once and cached."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from typing import Dict, List, Optional

from PIL import Image, ImageDraw

from services.referat import designs

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLED = os.path.join(ROOT, "webapp", "referat", "thumbs")
CACHE = os.path.join(ROOT, "storage", "gallery_cache", "referat_v2")
SAMPLE = os.path.join(ROOT, "assets", "referat_sample.json")
SAMPLES = os.path.join(ROOT, "assets", "samples")
# sample pictures drawn for each sample topic: (art style, icon)
TOPIC_ART = {"photosynthesis": ("botanical", "leaf"), "timur": ("ikat", "landmark"), "heart": ("medical", "heart-pulse"),
             "ai": ("circuit", "brain-circuit"), "startup": ("isometric", "rocket"), "navoi": ("ink", "feather"),
             "climate": ("topo", "thermometer-sun"), "pedagogy": ("doodle", "graduation-cap")}
PAGES = {1: 0, 4: 3}       # picture name -> PDF page index (title page, first chapter page)
WIDTH = 620
PAGE_SIZE = 10
_locks: Dict[str, asyncio.Lock] = {}
_sem: Optional[asyncio.Semaphore] = None


def _sample_images(t: dict):
    from services.deck.art import art_data_uri
    p = t["palette"]
    pal = {"bg": p["soft"], "bg2": p["soft"], "primary": p["accent"], "secondary": p["accent2"], "accent": p["accent2"],
           "text": p["ink"], "muted": p["ink"], "ink": p["ink"], "surface": "#ffffff", "on_primary": "#ffffff"}
    style, icon = TOPIC_ART.get(t.get("topic", ""), TOPIC_ART["photosynthesis"])
    img = art_data_uri(style, pal, icon, icon, 800, 500)
    img2 = art_data_uri(style, pal, icon, icon, 800, 500, seed=1)
    return {"s1.0": img, "s2.1": img2}, art_data_uri(style, pal, icon, icon, 1200, 900, seed=2, badge=False)


def sample_doc(t: dict) -> dict:
    """The sample referat on the template's own topic (falls back to the photosynthesis one)."""
    p = os.path.join(SAMPLES, f"referat_{t.get('topic', '')}.json")
    with open(p if os.path.exists(p) else SAMPLE, encoding="utf-8") as f:
        return json.load(f)


def path(template_id: str, n: int) -> Optional[str]:
    for d in (BUNDLED, CACHE):
        p = os.path.join(d, f"{template_id}_{n}.jpg")
        if os.path.exists(p):
            return p
    return None


async def ensure(template_id: str) -> None:
    """Draws both pictures of a template if they are missing."""
    global _sem
    if template_id not in designs.BY_ID or all(path(template_id, n) for n in PAGES):
        return
    lock = _locks.setdefault(template_id, asyncio.Lock())
    if _sem is None:
        _sem = asyncio.Semaphore(2)
    async with lock:
        if all(path(template_id, n) for n in PAGES):
            return
        from services.referat import render
        t = designs.get(template_id)
        doc = sample_doc(t)
        images, cover = _sample_images(t)
        tmp = tempfile.mkdtemp(prefix="refgal_")
        try:
            async with _sem:
                pdf = await render.html_to_pdf(render.build_html(doc, template_id, images, cover),
                                               os.path.join(tmp, "s.pdf"))
            os.makedirs(CACHE, exist_ok=True)
            for n, idx in PAGES.items():
                out = await asyncio.to_thread(render.pdf_pages_to_images, pdf, tmp, [idx], WIDTH, f"p{n}")
                if out:
                    Image.open(out[0]).convert("RGB").save(os.path.join(CACHE, f"{template_id}_{n}.jpg"), quality=80)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


async def page_path(template_id: str, n: int) -> Optional[str]:
    if n not in PAGES:
        return None
    if not path(template_id, n):
        await ensure(template_id)
    return path(template_id, n)


def pages() -> int:
    return (len(designs.TEMPLATES) + PAGE_SIZE - 1) // PAGE_SIZE


def page_ids(page: int) -> List[str]:
    return [t["id"] for t in designs.TEMPLATES[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]]


async def sheet(page: int) -> Optional[str]:
    """Title pages of one page of templates as a numbered grid (5 × 2) for the bot."""
    ids = page_ids(page)
    if not ids:
        return None
    out = os.path.join(CACHE, f"sheet_{page}.jpg")
    if os.path.exists(out):
        return out
    for tid in ids:
        await ensure(tid)
    tw, th, gap, label = 300, 424, 14, 46
    cols = 5
    rows = (len(ids) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + label) + (rows + 1) * gap), (232, 235, 241))
    d = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        from services.deck import fonts
        f = ImageFont.truetype(fonts.font_paths("g:inter")[0], 24)
        try:
            f.set_variation_by_axes([700, 14])
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        f = None
    for k, tid in enumerate(ids):
        t = designs.get(tid)
        x, y = gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + label + gap)
        p = path(tid, 1)
        if p:
            img.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        d.rectangle((x, y, x + tw - 1, y + th - 1), outline=(200, 204, 214))
        d.text((x + 4, y + th + 10), f"{t['code']}. {t['name']}", fill=(28, 34, 48), font=f)
    os.makedirs(CACHE, exist_ok=True)
    img.save(out, quality=84)
    return out
