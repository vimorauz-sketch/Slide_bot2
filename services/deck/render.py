"""
Deck renderer: content JSON + theme -> HTML -> (Playwright/Chromium) -> PNG, PDF and PPTX.

All three outputs come from the same HTML page, so the preview the user sees in Telegram,
the PDF and the PowerPoint file always match.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import re
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from services.deck import art, charts, icons, packs, stickers
from services.deck.catalog import LAYOUTS, downgrade_to_text_image, is_slide_usable, normalize_slide
from services.deck.fonts import css_family, font_face_css
from services.deck.text import clean_value
from services.deck.themes import THEMES_DIR, get_theme

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_TEMPLATES = _HERE / "templates"

W, H = 1920, 1080
MIN_FIT = 0.74
MAX_FIT = 1.18
NO_GROW = ["cover", "highlight", "closing", "section", "quote"]
MAX_TRIM_ROUNDS = 3

# Layouts that show a picture, and the size of the picture slot (for generated art).
_BLEED = (845, 1080)
_FULL = (1920, 1080)
IMAGE_LAYOUTS = {"cover", "text_image", "icon_list", "quote", "section", "stats", "highlight", "closing"}
_ALWAYS_IMAGE = {"cover", "text_image", "icon_list", "highlight", "closing", "section"}

I18N = {
    "uz": {"author": "Muallif", "institution": "Ta’lim muassasasi", "teacher": "O‘qituvchi", "subject": "Fan",
           "group": "Guruh", "course": "Kurs", "year": "Yil", "grade": "Sinf", "date": "Sana", "thanks": "E’tiboringiz uchun rahmat!", "questions": "Savollaringiz bo‘lsa, marhamat"},
    "ru": {"author": "Автор", "institution": "Учебное заведение", "teacher": "Преподаватель", "subject": "Предмет",
           "group": "Группа", "course": "Курс", "year": "Год", "grade": "Класс", "date": "Дата", "thanks": "Спасибо за внимание!", "questions": "Готов ответить на ваши вопросы"},
    "en": {"author": "Author", "institution": "Institution", "teacher": "Teacher", "subject": "Subject",
           "group": "Group", "course": "Year", "year": "Year", "grade": "Grade", "date": "Date", "thanks": "Thank you!", "questions": "Questions are welcome"},
}


# ------------------------------------------------------------------ jinja
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_ARROW_SVG = ('<span class="arrow"><svg viewBox="0 0 40 16"><path d="M1 8H36M28 2l8 6-8 6" fill="none" stroke="currentColor" '
              'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></span>')
_EQ_SVG = ('<span class="arrow"><svg viewBox="0 0 40 18"><path d="M2 6H36M30 1l6 5M38 12H4M10 17l-6-5" fill="none" stroke="currentColor" '
           'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span>')


def _rich(value: Any) -> Markup:
    """Escapes text and renders unicode sub/superscripts with <sub>/<sup> (bundled fonts lack those glyphs)."""
    s = escape(str(value or ""))
    s = re.sub(r"[₀-₉]+", lambda m: f"<sub>{m.group(0).translate(_SUB)}</sub>", s)
    s = re.sub(r"[⁰-⁹⁺⁻]+", lambda m: f"<sup>{m.group(0).translate(_SUP)}</sup>", s)
    s = s.replace("→", _ARROW_SVG).replace("⇌", _EQ_SVG).replace("⟶", _ARROW_SVG)
    return Markup(s)


def _formula(value: Any) -> Markup:
    """Like _rich, plus chemistry-style subscripts for digits written inline (CO2 -> CO₂)."""
    s = str(value or "")
    s = s.replace("->", "→").replace("=>", "→").replace("<=>", "⇌")
    s = re.sub(r"(?<=[A-Za-z\)\]])(\d+)", lambda m: m.group(1).translate(str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")), s)
    return _rich(s)


def _icon_filter(name: Any, text: str = "") -> Markup:
    return Markup(icons.svg(str(name or ""), text))


def _env() -> Environment:
    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(str(_TEMPLATES)), FileSystemLoader(str(THEMES_DIR))]),
        autoescape=select_autoescape(["html", "j2"], default_for_string=True, default=True),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["rich"] = _rich
    env.filters["formula"] = _formula
    env.filters["icon"] = _icon_filter
    return env


_ENV = _env()
_BASE_CSS = "\n".join((_TEMPLATES / f).read_text(encoding="utf-8") for f in ("base.css", "traits.css", "photo.css"))


# ------------------------------------------------------------------ deck preparation
def _palette(theme: Dict[str, Any]) -> Dict[str, str]:
    p = dict(theme["palette"])
    p.setdefault("extra", p.get("accent"))
    return p


# Content layouts with free space in the top-right corner for a subject sticker.
STICKER_CORNER_LAYOUTS = {"cards", "process", "stats", "chart", "comparison", "timeline", "formula", "table",
                          "summary", "references", "pyramid", "cycle", "agenda", "icon_list"}


def _sticker(theme: Dict[str, Any], subject: str, index: int, size: int) -> str:
    style = theme.get("sticker_style")
    if not style:
        return ""
    offset = int(str(theme.get("code") or 0) or 0) % 5
    return stickers.render(stickers.pick(subject, index, offset), _palette(theme), style, size)


def _art_image(theme: Dict[str, Any], slide: Dict[str, Any], seed: int, size, subject: str = "general") -> Dict[str, Any]:
    v = slide.get("visual") or {}
    hint = " ".join(str(x) for x in [v.get("query", ""), slide.get("title", ""), slide.get("statement", "")])
    icon_name = icons.resolve(v.get("icon") or "", hint)
    badge = slide.get("layout") != "closing" and not (slide.get("layout") == "cover" and slide.get("cover_variant") == "center")
    overlay = _sticker(theme, subject, seed, 300) if badge and theme.get("art_sticker", True) else ""
    return {"src": art.art_data_uri(theme.get("art", "academic"), _palette(theme), icon_name, hint, size[0], size[1], seed, badge, overlay),
            "is_art": True, "credit": ""}


BLEED_COVERS = ("split", "split-left", "band", "circle", "arch", "frame", "diagonal", "poster")


ITEM_PHOTO_LAYOUTS = {"cards": "items", "process": "steps", "icon_list": "items"}
_ITEM = (960, 680)


def _item_art(theme: Dict[str, Any], slide: Dict[str, Any], item: Dict[str, Any], seed: int, subject: str) -> Dict[str, Any]:
    """Fallback picture for a card / step without a photo: the theme's art with the item's icon."""
    hint = " ".join(str(x) for x in (item.get("photo", ""), item.get("title", ""), slide.get("title", "")))
    icon_name = icons.resolve(item.get("icon") or "", hint)
    return {"src": art.art_data_uri(theme.get("art", "academic"), _palette(theme), icon_name, hint, _ITEM[0], _ITEM[1], seed, True),
            "is_art": True, "credit": "", "slot": "item"}


def _slot_size(layout: str, cover_variant: str) -> tuple:
    if layout == "cover" and cover_variant == "bottom":
        return (1920, 540)
    if layout in ("highlight", "closing") or (layout == "cover" and cover_variant not in BLEED_COVERS):
        return _FULL
    return _BLEED


def build_slides(content: Dict[str, Any], theme: Dict[str, Any], images: Optional[Dict[int, Any]] = None) -> List[Dict[str, Any]]:
    """Normalizes content and computes everything the templates need (images, charts, geometry)."""
    images = images or {}
    lang = content.get("language", "uz")
    labels = I18N.get(lang, I18N["uz"])
    ts = content.get("title_slide", {}) or {}
    cover_variant = ts.get("cover_variant") or theme.get("cover_variant", "split")

    cover = {
        "layout": "cover", "cover_variant": cover_variant,
        "title": ts.get("title", ""), "subtitle": ts.get("subtitle", ""),
        "kicker": ts.get("kicker") or ts.get("subject", ""),
        "visual": ts.get("visual") or {"kind": "photo", "query": ts.get("image_query", "") or ts.get("title", "")},
        "notes": ts.get("notes", ""),
    }
    meta = []
    grade = any(w in str(ts.get("course", "")).lower() for w in ("sinf", "класс", "grade"))
    for key, label in (("author", labels["author"]), ("course", labels["grade" if grade else "course"]),
                       ("group", labels["group"]), ("institution", labels["institution"]),
                       ("teacher", labels["teacher"]), ("date", labels["date"])):
        if ts.get(key):
            meta.append({"k": label, "v": ts[key]})
    cover["meta"] = meta

    slides: List[Dict[str, Any]] = [cover]
    for raw in content.get("slides", []):
        s = normalize_slide(raw)
        if not is_slide_usable(s):
            s = downgrade_to_text_image(s)
        slides.append(s)

    subject = stickers.detect_subject(content)
    place = theme.get("sticker_place", "none") if theme.get("sticker_style") else "none"
    photo = bool(theme.get("photo"))
    side_toggle = 0
    for idx, s in enumerate(slides):
        layout = s["layout"]
        # Picture placement alternates so consecutive picture slides don't look identical.
        photo_extra = photo and layout in ("summary", "agenda")
        if (layout in ("text_image", "icon_list", "quote", "section", "stats") or photo_extra) and s.get("variant") not in ("left", "right"):
            s["variant"] = "right" if side_toggle % 2 == 0 else "left"
            side_toggle += 1
        if layout == "cards" and not s.get("variant"):
            s["variant"] = theme.get("cards_variant", "row")

        wants_image = layout in _ALWAYS_IMAGE or photo_extra or (
            layout in IMAGE_LAYOUTS and (s.get("visual") or {}).get("kind", "none") != "none")
        if layout == "stats" and len(s.get("stats", [])) > 3:
            wants_image = False
        if wants_image:
            img = images.get(idx) or raw_image(content, idx)
            if not img:
                img = _art_image(theme, s, idx, _slot_size(layout, cover_variant), subject)
            s["image"] = img
        else:
            s["image"] = None

        s["item_photos"] = False
        item_key = ITEM_PHOTO_LAYOUTS.get(layout)
        if photo and item_key and s.get(item_key):
            raw_slides = content.get("slides") or []
            raw = raw_slides[idx - 1] if 0 < idx <= len(raw_slides) and isinstance(raw_slides[idx - 1], dict) else {}
            raw_items = raw.get(item_key) or []
            for k, it in enumerate(s[item_key]):
                src = raw_items[k] if raw_items and k < len(raw_items) and isinstance(raw_items[k], dict) else {}
                img = src.get("image")
                if not (img and (not str(img.get("src", "")).startswith("file:") or os.path.exists(img["src"][7:]))):
                    img = _item_art(theme, s, it, idx * 7 + k, subject)
                it["image"] = img
            s["item_photos"] = True

        s["pack_svg"] = ""
        if theme.get("pack"):
            kind = "content"
            if layout == "cover":
                cv = s.get("cover_variant", cover_variant)
                kind = "cover-mirror" if cv == "split-left" else ("content" if cv in ("center", "bottom") else "cover")
            s["pack_svg"] = packs.pack_svg(theme["pack"], _palette(theme), kind, seed=idx)
        s["sticker"] = ""
        s["item_stickers"] = []
        if place in ("corner", "both") and layout in STICKER_CORNER_LAYOUTS and not s["image"]:
            s["sticker"] = _sticker(theme, subject, idx + 3, 200)
        if place in ("cards", "both") and layout in ("cards", "icon_list"):
            s["item_stickers"] = [_sticker(theme, subject, idx * 3 + k, 132) for k in range(len(s.get("items", [])))]
            if place == "both":
                s["sticker"] = ""

        if layout == "chart":
            s["chart_svg"] = charts.chart_svg(s["chart"])
        elif layout == "cycle":
            s["cycle_svg"] = charts.cycle_svg(len(s["stages"]))
            s["cycle_geo"] = charts.cycle_geometry(len(s["stages"]))
        elif layout == "pyramid":
            s["pyramid_geo"] = charts.pyramid_geometry(len(s["levels"]))
        elif layout == "closing":
            s["title"] = s.get("title") or labels["thanks"]
            s["subtitle"] = s.get("subtitle") or labels["questions"]
        elif layout == "cover":
            s.setdefault("cover_variant", cover_variant)
    return slides


def raw_image(content: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    """Images resolved on an earlier run are stored back into the content (see images.py)."""
    if idx == 0:
        return (content.get("title_slide") or {}).get("image")
    lst = content.get("slides", [])
    if 0 < idx <= len(lst):
        img = lst[idx - 1].get("image")
        if img and img.get("src", "").startswith("file:") and not os.path.exists(img["src"][7:]):
            return None
        return img
    return None


def render_html(content: Dict[str, Any], theme: Dict[str, Any], slides: List[Dict[str, Any]]) -> str:
    lang = content.get("language", "uz")
    ts = content.get("title_slide", {}) or {}
    deck = {
        "language": lang,
        "footer_text": ts.get("footer") or ts.get("title", ""),
        "author_line": " · ".join(x for x in [ts.get("author", ""), ts.get("institution", "")] if x),
    }
    if len(deck["footer_text"]) > 60:
        deck["footer_text"] = deck["footer_text"][:58].rsplit(" ", 1)[0] + "…"
    fonts = theme["fonts"]
    font_css = font_face_css([fonts["title"], fonts["body"]] + fonts.get("extra", []))
    font_vars = f":root{{--font-title:{css_family(fonts['title'])};--font-body:{css_family(fonts['body'])};}}"
    tpl = _ENV.get_template("deck.html.j2")
    return tpl.render(
        deck=deck, theme=theme, slides=slides,
        theme_decor=f"{theme.get('family', theme['id'])}/decor.j2" if theme.get("has_decor") else "__none__.j2",
        bleed_covers=BLEED_COVERS,
        font_css=font_css, base_css=_BASE_CSS + font_vars, theme_css=theme.get("css", ""),
    )


# ------------------------------------------------------------------ browser
_FIT_JS = r"""
([minFit, maxFit, noGrow]) => {
  const slides = [...document.querySelectorAll('.slide')];
  const overflowing = (sl, spare = 0) => {
    const r = sl.getBoundingClientRect();
    const limitB = r.bottom - (sl.classList.contains('no-foot') ? 30 : 74) - spare;
    for (const el of sl.querySelectorAll('[data-t], .card, .step-card, .stat, .side, .term, .tbl-wrap, .formula-box')) {
      if (el.closest('.s-foot')) continue;
      const b = el.getBoundingClientRect();
      if (b.height === 0) continue;
      if (b.bottom > limitB + 1 || b.right > r.right - 20 + 1 || b.top < r.top + 20) return true;
      if (el.scrollHeight > el.clientHeight + 2 && getComputedStyle(el).overflow !== 'visible') return true;
    }
    return false;
  };
  const result = [];
  slides.forEach((sl, i) => {
    let fit = 1;
    sl.style.setProperty('--fit', fit);
    while (overflowing(sl) && fit > minFit) {
      fit = Math.round((fit - 0.03) * 100) / 100;
      sl.style.setProperty('--fit', fit);
    }
    // Sparse slides grow (up to maxFit) so short content does not float in empty space.
    if (fit === 1 && !noGrow.includes(sl.dataset.layout)) {
      while (fit < maxFit) {
        const next = Math.round((fit + 0.03) * 100) / 100;
        sl.style.setProperty('--fit', next);
        if (overflowing(sl, 70)) { sl.style.setProperty('--fit', fit); break; }
        fit = next;
      }
    }
    result.push({i, fit, overflow: overflowing(sl)});
  });
  return result;
}
"""

_MEASURE_JS = r"""
([titleFamily, fbTitle, fbBody]) => {
  const SUB = '₀₁₂₃₄₅₆₇₈₉', SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';
  // Metric-compatible clones let us measure the PowerPoint fallback fonts exactly.
  const CLONES = {'Arial': 'Liberation Sans', 'Times New Roman': 'Liberation Serif', 'Calibri': 'Carlito', 'Cambria': 'Caladea'};
  const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d');
  const widthOf = (text, font, ls) => { ctx.font = font; return ctx.measureText(text).width + ls * text.length; };
  const out = [];
  document.querySelectorAll('.slide').forEach((sl) => {
    const sr = sl.getBoundingClientRect();
    const items = [];
    sl.querySelectorAll('[data-t]').forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return;
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const lines = []; let cur = ''; let lastTop = null; let node;
      const range = document.createRange();
      const fs = parseFloat(cs.fontSize);
      while ((node = walker.nextNode())) {
        const parentTag = node.parentElement ? node.parentElement.tagName : '';
        const txt = node.textContent;
        for (let k = 0; k < txt.length; k++) {
          let ch = txt[k];
          if (parentTag === 'SUB' && ch >= '0' && ch <= '9') ch = SUB[+ch];
          if (parentTag === 'SUP' && ch >= '0' && ch <= '9') ch = SUP[+ch];
          range.setStart(node, k); range.setEnd(node, k + 1);
          const rects = range.getClientRects();
          if (!rects.length) { if (/\s/.test(ch)) cur += ' '; continue; }
          const top = rects[0].top;
          if (lastTop !== null && top > lastTop + fs * 0.6) { lines.push(cur); cur = ''; }
          if (lastTop === null || top > lastTop + fs * 0.6) lastTop = top;
          cur += ch;
        }
      }
      lines.push(cur);
      let clean = lines.map((l) => l.replace(/\s+/g, ' ').trim()).filter((l) => l.length);
      if (!clean.length) return;
      if (cs.textTransform === 'uppercase') clean = clean.map((l) => l.toUpperCase());
      let color = cs.color;
      const fill = cs.webkitTextFillColor;
      if (fill && fill !== color && !fill.includes('0, 0, 0, 0')) color = fill;
      const bgClip = cs.webkitBackgroundClip || cs.backgroundClip;
      const isTitle = cs.fontFamily.replace(/"/g, '').startsWith(titleFamily);
      const fb = isTitle ? fbTitle : fbBody;
      const weight = parseInt(cs.fontWeight) || 400;
      const style = cs.fontStyle === 'italic' ? 'italic ' : '';
      const ls = parseFloat(cs.letterSpacing) || 0;
      const realFont = `${style}${weight} ${fs}px ${cs.fontFamily}`;
      const fbFont = `${style}${weight >= 600 ? 700 : 400} ${fs}px "${fb}", "${CLONES[fb] || fb}"`;
      let scale = 1;
      for (const ln of clean) {
        const realW = widthOf(ln, realFont, ls);
        const fbW = widthOf(ln, fbFont, ls);
        const allowed = Math.max(r.width, realW) * 1.05;
        if (fbW > allowed) scale = Math.min(scale, allowed / fbW);
      }
      items.push({
        x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height,
        lines: clean, fontSize: fs, fontWeight: weight, italic: cs.fontStyle === 'italic',
        color, gradientText: bgClip === 'text', font: fb, scale,
        align: cs.textAlign, lineHeight: parseFloat(cs.lineHeight) || fs * 1.3, letterSpacing: ls,
      });
    });
    out.push(items);
  });
  return out;
}
"""

_pw_state: Dict[str, Any] = {"pw": None, "browser": None, "loop": None}
_pw_lock: Optional[asyncio.Lock] = None


async def _get_browser():
    global _pw_lock
    loop = asyncio.get_running_loop()
    if _pw_lock is None or _pw_state["loop"] is not loop:
        _pw_lock = asyncio.Lock()
    async with _pw_lock:
        b = _pw_state["browser"]
        if b is not None and _pw_state["loop"] is loop and b.is_connected():
            return b
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        exe = os.environ.get("SLIDELAB_CHROMIUM")
        kwargs = {"args": ["--font-render-hinting=none", "--disable-gpu", "--no-sandbox"]}
        if exe:
            kwargs["executable_path"] = exe
        browser = await pw.chromium.launch(**kwargs)
        _pw_state.update(pw=pw, browser=browser, loop=loop)
        return browser


ART_CACHE = Path(__file__).resolve().parents[2] / "storage" / "art_cache"


async def _rasterize_art(context, slides: List[Dict[str, Any]]) -> None:
    """Generated art is SVG with blur/glow filters, which Chrome's PDF backend redraws very
    slowly. Each piece is rendered once to JPEG (cached by content hash) and used as a file."""
    import hashlib
    ART_CACHE.mkdir(parents=True, exist_ok=True)
    page = None
    try:
        todo = []
        for s in slides:
            todo.append((s.get("image"), _slot_size(s["layout"], s.get("cover_variant", ""))))
            for key in ("items", "steps"):
                for it in s.get(key) or []:
                    if isinstance(it, dict) and it.get("image"):
                        todo.append((it["image"], _ITEM))
        for img, (w, h) in todo:
            if not img or not img.get("is_art") or not str(img.get("src", "")).startswith("data:"):
                continue
            key = hashlib.sha1(img["src"].encode("ascii")).hexdigest()[:24]
            dst = ART_CACHE / f"{key}.jpg"
            if not dst.exists():
                if page is None:
                    page = await context.new_page()
                await page.set_viewport_size({"width": w, "height": h})
                await page.set_content(f'<html><body style="margin:0"><img src="{img["src"]}" '
                                       f'style="display:block;width:{w}px;height:{h}px"></body></html>')
                await page.wait_for_load_state("load")
                await page.screenshot(path=str(dst), type="jpeg", quality=90, clip={"x": 0, "y": 0, "width": w, "height": h})
            img["src"] = dst.as_uri()
    finally:
        if page is not None:
            await page.close()


async def shutdown_browser() -> None:
    b, pw = _pw_state.get("browser"), _pw_state.get("pw")
    _pw_state.update(pw=None, browser=None, loop=None)
    try:
        if b:
            await b.close()
        if pw:
            await pw.stop()
    except Exception:  # pragma: no cover - best effort
        pass


async def _capture_slides(page, out_dir: str, prefix: str, n: int, scale: float, fmt: str = "jpg") -> List[str]:
    """Element screenshots as JPEG: about 3x faster than PNG on effect-heavy themes, and the
    files are what Telegram previews and PPTX backgrounds need anyway."""
    sections = await page.query_selector_all(".slide")
    paths = []
    for i, el in enumerate(sections[:n]):
        p = os.path.join(out_dir, f"{prefix}_{i + 1:02d}.{fmt}")
        if fmt == "png":
            await el.screenshot(path=p, type="png")
        else:
            await el.screenshot(path=p, type="jpeg", quality=92)
        paths.append(p)
    return paths


def _images_to_pdf(paths: List[str], pdf_path: str) -> str:
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims[0].save(pdf_path, "PDF", save_all=True, append_images=ims[1:], resolution=144.0, quality=90)
    return pdf_path


# ------------------------------------------------------------------ trimming
def _shrink_slide(s: Dict[str, Any]) -> Dict[str, Any]:
    """Makes a slide's content smaller when shrinking the font was not enough."""
    s = copy.deepcopy(s)
    layout = s["layout"]
    lists = {k: v for k, v in s.items() if isinstance(v, list) and v and k not in ("meta", "rows", "headers", "labels", "pyramid_geo")}
    spec = LAYOUTS.get(layout, {}).get("fields", {})
    for key, val in sorted(lists.items(), key=lambda kv: -len(kv[1])):
        rule = spec.get(key)
        if isinstance(rule, dict) and len(val) > rule.get("min", 1):
            s[key] = val[:-1]
            return s
    # No list can lose an item: shorten every long text by ~20%.
    def cut(text: str) -> str:
        if not isinstance(text, str) or len(text) < 40:
            return text
        target = int(len(text) * 0.8)
        t = text[:target].rsplit(" ", 1)[0].rstrip(" ,;:")
        return t + "…"
    for k, v in list(s.items()):
        if k in ("title", "lead", "text", "statement", "quote", "caption", "takeaway", "subtitle", "verdict"):
            s[k] = cut(v)
        elif isinstance(v, list):
            s[k] = [({kk: cut(vv) for kk, vv in it.items()} if isinstance(it, dict) else cut(it)) for it in v]
    if layout == "table":
        s["rows"] = s.get("rows", [])[:-1] if len(s.get("rows", [])) > 2 else s.get("rows", [])
    return s


