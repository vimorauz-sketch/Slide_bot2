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
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from services import ai_service
from services.deck import render_deck
from services.preview_service import make_overview_grid, make_watermarked_previews

logger = logging.getLogger(__name__)

Progress = Optional[Callable[[str], Awaitable[None]]]


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
    if tpl == "custom_ai" and data.get("custom_design_spec"):
        return data["custom_design_spec"]
    return tpl


async def build_presentation(data: Dict[str, Any], storage_dir: str, outline: Optional[Dict[str, Any]] = None,
                             progress: Progress = None, preview_count: int = 2) -> BuildResult:
    os.makedirs(storage_dir, exist_ok=True)

    async def say(text: str) -> None:
        if progress:
            try:
                await progress(text)
            except Exception:  # a failed status edit must never stop the build
                pass

    await say("write")
    content = await ai_service.generate_presentation_content(data, outline)
    theme_key = theme_key_from_data(data)
    await say("render")
    res = await render_deck(content, theme_key, storage_dir)

    content_path = os.path.join(storage_dir, "content.json")
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump({"content": content, "theme": theme_key}, f, ensure_ascii=False, indent=1)

    previews = make_watermarked_previews(res.slide_pngs, storage_dir, count=preview_count)
    overview = make_overview_grid(res.slide_pngs, os.path.join(storage_dir, "overview_wm.jpg"), watermark=True)
    return BuildResult(storage_dir=storage_dir, content_path=content_path, pptx_path=res.pptx_path, pdf_path=res.pdf_path,
                       slide_pngs=res.slide_pngs, previews=previews, overview=overview, content=content)


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
