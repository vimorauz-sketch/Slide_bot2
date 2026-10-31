"""
Makes a referat end to end: text (AI) → real photos (if the user wants pictures) → PDF + Word
→ preview pictures with a watermark. Everything needed to rebuild the files later is kept in
<storage>/referat.json (and in the order's content_json).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

from services.referat import designs, render, writer

logger = logging.getLogger(__name__)
Progress = Optional[Callable[[str, int, int], Awaitable[None]]]
SAVE_NAME = "referat.json"


@dataclass
class ReferatResult:
    pdf_path: str = ""
    docx_path: str = ""
    previews: List[str] = field(default_factory=list)
    pages: int = 0
    saved: Dict[str, Any] = field(default_factory=dict)


def style_of(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: data.get(k) for k in ("font_title", "font_body") if data.get(k)}


async def _find_images(doc: Dict[str, Any], need_cover: bool) -> Dict[str, Dict[str, Any]]:
    """{"s1.0": {"src": file-uri, "path": local path}, "cover": ...} for the pictures the text asks for."""
    from services.deck import images as img
    resolver = img.ImageResolver({"image_style": "realistic documentary photo"})
    if not resolver.providers:
        return {}
    wanted = []
    for i, s in enumerate(doc.get("sections") or []):
        if s.get("image", {}).get("query"):
            wanted.append((f"s{i}", s["image"]["query"]))
        for j, sub in enumerate(s.get("subsections") or []):
            if (sub.get("image") or {}).get("query"):
                wanted.append((f"s{i}.{j}", sub["image"]["query"]))
    cover_q = (doc.get("cover_image") or {}).get("query") or doc.get("meta", {}).get("topic", "")
    if need_cover and cover_q:
        wanted.append(("cover", cover_q))
    if not wanted:
        return {}
    import aiohttp
    async with aiohttp.ClientSession(headers={"User-Agent": img.UA}) as session:
        results = await asyncio.gather(*(resolver.resolve(session, q, "", "photo", "chart") for _, q in wanted),
                                       return_exceptions=True)
    out = {}
    for (key, _), res in zip(wanted, results):
        if isinstance(res, dict) and str(res.get("src", "")).startswith("file:"):
            out[key] = {"src": res["src"], "path": res["src"][7:], "credit": res.get("credit", "")}
    return out


def _fallback_cover(t: Dict[str, Any]) -> str:
    """No photo found for a photo title page: a drawn picture in the template's colours."""
    from services.deck.art import art_data_uri
    p = t["palette"]
    pal = {"bg": p["soft"], "bg2": p["soft"], "primary": p["accent"], "secondary": p["accent2"], "accent": p["accent2"],
           "text": p["ink"], "muted": p["ink"], "ink": p["ink"], "surface": "#ffffff", "on_primary": "#ffffff"}
    return art_data_uri("botanical", pal, "book", "book", 1200, 700)


