"""
Template gallery images.

* Static (built by scripts/build_gallery.py, shipped in webapp/thumbs/):
    <template>/<n>.webp       6 preview slides in the template's default colours
    <template>/c/<slug>.webp  cover in every other colour set
* On demand (served by bot/webhook_app.py at /webapp/preview/<key>/<n>.webp):
    the 6 preview slides in any colour set, rendered once and cached in storage/preview_cache.
* Photo templates (201-400) have no static thumbs: their previews need real photos, so the bot
  server renders them on demand (and warms the covers up in the background after start).
* Inline-keyboard gallery: colour grid per template and cover collages for template lists.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import shutil
import tempfile
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_DIR = os.path.join(ROOT, "webapp")
THUMBS_DIR = os.path.join(WEBAPP_DIR, "thumbs")
GALLERY_VERSION = "5"  # bump when templates change so cached previews are rebuilt
PREVIEW_CACHE = os.path.join(ROOT, "storage", "preview_cache", "v" + GALLERY_VERSION)
GALLERY_CACHE = os.path.join(ROOT, "storage", "gallery_cache", "v" + GALLERY_VERSION)
SAMPLE = os.path.join(ROOT, "assets", "sample_content.json")

PREVIEW_SLIDES = [1, 2, 4, 9, 13]      # sample deck slides shown after the cover
PREVIEW_SIZE = (640, 360)
COVER_SIZE = (480, 270)
KEY_RE = re.compile(r"^[0-9a-z_]+(~[a-z]+)?$")

_locks: Dict[str, asyncio.Lock] = {}
_render_sem: Optional[asyncio.Semaphore] = None


def _sem() -> asyncio.Semaphore:
    """At most one gallery render at a time: keeps the bot responsive on a small server."""
    global _render_sem
    if _render_sem is None:
        _render_sem = asyncio.Semaphore(1)
    return _render_sem


def is_live(template_id: str) -> bool:
    """Templates whose previews are rendered on the server (photo templates)."""
    from services.deck import themes
    return bool(themes.get_theme(themes.split_key(template_id)[0]).get("photo"))


def sample_content(cover_only: bool = False) -> dict:
    with open(SAMPLE, encoding="utf-8") as f:
        c = copy.deepcopy(json.load(f))
    c["slides"] = [] if cover_only else [c["slides"][i] for i in PREVIEW_SLIDES]
    return c


async def render_set(key: str, out_dir: str, cover_only: bool = False, size=PREVIEW_SIZE, quality: int = 74) -> List[str]:
    """Renders the preview slides of one template/colour key as WebP files n.webp in out_dir."""
    from services.deck import render_deck

    tmp = tempfile.mkdtemp(prefix="gal_")
    try:
        async with _sem():
            res = await render_deck(sample_content(cover_only), key, tmp, want_pdf=False, want_pptx=False,
                                    png_scale=0.5 if size[0] > 480 else 0.34, fetch_images=is_live(key))
        os.makedirs(out_dir, exist_ok=True)
        paths = []
        for i, p in enumerate(res.slide_pngs):
            dst = os.path.join(out_dir, f"{i}.webp")
            Image.open(p).convert("RGB").resize(size, Image.LANCZOS).save(dst, "WEBP", quality=quality, method=6)
            paths.append(dst)
        return paths
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def preview_path(key: str, n: int) -> Optional[str]:
    """Path of preview slide n for a template/colour key, rendering the set on first request."""
    from services.deck import themes

    if not KEY_RE.match(key or "") or not themes.is_known_theme(key) or not 0 <= n <= len(PREVIEW_SLIDES):
        return None
    key = themes.resolve_theme_id(key)
    base, color = themes.split_key(key)
    if not color:
        p = os.path.join(THUMBS_DIR, base, f"{n}.webp")
        if os.path.exists(p):
            return p
    out = os.path.join(PREVIEW_CACHE, key.replace("~", "__"))
    p = os.path.join(out, f"{n}.webp")
    if os.path.exists(p):
        return p
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if not os.path.exists(p):
            await render_set(key, out)
    return p if os.path.exists(p) else None


# ------------------------------------------------------------------ inline gallery images
def _font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cover_thumb(key: str) -> Optional[str]:
    """Existing cover image for a template/colour key (static thumb or server-rendered cache)."""
    from services.deck import themes

    base, color = themes.split_key(key)
    p = os.path.join(THUMBS_DIR, base, "c", f"{color}.webp") if color else os.path.join(THUMBS_DIR, base, "0.webp")
    if os.path.exists(p):
        return p
    for q in (os.path.join(PREVIEW_CACHE, "covers", f"{key.replace('~', '__')}.webp"),
              os.path.join(PREVIEW_CACHE, key.replace("~", "__"), "0.webp")):
        if os.path.exists(q):
            return q
    return None


async def cover_path(key: str) -> Optional[str]:
    """Cover of any template/colour key, rendering (cover only) on first request."""
    from services.deck import themes

    if not KEY_RE.match(key or "") or not themes.is_known_theme(key):
        return None
    key = themes.resolve_theme_id(key)
    p = cover_thumb(key)
    if p:
        return p
    out_dir = os.path.join(PREVIEW_CACHE, "covers")
    dst = os.path.join(out_dir, f"{key.replace('~', '__')}.webp")
    lock = _locks.setdefault("cover:" + key, asyncio.Lock())
    async with lock:
        if not os.path.exists(dst):
            tmp_dir = os.path.join(out_dir, "_" + key.replace("~", "__"))
            try:
                paths = await render_set(key, tmp_dir, cover_only=True, size=COVER_SIZE, quality=72)
                if paths:
                    os.replace(paths[0], dst)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
    return dst if os.path.exists(dst) else None


async def ensure_covers(keys: List[str]) -> None:
    for k in keys:
        try:
            await cover_path(k)
        except Exception:  # noqa: BLE001 - a missing preview must never break the gallery
            pass


async def warm_up(delay: float = 20.0) -> None:
    """Background task: renders the covers of all server-rendered templates after start."""
    import logging
    from services.deck import themes

    await asyncio.sleep(delay)
    ids = [t for t in themes.list_theme_ids() if is_live(t)]
    done = 0
    for tid in ids:
        try:
            if await cover_path(tid):
                done += 1
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).info("gallery warm-up %s: %s", tid, e)
        await asyncio.sleep(0.2)
    logging.getLogger(__name__).info("gallery warm-up finished: %d/%d photo template covers", done, len(ids))


def _grid(items, out_path: str, cols: int, tw: int, label_h: int = 44, font_size: int = 24) -> Optional[str]:
    items = [(p, t) for p, t in items if p]
    if not items:
        return None
    th = tw * 9 // 16
    gap = 12
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * gap, rows * (th + label_h) + (rows + 1) * gap), (22, 22, 28))
    d = ImageDraw.Draw(sheet)
    f = _font(font_size)
    for i, (img, text) in enumerate(items):
        x, y = gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + label_h + gap)
        sheet.paste(Image.open(img).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
        if label_h:
            d.text((x + 4, y + th + 9), text, fill=(238, 238, 244), font=f)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path, quality=86)
    return out_path


async def colors_sheet_async(template_id: str) -> Optional[str]:
    from services.deck import themes
    await ensure_covers([c["key"] for c in themes.theme_colors(template_id)])
    return colors_sheet(template_id)


async def list_sheet_async(template_ids: List[str], name: str) -> Optional[str]:
    await ensure_covers(template_ids)
    return list_sheet(template_ids, name)


def colors_sheet(template_id: str, refresh: bool = False) -> Optional[str]:
    """All colour sets of one template as a grid (photo for the inline gallery)."""
    from services.deck import themes

    out = os.path.join(GALLERY_CACHE, f"colors_{template_id}.jpg")
    if os.path.exists(out) and not refresh:
        return out
    items = [(cover_thumb(c["key"]), f"{i + 1}. {c['name']}") for i, c in enumerate(themes.theme_colors(template_id))]
    return _grid(items, out, cols=5, tw=420)


def list_sheet(template_ids: List[str], name: str, refresh: bool = False) -> Optional[str]:
    """Covers of a page of templates (photo for the inline gallery list)."""
    from services.deck import themes

    out = os.path.join(GALLERY_CACHE, f"list_{name}.jpg")
    if os.path.exists(out) and not refresh:
        return out
    items = []
    for tid in template_ids:
        t = themes.get_theme(tid)
        items.append((cover_thumb(tid), f"{int(t['code'])}. {t['name']}"))
    return _grid(items, out, cols=4, tw=440)
