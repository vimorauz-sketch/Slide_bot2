"""
End-to-end presentation build used by the bot: AI content -> photos -> render -> previews.

Everything an order needs later (content.json with the chosen photos, the PPTX, the PDF and
the slide PNGs) is written into the order's storage directory, so downloads after payment never
call the AI again and a missing PDF can be re-rendered byte-for-byte from content.json.
"""
from __future__ import annotations

import json
import logging
import os
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from services import ai_service
from services.deck import render_deck
from services.preview_service import make_overview_grid, make_watermarked_previews

logger = logging.getLogger(__name__)

Progress = Optional[Callable[..., Awaitable[None]]]


@dataclass
class BuildResult:
    storage_dir: str
    content_path: str
    pptx_path: Optional[str]
    pdf_path: Optional[str]
    slide_pngs: List[str] = field(default_factory=list)
    previews: List[str] = field(default_factory=list)
    overview: Optional[str] = None
    content: Dict[str, Any] = field(default_factory=dict)


def theme_key_from_data(data: Dict[str, Any]) -> Any:
    tpl = data.get("template_id", "05_nature_organic")
    base = data["custom_design_spec"] if tpl == "custom_ai" and data.get("custom_design_spec") else tpl
    fonts = {r: data.get(f"font_{r}") for r in ("title", "body") if data.get(f"font_{r}")}
    color = data.get("text_color")
    if not fonts and not color:
        return base
    if data.get("language") == "ru":  # a Latin-only font cannot draw Russian
        from services.deck.fonts import cyrillic_fallback
        fonts = {r: cyrillic_fallback(f) for r, f in fonts.items()}
    style: Dict[str, Any] = {"base": base}
    if fonts:
        style["fonts"] = fonts
    if color:
        style["text_color"] = color
    return style


def refresh_title(content: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """Puts the wizard's latest answers on the title slide (content may have been written in the
    background before the user typed their name, institution, date…)."""
    ts = content.setdefault("title_slide", {})
    for key, field_ in (("author", "author_name"), ("institution", "institution"), ("teacher", "teacher_name"),
                        ("course", "course"), ("date", "date"), ("subject", "subject")):
        ts[key] = data.get(field_, "") or ""
    if not ts["author"]:
        ts["author"] = "Muallif"
    content.setdefault("meta", {})["template_id"] = data.get("template_id")
    return content


async def build_presentation(data: Dict[str, Any], storage_dir: str, outline: Optional[Dict[str, Any]] = None,
                             progress: Progress = None, preview_count: int = 2,
                             content: Optional[Dict[str, Any]] = None, files_now: bool = False) -> BuildResult:
    """Writes (or takes the ready `content`), finds photos and draws the slides.

    progress(stage, done, total) is called with stages "write", "photos", "render", "previews".
    With files_now=False only the slide images and previews are made here (what the user sees
    first); the PDF and PPTX are produced by start_files() in the background."""
    os.makedirs(storage_dir, exist_ok=True)

    async def say(stage: str, done: int = 0, total: int = 0) -> None:
        if progress:
            try:
                await progress(stage, done, total)
            except Exception:  # a failed status edit must never stop the build
                pass

    if content is None:
        await say("write")
        content = await ai_service.generate_presentation_content(
            data, outline, on_progress=lambda d, t: say("write", d, t))
    refresh_title(content, data)
    theme_key = theme_key_from_data(data)

    await say("photos")
    from services.deck.images import resolve_images
    from services.deck.themes import get_theme
    try:
        images = await resolve_images(content, get_theme(theme_key))
    except Exception as e:  # never fail a deck because of pictures
        logger.warning("image lookup failed: %s", e)
        images = {}

    await say("render")
    res = await render_deck(content, theme_key, storage_dir, images=images, fetch_images=False,
                            want_pdf=files_now, want_pptx=files_now)

    content_path = os.path.join(storage_dir, "content.json")
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump({"content": content, "theme": theme_key}, f, ensure_ascii=False, indent=1)

    await say("previews")
    previews = make_watermarked_previews(res.slide_pngs, storage_dir, count=preview_count)
    overview = make_overview_grid(res.slide_pngs, os.path.join(storage_dir, "overview_wm.jpg"), watermark=True)
    pdf = res.pdf_path or os.path.join(storage_dir, "presentation.pdf")
    pptx = res.pptx_path or os.path.join(storage_dir, "presentation.pptx")
    return BuildResult(storage_dir=storage_dir, content_path=content_path, pptx_path=pptx, pdf_path=pdf,
                       slide_pngs=res.slide_pngs, previews=previews, overview=overview, content=content)


# ------------------------------------------------------------------ PDF / PPTX after the previews
_file_tasks: Dict[str, "asyncio.Task"] = {}


def _missing_local_images(content: Dict[str, Any]) -> bool:
    """True when the deck points at photo files this server no longer has (e.g. after a redeploy)."""
    found = []

    def walk(v):
        if isinstance(v, dict):
            src = v.get("src")
            if isinstance(src, str) and src.startswith("file://"):
                found.append(src[7:])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(content)
    return any(not os.path.exists(p) for p in found)


async def _make_files(storage_dir: str) -> None:
    with open(os.path.join(storage_dir, "content.json"), encoding="utf-8") as f:
        saved = json.load(f)
    content = saved["content"]
    await render_deck(content, saved.get("theme", "05_nature_organic"), storage_dir,
                      want_pngs=False, fetch_images=_missing_local_images(content))


def start_files(storage_dir: str) -> "asyncio.Task":
    """Starts building presentation.pdf and .pptx in the background (once per order)."""
    import asyncio
    task = _file_tasks.get(storage_dir)
    if task is None or (task.done() and task.exception() is not None):
        task = asyncio.ensure_future(_make_files(storage_dir))
        _file_tasks[storage_dir] = task
        task.add_done_callback(lambda t: t.cancelled() or t.exception() is None or
                               logger.error("background files failed: %s", t.exception()))
    return task


async def ensure_files(storage_dir: str) -> None:
    """Waits until the PDF and PPTX of an order exist (building them now if needed)."""
    if all(os.path.exists(os.path.join(storage_dir, n)) for n in ("presentation.pdf", "presentation.pptx")):
        return
    if not os.path.exists(os.path.join(storage_dir, "content.json")):
        return
    await start_files(storage_dir)


async def rerender_pdf(storage_dir: str, fallback_data: Optional[Dict[str, Any]] = None,
                       theme_key: Any = "05_nature_organic") -> str:
    """Rebuilds the PDF of an order. Uses the saved content.json when present (same text and
    photos as the paid preview); otherwise regenerates content from the order's basic data."""
    path = os.path.join(storage_dir, "content.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        content, theme_key = saved["content"], saved.get("theme", theme_key)
    else:
        content = ai_service.generate_mock_presentation(fallback_data or {})
    res = await render_deck(content, theme_key, storage_dir, want_pptx=False, want_pngs=False, fetch_images=False)
    return res.pdf_path