def watermark(src: str, dst: str) -> str:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    try:
        from services.deck import fonts
        f = ImageFont.truetype(fonts.font_paths("g:montserrat")[0], max(18, w // 16))
    except Exception:  # noqa: BLE001
        f = ImageFont.load_default()
    text = "NAMUNA • SLIDELAB"
    for k in range(-2, 6):
        d.text((w * 0.05 + k * 30, h * 0.12 + k * h * 0.17), text, font=f, fill=(120, 120, 140, 70))
    layer = layer.rotate(28, resample=Image.BICUBIC, center=(w / 2, h / 2))
    out = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
    out.save(dst, quality=85)
    return dst


async def render_files(saved: Dict[str, Any], storage_dir: str, want_docx: bool = True) -> ReferatResult:
    """PDF (+ Word) from a saved referat (the text and the pictures already chosen)."""
    os.makedirs(storage_dir, exist_ok=True)
    doc, tid, style = saved["doc"], saved.get("template", designs.DEFAULT), saved.get("style") or {}
    imgs: Dict[str, Dict[str, Any]] = {k: v for k, v in (saved.get("images") or {}).items()
                                       if v.get("path") and os.path.exists(v["path"])}
    t = render.resolve_template(tid, style, doc.get("language", "uz"))
    has_photo = bool(t["layout"].get("photo"))
    cover = imgs.get("cover", {}).get("src", "") if has_photo else ""
    if has_photo and not cover:
        cover = _fallback_cover(t)
    srcs = {k: v["src"] for k, v in imgs.items() if k != "cover"}
    pdf = await render.html_to_pdf(render.build_html(doc, tid, srcs, cover, style), os.path.join(storage_dir, "referat.pdf"))
    res = ReferatResult(pdf_path=pdf, pages=render.page_count(pdf), saved=saved)
    if want_docx:
        from services.referat.docx_export import build_docx
        bg = await render.html_to_png(render.build_html(doc, tid, srcs, cover, style, background_only=True),
                                      os.path.join(storage_dir, "cover_bg.png"))
        vm = render.view_model(doc, t, srcs)
        paths = {k: v["path"] for k, v in imgs.items()}
        res.docx_path = await asyncio.to_thread(build_docx, os.path.join(storage_dir, "referat.docx"), vm, t, bg, paths,
                                                render.running_title(t, vm["m"].get("topic", "")))
    return res


async def build_referat(data: Dict[str, Any], storage_dir: str, progress: Progress = None,
                        doc: Optional[Dict[str, Any]] = None) -> ReferatResult:
    """progress(stage, done, total): stages "write", "photos", "render", "previews"."""
    async def tick(stage, done, total):
        if progress:
            try:
                await progress(stage, done, total)
            except Exception:  # noqa: BLE001
                pass

    os.makedirs(storage_dir, exist_ok=True)
    tid = data.get("referat_template") or designs.DEFAULT
    t = designs.get(tid)
    if doc is None:
        await tick("write", 0, 1)
        doc = await writer.write_document(data, progress=lambda d, n: tick("write", d, n))
    if not doc.get("meta"):
        doc["meta"] = writer.build_meta(data)
    await tick("photos", 0, 1)
    try:
        images = await _find_images(doc, need_cover=bool(t["layout"].get("photo")))
    except Exception:  # noqa: BLE001 - a referat without pictures is still a referat
        logger.exception("referat photos failed")
        images = {}
    await tick("photos", 1, 1)
    saved = {"doc": doc, "template": tid, "style": style_of(data), "images": images}
    with open(os.path.join(storage_dir, SAVE_NAME), "w", encoding="utf-8") as f:
        json.dump(saved, f, ensure_ascii=False)
    await tick("render", 0, 1)
    res = await render_files(saved, storage_dir, want_docx=True)
    await tick("render", 1, 1)
    await tick("previews", 0, 1)
    first_chapter = next((k for k, s in enumerate(doc.get("sections") or []) if s.get("kind") == "chapter"), 1)
    pages = await asyncio.to_thread(render.pdf_pages_to_images, res.pdf_path, os.path.join(storage_dir, "pv"),
                                    [0, min(res.pages - 1, 2 + first_chapter)], 900, "page")
    res.previews = [watermark(pth, pth.replace(".jpg", "_wm.jpg")) for pth in pages]
    await tick("previews", 1, 1)
    return res


async def ensure_files(storage_dir: str) -> ReferatResult:
    """Rebuilds the PDF and Word files from referat.json (after a redeploy wiped them)."""
    pdf, docx_ = os.path.join(storage_dir, "referat.pdf"), os.path.join(storage_dir, "referat.docx")
    if os.path.exists(pdf) and os.path.exists(docx_):
        return ReferatResult(pdf_path=pdf, docx_path=docx_, pages=render.page_count(pdf))
    with open(os.path.join(storage_dir, SAVE_NAME), encoding="utf-8") as f:
        saved = json.load(f)
    return await render_files(saved, storage_dir, want_docx=True)


def content_for_db(saved: Dict[str, Any]) -> str:
    return json.dumps({"referat": saved}, ensure_ascii=False)