# ------------------------------------------------------------------ public API
@dataclass
class DeckResult:
    html_path: str
    slide_pngs: List[str] = field(default_factory=list)
    pdf_path: Optional[str] = None
    pptx_path: Optional[str] = None
    fit: List[Dict[str, Any]] = field(default_factory=list)
    slides: List[Dict[str, Any]] = field(default_factory=list)


async def render_deck(
    content: Dict[str, Any],
    theme_key_or_spec: Any,
    out_dir: str,
    *,
    want_pdf: bool = True,
    want_pptx: bool = True,
    want_pngs: bool = True,
    images: Optional[Dict[int, Any]] = None,
    png_scale: float = 1.0,
    fetch_images: bool = True,
) -> DeckResult:
    """Renders a whole deck. `images` maps slide index (0 = cover) to resolved images.

    With fetch_images=True, photos are looked up (services/deck/images.py) and stored back
    into `content` in place, so a later re-render reuses exactly the same pictures."""
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    theme = get_theme(theme_key_or_spec)
    if fetch_images and images is None:
        from services.deck.images import resolve_images
        try:
            images = await resolve_images(content, theme)
        except Exception as e:  # never fail a deck because of pictures
            logger.warning("image lookup failed: %s", e)
            images = {}
    lang = content.get("language", "uz")
    content = clean_value(copy.deepcopy(content), lang)
    slides = build_slides(content, theme, images)

    html_path = os.path.join(out_dir, "deck.html")
    browser = await _get_browser()
    context = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=png_scale)
    page = await context.new_page()
    import time
    t0 = time.perf_counter()
    timings: Dict[str, float] = {}

    def mark(name: str) -> None:
        timings[name] = round(time.perf_counter() - t0, 2)

    try:
        await _rasterize_art(context, slides)
        mark("art")
        fit: List[Dict[str, Any]] = []
        for _round in range(MAX_TRIM_ROUNDS + 1):
            html = render_html(content, theme, slides)
            Path(html_path).write_text(html, encoding="utf-8")
            await page.goto(Path(html_path).as_uri(), wait_until="load")
            await page.evaluate("document.fonts.ready.then(() => true)")
            mark(f"load{_round}")
            fit = await page.evaluate(_FIT_JS, [MIN_FIT, MAX_FIT, NO_GROW])
            mark(f"fit{_round}")
            bad = [f["i"] for f in fit if f["overflow"]]
            if not bad or _round == MAX_TRIM_ROUNDS:
                if bad:
                    logger.warning("Slides still overflow after trimming: %s", bad)
                break
            for i in bad:
                slides[i] = _shrink_slide(slides[i])

        result = DeckResult(html_path=html_path, fit=fit, slides=slides)
        n_slides = len(slides)

        if want_pngs:
            result.slide_pngs = await _capture_slides(page, out_dir, "slide", n_slides, png_scale)
            mark("png")

        if want_pdf:
            pdf_path = os.path.join(out_dir, "presentation.pdf")
            if theme.get("pdf_mode") == "raster":
                # Glow/blur-heavy themes: Chrome's vector PDF re-rasterizes every effect and takes
                # many seconds; a PDF built from the slide images is instant and pixel-identical.
                pngs = result.slide_pngs or await _capture_slides(page, out_dir, "slide", n_slides, png_scale)
                _images_to_pdf(pngs, pdf_path)
            else:
                await page.emulate_media(media="screen")
                await page.pdf(path=pdf_path, width=f"{W}px", height=f"{H}px", print_background=True,
                               margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}, prefer_css_page_size=True)
            result.pdf_path = pdf_path
            mark("pdf")

        if want_pptx:
            from services.deck.pptx_export import build_pptx
            from services.deck.fonts import family_name
            pf = theme.get("pptx_fonts", {})
            measured = await page.evaluate(_MEASURE_JS, [family_name(theme["fonts"]["title"]),
                                                         pf.get("title", "Arial"), pf.get("body", "Arial")])
            await page.evaluate("document.body.classList.add('pptx-bg')")
            bgs = await _capture_slides(page, out_dir, "bg", n_slides, png_scale)
            await page.evaluate("document.body.classList.remove('pptx-bg')")
            pptx_path = os.path.join(out_dir, "presentation.pptx")
            build_pptx(pptx_path, bgs, measured, slides, theme)
            result.pptx_path = pptx_path
            mark("pptx")
        logger.info("deck rendered (%s, %d slides): %s", theme.get("id"), n_slides, timings)
        return result
    finally:
        await context.close()
