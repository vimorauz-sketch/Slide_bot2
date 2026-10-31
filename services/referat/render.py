"""Referat document → HTML → PDF (Chromium paged media) and page pictures (pypdfium2)."""
from __future__ import annotations

import copy
import logging
import os
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.deck import fonts
from services.deck.text import fix_uzbek
from services.referat import decor, designs

logger = logging.getLogger(__name__)

_ENV = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
                   autoescape=select_autoescape(["html", "j2"]))

LABELS = {
    "uz": {"subject": "Fan", "topic": "Mavzu", "author": "Bajardi", "group": "Guruh", "teacher": "Tekshirdi",
           "plan": "Reja", "references": "Foydalanilgan adabiyotlar", "figure": "rasm", "table": "jadval"},
    "ru": {"subject": "Предмет", "topic": "Тема", "author": "Выполнил(а)", "group": "Группа", "teacher": "Проверил(а)",
           "plan": "Содержание", "references": "Список литературы", "figure": "рисунок", "table": "таблица"},
    "en": {"subject": "Subject", "topic": "Topic", "author": "Prepared by", "group": "Group", "teacher": "Supervisor",
           "plan": "Contents", "references": "References", "figure": "Figure", "table": "Table"},
}
CLASSIC_COVERS = ("frame", "double", "ornament", "emblem", "arch")


def _clean(v: Any, lang: str) -> Any:
    if isinstance(v, str):
        return fix_uzbek(v) if lang == "uz" else v
    if isinstance(v, list):
        return [_clean(x, lang) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x, lang) for k, x in v.items()}
    return v


def view_model(doc: Dict[str, Any], template: Dict[str, Any], images: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Numbers chapters (1, 1.1 …), figures and tables; images maps "s<i>" / "s<i>.<j>" → src."""
    images = images or {}
    lang = doc.get("language", "uz") if doc.get("language") in LABELS else "uz"
    doc = _clean(copy.deepcopy(doc), lang)
    sections: List[Dict[str, Any]] = []
    chapter = fig = tab = 0
    for i, s in enumerate(doc.get("sections") or []):
        numbered = s.get("kind", "chapter") == "chapter"
        if numbered:
            chapter += 1
        sec = {"title": s.get("title", ""), "title_display": s.get("title", ""),
               "number": f"{chapter}." if numbered else "", "paragraphs": s.get("paragraphs") or [], "subsections": []}
        for j, sub in enumerate(s.get("subsections") or []):
            item = {"title": sub.get("title", ""), "number": f"{chapter}.{j + 1}." if numbered else "",
                    "paragraphs": sub.get("paragraphs") or [], "image": None, "table": None}
            src = images.get(f"s{i}.{j}")
            if sub.get("image") and src:
                fig += 1
                item["image"] = {"src": src, "caption": sub["image"].get("caption", ""), "n": fig, "key": f"s{i}.{j}"}
            if sub.get("table") and sub["table"].get("rows"):
                tab += 1
                item["table"] = dict(sub["table"], n=tab)
            sec["subsections"].append(item)
        src = images.get(f"s{i}")
        if s.get("image") and src:
            fig += 1
            sec["image"] = {"src": src, "caption": s["image"].get("caption", ""), "n": fig, "key": f"s{i}"}
        sections.append(sec)
    m = dict(doc.get("meta") or {})
    m.setdefault("kind", "REFERAT")
    return {"lang": lang, "L": LABELS[lang], "m": m, "sections": sections, "references": doc.get("references") or [],
            "template": template}


def resolve_template(template_id: str, style: Optional[Dict[str, Any]] = None, lang: str = "uz") -> Dict[str, Any]:
    """The template with the user's own fonts (and Cyrillic fonts for Russian)."""
    t = designs.get(template_id)
    t["fonts"] = dict(t["fonts"])
    style = style or {}
    for role in ("title", "body"):
        fid = style.get(f"font_{role}")
        if fid and fonts.is_library_font(fid):
            t["fonts"][role] = fid
    if lang == "ru":
        t["fonts"] = {k: fonts.cyrillic_fallback(v) for k, v in t["fonts"].items()}
    return t


def running_title(t: Dict[str, Any], topic: str) -> str:
    if t["cover"] in CLASSIC_COVERS:
        return ""
    running = topic[:70] + ("…" if len(topic) > 70 else "")
    return "".join(ch for ch in running if ch not in '\\"<>{};')


def body_size(t: Dict[str, Any]) -> str:
    cat = (fonts.library_font(t["fonts"]["body"]) or {}).get("category")
    return "13pt" if cat in ("modern", "tech") else "14pt"


def build_html(doc: Dict[str, Any], template_id: str, images: Optional[Dict[str, str]] = None,
               cover_photo: str = "", style: Optional[Dict[str, Any]] = None, background_only: bool = False) -> str:
    lang = doc.get("language", "uz")
    t = resolve_template(template_id, style, lang)
    vm = view_model(doc, t, images)
    html = _ENV.get_template("referat.html.j2").render(
        t=t, p=t["palette"], m=vm["m"], L=vm["L"], lang=vm["lang"], sections=vm["sections"],
        references=vm["references"], decor=decor.cover_svg(t["cover"], t["palette"]), cover_photo=cover_photo,
        font_css=fonts.font_face_css([t["fonts"]["title"], t["fonts"]["body"]]),
        font_title=fonts.css_family(t["fonts"]["title"]), font_body=fonts.css_family(t["fonts"]["body"]),
        body_size=body_size(t), running=running_title(t, vm["m"].get("topic", "")))
    if background_only:  # the title page's decoration alone (the Word file puts its text on top)
        html = html.replace("</style>", ".cv{visibility:hidden} body>section:not(.cover){display:none}</style>", 1)
    return html


async def html_to_png(html: str, png_path: str, scale: float = 2.0) -> str:
    """The first A4 page as a picture (used for the title page background of the Word file)."""
    from pathlib import Path
    from services.deck.render import _get_browser
    browser = await _get_browser()
    context = await browser.new_context(viewport={"width": 794, "height": 1123}, device_scale_factor=scale)
    try:
        page = await context.new_page()
        html_path = os.path.splitext(png_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html.replace("</style>", "@media screen{.cover{width:794px;height:1123px}}</style>", 1))
        await page.goto(Path(html_path).as_uri(), wait_until="load")
        await page.evaluate("document.fonts.ready.then(() => true)")
        await page.screenshot(path=png_path, clip={"x": 0, "y": 0, "width": 794, "height": 1123})
    finally:
        await context.close()
        try:
            os.remove(html_path)
        except (OSError, UnboundLocalError):
            pass
    return png_path


async def html_to_pdf(html: str, pdf_path: str) -> str:
    from services.deck.render import _get_browser
    browser = await _get_browser()
    context = await browser.new_context()
    try:
        page = await context.new_page()
        # loaded from a file: the fonts and pictures are file:// URLs (blocked for about:blank pages)
        html_path = os.path.splitext(pdf_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        from pathlib import Path
        await page.goto(Path(html_path).as_uri(), wait_until="load")
        await page.evaluate("document.fonts.ready.then(() => true)")
        await page.pdf(path=pdf_path, format="A4", print_background=True, prefer_css_page_size=True)
    finally:
        await context.close()
        try:
            os.remove(html_path)
        except (OSError, UnboundLocalError):
            pass
    return pdf_path


def pdf_pages_to_images(pdf_path: str, out_dir: str, pages: List[int], width: int = 900, prefix: str = "page") -> List[str]:
    """Pictures of the given PDF pages (0-based), JPEG."""
    import pypdfium2 as pdfium
    os.makedirs(out_dir, exist_ok=True)
    pdf = pdfium.PdfDocument(pdf_path)
    out = []
    try:
        for i in pages:
            if i >= len(pdf):
                continue
            page = pdf[i]
            scale = width / page.get_width()
            img = page.render(scale=scale).to_pil().convert("RGB")
            path = os.path.join(out_dir, f"{prefix}_{i + 1}.jpg")
            img.save(path, quality=86)
            out.append(path)
    finally:
        pdf.close()
    return out


def page_count(pdf_path: str) -> int:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()
