"""
AI content pipeline (OpenAI).

1. generate_outline()  -> deck title + one line per slide (title, key point, layout). The bot
                          shows this plan to the user for approval before anything is drawn.
2. generate_presentation_content() -> every slide written in parallel, each against the JSON
                          shape of its own layout (services/deck/catalog.py), plus a picture
                          query, an icon and speaker notes.
3. The renderer (services/deck) then lays it out, fits text, finds photos and exports.

Without an API key (or when the API fails) a deterministic mock generator is used, so the bot
always produces a usable deck.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import logging
import math
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from config import settings
from services.deck import icons as deck_icons
from services.deck.catalog import CONTENT_LAYOUTS, LAYOUTS, catalog_for_prompt, resolve_layout_name

logger = logging.getLogger(__name__)


def get_openai_client() -> Optional[AsyncOpenAI]:
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
        return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return None


def _model() -> str:
    return getattr(settings, "OPENAI_MODEL", "gpt-4o")


LANG_RULES = {
    "uz": ("Uzbek (Latin script). Use the letters o‘ and g‘ (with the ‘ sign) and ’ for the tutuq belgisi "
           "(ma’ruza, sun’iy). Clear literary Uzbek, academic but easy to read. Never mix in Cyrillic."),
    "ru": "Russian. Grammatically correct academic Russian, clear and concise.",
    "en": "English. Clear, professional academic English.",
}

# Layouts that carry a big picture (used to keep decks visual).
PICTURE_LAYOUTS = {"text_image", "icon_list", "highlight", "section", "quote"}
# Free-choice layouts for the body of the deck.
BODY_LAYOUTS = ["text_image", "cards", "icon_list", "process", "timeline", "cycle", "stats", "chart",
                "comparison", "pyramid", "quote", "formula", "highlight", "table", "section"]
_REF_WORDS = re.compile(r"adabiyot|manba|литератур|источник|reference|sources|bibliograph", re.I)


# ======================================================================= structure
def plan_structure(slide_count: int, notes: str = "") -> Dict[str, Any]:
    """Which fixed slides the deck gets, given its size (slide_count includes the cover)."""
    n = max(3, int(slide_count))
    content = n - 1
    s = {
        "agenda": n >= 7,
        "closing": n >= 8,
        "references": n >= 12 or bool(_REF_WORDS.search(notes or "")),
        "summary": True,
    }
    fixed = sum(1 for k in ("agenda", "closing", "references", "summary") if s[k])
    while fixed > content - 1 and fixed > 1:  # tiny decks: drop extras, keep at least one body slide
        for k in ("closing", "references", "agenda"):
            if s[k]:
                s[k] = False
                fixed -= 1
                break
    s["body"] = max(0, content - fixed)
    return s


def enforce_outline(slides: List[Dict[str, Any]], slide_count: int, notes: str = "") -> List[Dict[str, Any]]:
    """Makes any model-proposed outline structurally sound: exact length, fixed slides in place,
    no repeated neighbouring layouts, enough picture slides, rare layouts kept rare."""
    st = plan_structure(slide_count, notes)
    special = {"agenda", "summary", "references", "closing", "cover"}
    body = []
    for s in slides:
        lay = resolve_layout_name(s.get("layout"))
        if lay in special:
            continue
        body.append({**s, "layout": lay})
    target = st["body"]
    body = body[:target]
    filler = ["text_image", "cards", "icon_list", "process", "comparison", "text_image"]
    i = 0
    while len(body) < target:
        body.append({"title": "", "key_point": "", "layout": filler[i % len(filler)]})
        i += 1

    # Rare layouts.
    limits = {"quote": 1, "highlight": max(1, slide_count // 8), "section": slide_count // 10,
              "formula": 2, "table": 2, "chart": 2, "pyramid": 1, "cycle": 2, "timeline": 2}
    counts: Dict[str, int] = {}
    for s in body:
        lay = s["layout"]
        counts[lay] = counts.get(lay, 0) + 1
        if lay in limits and counts[lay] > limits[lay]:
            s["layout"] = "text_image"
    # At least ~35% of body slides carry a picture: plain-text layouts become text + picture.
    need = math.ceil(len(body) * 0.35)
    have = sum(1 for s in body if s["layout"] in PICTURE_LAYOUTS)
    for s in body:
        if have >= need:
            break
        if s["layout"] in ("process", "cards") and have < need:
            s["layout"] = "text_image" if s["layout"] == "process" else "icon_list"
            have += 1
    # No identical neighbours.
    alternatives = ["text_image", "cards", "icon_list", "process", "comparison"]
    for k in range(1, len(body)):
        if body[k]["layout"] == body[k - 1]["layout"]:
            nxt = body[k + 1]["layout"] if k + 1 < len(body) else None
            body[k]["layout"] = next(a for a in alternatives if a not in (body[k - 1]["layout"], nxt))

    out: List[Dict[str, Any]] = []
    if st["agenda"]:
        out.append({"layout": "agenda", "title": "", "key_point": ""})
    out.extend(body)
    out.append({"layout": "summary", "title": "", "key_point": ""})
    if st["references"]:
        out.append({"layout": "references", "title": "", "key_point": ""})
    if st["closing"]:
        out.append({"layout": "closing", "title": "", "key_point": ""})
    # Carry titles of fixed slides from the model's outline when it wrote them.
    model_fixed = {resolve_layout_name(s.get("layout")): s for s in slides if resolve_layout_name(s.get("layout")) in special}
    for s in out:
        src = model_fixed.get(s["layout"])
        if src and not s.get("title"):
            s["title"] = src.get("title", "")
            s["key_point"] = src.get("key_point", "")
    return out


# ======================================================================= prompts
def _shape(layout: str) -> Dict[str, Any]:
    """Example JSON for one layout, with the character budgets spelled out."""
    spec = LAYOUTS[layout]["fields"]

    def field(rule):
        if isinstance(rule, int):
            return f"string, max {rule} chars"
        if "min" in rule:
            item = {k: f"string, max {v} chars" for k, v in rule["fields"].items()} if "fields" in rule else f"string, max {rule.get('len', 150)} chars"
            return [item, f"... {rule['min']}-{rule['max']} items"]
        return {k: field(v) for k, v in rule.items()}

    shape: Dict[str, Any] = {k: field(v) for k, v in spec.items()}
    if layout == "chart":
        shape["chart"] = {"type": "column | bar | line | donut | pie", "labels": ["3-8 short labels"],
                          "series": [{"name": "series name", "values": ["numbers, same count as labels"]}],
                          "unit": "unit, e.g. % or mln t"}
    if layout == "table":
        shape["headers"] = ["2-4 column headers"]
        shape["rows"] = [["cell", "cell"], "... 2-6 rows"]
    if layout == "formula":
        shape["formula"] = "the formula as plain text, e.g. 6CO2 + 6H2O → C6H12O6 + 6O2 (digits after letters become subscripts)"
    for k in list(shape):
        if k.endswith("items") or k in ("items",):
            pass
    shape["section"] = "optional short label shown above the title (part of the talk), max 30 chars"
    shape["visual"] = {"kind": "photo | illustration | none",
                       "query": "2-5 English words for a stock photo search (concrete, visual)",
                       "prompt": "one English sentence describing an ideal illustration, no text in image",
                       "icon": "one icon name from the icon list"}
    shape["notes"] = "speaker notes: 2-4 sentences the presenter can say, in the deck language"
    return shape


def _audience(data: Dict[str, Any]) -> str:
    level = data.get("level") or ""
    course = data.get("course") or ""
    return " ".join(x for x in [level, course] if x) or "students"


OUTLINE_SYSTEM = """You are a senior presentation author who plans clear, well-structured academic presentations.
Plan the deck as a story: each slide makes ONE point, slides follow a logical order, nothing important
from the topic is missing, and nothing repeats. Choose for every slide the layout that best shows its
content (the shape of the content decides the layout: steps -> process, a loop -> cycle, dates ->
timeline, two things -> comparison, numbers -> stats or chart, parts/types -> cards, one concept with a
picture -> text_image, a formula -> formula).

Available layouts:
{catalog}

Rules:
- Return exactly {body} body slides (the agenda, summary, references and closing slides are added by the system).
- Never use the same layout on two consecutive slides. Prefer variety; at least a third of the slides should carry a picture
  (text_image, icon_list, highlight).
- Use 'stats' and 'chart' ONLY with real, well-known figures you are confident about. Never invent numbers.
- Use 'quote' ONLY for a real quotation you can attribute precisely; otherwise do not use it.
- Use 'formula' only when the topic really has a formula or equation.
- Titles are short and specific (max 70 characters), not generic ("Introduction", "Main part").
- Language of all text: {lang}

Return JSON:
{{"title": "deck title", "subtitle": "one-line subtitle", "slides": [{{"title": "...", "key_point": "the one idea this slide proves, one sentence", "layout": "layout name", "section": "optional short part label"}}]}}"""


SLIDE_SYSTEM = """You write the content of ONE slide of an academic presentation, as JSON.
Deck topic: {topic}
Subject: {subject}
Audience: {audience}
Language: {lang}
Writing style: {tone}
{notes_line}
The whole deck (for context; do not repeat other slides):
{outline}

Write slide {num} of {total}. Layout: '{layout}'. Planned title: "{title}". Key point: "{key_point}".

Rules:
- Facts must be accurate and specific to the topic; prefer concrete terms, names, dates and real figures.
  Never invent statistics, quotations or sources. If unsure of a number, describe it qualitatively.
- Respect every character limit: short, presentation-style phrases, not long paragraphs.
- Do not start bullet points with numbers or symbols; the design adds markers.
- 'visual.query' is in English and names something photographable (e.g. "green leaf macro", "Registan Samarkand").
  Use kind "illustration" for diagrams/microscopic/abstract scientific pictures, "none" when no picture fits.
- 'photo' (in cards / steps / list items) is a 2-5 word English stock-photo query that shows exactly that item
  (e.g. "teacher using tablet classroom", "coral reef underwater"): concrete, photographable, no abstract words.
- 'icon' values must come from this list: {icons}
- Return ONLY JSON with exactly this shape:
{shape}"""


async def _chat_json(client: AsyncOpenAI, system: str, user: str) -> Dict[str, Any]:
    resp = await client.chat.completions.create(
        model=_model(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


# ======================================================================= outline
def _clean_outline_slides(raw: Any) -> List[Dict[str, Any]]:
    out = []
    for s in raw if isinstance(raw, list) else []:
        if isinstance(s, dict):
            out.append({"title": str(s.get("title", ""))[:90], "key_point": str(s.get("key_point", ""))[:240],
                        "layout": resolve_layout_name(s.get("layout")), "section": str(s.get("section", ""))[:40]})
    return out


async def generate_outline(data: Dict[str, Any], feedback: str = "", previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Returns {"title", "subtitle", "slides": [...]} where slides include the fixed ones."""
    slide_count = int(data.get("slide_count", 10))
    notes = data.get("additional_notes", "") or ""
    st = plan_structure(slide_count, notes)
    client = get_openai_client()
    if not client:
        return generate_mock_outline(data)
    lang = data.get("language", "uz")
    system = OUTLINE_SYSTEM.format(catalog=catalog_for_prompt(), body=st["body"], lang=LANG_RULES.get(lang, LANG_RULES["uz"]))
    user = (f"Topic: {data.get('topic', '')}\nSubject: {data.get('subject', '')}\nAudience: {_audience(data)}\n"
            f"Total slides including title slide: {slide_count}\nUser requirements: {notes or '-'}")
    if previous and feedback:
        user += ("\n\nThe user reviewed this previous plan:\n" + outline_to_text(previous, lang) +
                 f"\nTheir requested changes: {feedback}\nApply the changes and return the full new plan.")
    elif previous:
        user += "\n\nThe user asked for a different plan than this one; propose a clearly different structure:\n" + outline_to_text(previous, lang)
    try:
        raw = await _chat_json(client, system, user)
    except Exception as e:
        logger.error("Outline generation failed: %s", e)
        return generate_mock_outline(data)
    slides = enforce_outline(_clean_outline_slides(raw.get("slides")), slide_count, notes)
    return {"title": str(raw.get("title") or data.get("topic", ""))[:110],
            "subtitle": str(raw.get("subtitle", ""))[:160], "slides": slides, "source": "ai"}


_LAYOUT_LABELS = {
    "uz": {"agenda": "Reja", "summary": "Xulosa", "references": "Foydalanilgan adabiyotlar", "closing": "Yakuniy slayd"},
    "ru": {"agenda": "План", "summary": "Выводы", "references": "Литература", "closing": "Заключительный слайд"},
    "en": {"agenda": "Agenda", "summary": "Summary", "references": "References", "closing": "Closing slide"},
}


def outline_to_text(outline: Dict[str, Any], lang: str = "uz") -> str:
    labels = _LAYOUT_LABELS.get(lang, _LAYOUT_LABELS["uz"])
    lines = [f"1. {outline.get('title', '')}"]
    for i, s in enumerate(outline.get("slides", []), start=2):
        title = s.get("title") or labels.get(s["layout"], s["layout"])
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


# ======================================================================= slides
async def _write_slide(client, data, outline, idx, sem, theme) -> Dict[str, Any]:
    plan = outline["slides"][idx]
    layout = plan["layout"]
    lang = data.get("language", "uz")
    labels = _LAYOUT_LABELS.get(lang, _LAYOUT_LABELS["uz"])
    title = plan.get("title") or labels.get(layout, "")
    if layout == "closing":
        return {"layout": "closing", "title": "", "subtitle": "",
                "visual": {"kind": "photo", "query": f"{data.get('topic', '')} inspiring landscape"}}
    notes_line = f"User requirements: {data.get('additional_notes')}" if data.get("additional_notes") else ""
    system = SLIDE_SYSTEM.format(
        topic=data.get("topic", ""), subject=data.get("subject", ""), audience=_audience(data),
        lang=LANG_RULES.get(lang, LANG_RULES["uz"]), tone=theme.get("writing_tone", "Clear and engaging."),
        notes_line=notes_line, outline=outline_to_text(outline, lang), num=idx + 2, total=len(outline["slides"]) + 1,
        layout=layout, title=title, key_point=plan.get("key_point", ""),
        icons=", ".join(deck_icons.curated_names()), shape=json.dumps(_shape(layout), ensure_ascii=False, indent=1),
    )
    user = "Write this slide now."
    if layout == "agenda":
        user = "List the main sections of the deck (use the titles above, grouped into 3-6 items)."
    elif layout == "references":
        user = ("List real, verifiable sources on this topic (textbooks, encyclopedias, well-known papers) "
                "in a standard citation format. Prefer sources available to students in Uzbekistan when relevant.")
    async with sem:
        try:
            out = await _chat_json(client, system, user)
        except Exception as e:
            logger.warning("Slide %s generation failed: %s", idx + 2, e)
            out = {}
    if not isinstance(out, dict):
        out = {}
    out["layout"] = layout
    out.setdefault("title", title)
    if plan.get("section") and not out.get("section"):
        out["section"] = plan["section"]
    if not any(out.get(k) for k in ("lead", "bullets", "items", "steps", "points", "stages", "events", "stats",
                                     "levels", "statement", "quote", "formula", "rows", "chart", "sources", "left")):
        # The call failed: keep the slide meaningful with what the outline already says.
        out = {"layout": "text_image", "title": title, "lead": plan.get("key_point", ""),
               "visual": {"kind": "photo", "query": f"{data.get('topic', '')} {title}"}}
    return out


async def generate_presentation_content(data: Dict[str, Any], outline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full deck content in the renderer's format. Pass the approved `outline` when there is one."""
    client = get_openai_client()
    if not client:
        logger.warning("OpenAI API key not configured. Using the built-in content generator.")
        return generate_mock_presentation(data, outline)
    if outline is None:
        outline = await generate_outline(data)
    from services.deck.themes import get_theme
    theme = get_theme(data.get("custom_design_spec") or data.get("template_id", "05_nature_organic"))
    sem = asyncio.Semaphore(6)
    try:
        cover_task = _chat_json(client, (
            "Return JSON {\"subtitle\": \"one-line subtitle, max 120 chars\", \"visual\": {\"kind\": \"photo\", "
            "\"query\": \"2-5 English words for a striking cover photo\", \"icon\": \"icon name\"}} for a presentation. "
            f"Language of the subtitle: {LANG_RULES.get(data.get('language', 'uz'))}. Icons: {', '.join(deck_icons.curated_names()[:60])}"),
            f"Title: {outline.get('title')}\nTopic: {data.get('topic')}\nSubject: {data.get('subject')}")
        results = await asyncio.gather(
            cover_task, *(_write_slide(client, data, outline, i, sem, theme) for i in range(len(outline["slides"]))),
            return_exceptions=True)
    except Exception as e:  # pragma: no cover - gather with return_exceptions should not raise
        logger.error("Content generation failed: %s", e)
        return generate_mock_presentation(data, outline)
    cover = results[0] if isinstance(results[0], dict) else {}
    slides = [r if isinstance(r, dict) else {"layout": "text_image", "title": outline["slides"][i].get("title", ""),
                                             "lead": outline["slides"][i].get("key_point", "")}
              for i, r in enumerate(results[1:])]
    return _assemble(data, outline, slides, cover.get("subtitle") or outline.get("subtitle", ""), cover.get("visual"), "ai")


def _assemble(data, outline, slides, subtitle, cover_visual, source) -> Dict[str, Any]:
    return {
        "language": data.get("language", "uz"),
        "title_slide": {
            "title": outline.get("title") or data.get("topic", ""),
            "subtitle": subtitle,
            "subject": data.get("subject", ""),
            "author": data.get("author_name", ""),
            "institution": data.get("institution", ""),
            "teacher": data.get("teacher_name", ""),
            "course": data.get("course", ""),
            "visual": cover_visual or {"kind": "photo", "query": data.get("topic", "")},
        },
        "slides": slides,
        "outline": outline,
        "meta": {"source": source, "template_id": data.get("template_id")},
    }


# ======================================================================= OCR
async def parse_task_image(image_bytes: bytes) -> Dict[str, Any]:
    """Reads a photo of a homework task and extracts the presentation parameters."""
    client = get_openai_client()
    if not client:
        logger.warning("OpenAI API key not configured. Returning fallback OCR data.")
        return {
            "ok": False,
            "subject": "Biologiya",
            "topic": "Fotosintez jarayoni va uning ahamiyati",
            "slide_count": 10,
            "language": "uz",
            "requirements": "Slaydlarda tushunarli rasmlar va asosiy xulosalar bo‘lsin.",
            "missing_fields": ["author_name", "institution"]
        }

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    system_prompt = (
        "You are an expert OCR and Vision AI assistant. Analyze the image containing a homework task or presentation requirement. "
        "Extract the presentation parameters and return ONLY a valid JSON object with the following fields:\n"
        "{\n"
        '  "subject": "string or null",\n'
        '  "topic": "string or null",\n'
        '  "slide_count": integer or null,\n'
        '  "language": "uz" or "ru" or "en",\n'
        '  "requirements": "string summary of instructions",\n'
        '  "missing_fields": ["list of parameters missing from image, e.g., author_name, institution, slide_count"]\n'
        "}"
    )
    try:
        response = await client.chat.completions.create(
            model=getattr(settings, "OPENAI_VISION_MODEL", _model()),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this presentation task photo and extract structured parameters in JSON:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ]},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Error parsing task image with OpenAI Vision: {e}")
        return {
            "ok": False,
            "subject": "Topshiriq",
            "topic": "Fotosintez va O‘simliklar dunyosi",
            "slide_count": 10,
            "language": "uz",
            "requirements": "Rasmlar va qisqa matnlar",
            "missing_fields": ["author_name", "institution"]
        }


# ======================================================================= custom design
async def generate_custom_design_spec(prompt: str) -> Dict[str, Any]:
    """Parses a free-text design wish into colours (the renderer builds a theme from them)."""
    client = get_openai_client()
    fallback = {
        "name": "Custom AI Design", "primary_color": "#1A365D", "accent_color": "#2B6CB0",
        "background_color": "#F7FAFC", "card_color": "#FFFFFF", "text_color": "#2D3748",
        "font_title": "Arial", "font_body": "Calibri",
    }
    if not client:
        return fallback
    system_prompt = (
        "You are an expert graphic designer. Convert user design prompt into slide design spec JSON:\n"
        "{\n"
        '  "name": "Custom Design",\n'
        '  "primary_color": "HEX color string",\n'
        '  "accent_color": "HEX color string",\n'
        '  "background_color": "HEX color string",\n'
        '  "card_color": "HEX color string",\n'
        '  "text_color": "HEX color string",\n'
        '  "font_title": "Font name",\n'
        '  "font_body": "Font name"\n'
        "}\nMake sure text_color has strong contrast against background_color."
    )
    try:
        return await _chat_json(client, system_prompt, prompt)
    except Exception as e:
        logger.error(f"Error generating design spec: {e}")
        return {**fallback, "primary_color": "#0F172A", "accent_color": "#2563EB", "background_color": "#F8FAFC",
                "text_color": "#1E293B"}


# ======================================================================= mock generator
def generate_mock_outline(data: Dict[str, Any]) -> Dict[str, Any]:
    topic = data.get("topic") or "Tadqiqot va tahlil"
    slide_count = max(5, int(data.get("slide_count", 10) or 10))
    notes = data.get("additional_notes", "") or ""
    st = plan_structure(slide_count, notes)
    body_cycle = [
        ("text_image", f"{topic}: asosiy tushuncha", "Mavzuning ta’rifi va mohiyati"),
        ("cards", "Asosiy tarkibiy qismlar", "Mavzuni tashkil etuvchi uch-to‘rt asosiy jihat"),
        ("process", "Jarayon bosqichlari", "Hodisa qanday ketma-ketlikda sodir bo‘ladi"),
        ("icon_list", "Ta’sir etuvchi omillar", "Natijaga nimalar ta’sir qiladi"),
        ("comparison", "Afzallik va cheklovlar", "Ikki tomonni solishtirish"),
        ("text_image", "Amaliy ahamiyati", "Kundalik hayot va fan uchun foydasi"),
        ("cards", "Zamonaviy yo‘nalishlar", "Hozirgi tadqiqotlar va istiqbollar"),
        ("highlight", "Muhim fikr", "Eng esda qolarli g‘oya"),
    ]
    body = []
    for i in range(st["body"]):
        lay, title, kp = body_cycle[i % len(body_cycle)]
        body.append({"layout": lay, "title": title, "key_point": kp})
    slides = enforce_outline(body, slide_count, notes)
    return {"title": topic, "subtitle": f"{data.get('subject') or 'Fan'} fani bo‘yicha taqdimot", "slides": slides,
            "source": "mock"}


def _mock_slide(layout: str, title: str, topic: str, subject: str, outline_titles: List[str]) -> Dict[str, Any]:
    t = topic
    if layout == "agenda":
        items = [x for x in outline_titles if x][:6] or ["Kirish", "Asosiy qism", "Xulosa"]
        return {"layout": "agenda", "title": "Reja", "items": [{"title": x, "text": ""} for x in items[:6]]}
    if layout == "text_image":
        return {"layout": "text_image", "title": title,
                "lead": f"{t} — {subject} fanining muhim mavzularidan biri bo‘lib, uni tushunish amaliy masalalarni hal qilishga yordam beradi.",
                "bullets": [f"{t}ning asosiy ta’rifi va mohiyati", "Tarixiy rivojlanishi va asosiy olimlar", "Bugungi kundagi qo‘llanilishi"],
                "visual": {"kind": "photo", "query": f"{t} {subject}", "icon": "lightbulb"}}
    if layout == "cards":
        return {"layout": "cards", "title": title, "items": [
            {"icon": "book-open", "title": "Nazariy asos", "text": f"{t}ga oid asosiy tushuncha va qonuniyatlar."},
            {"icon": "layers", "title": "Tuzilishi", "text": "Mavzuni tashkil etuvchi qismlar va ularning o‘zaro bog‘liqligi."},
            {"icon": "target", "title": "Amaliyot", "text": "Bilimlarni real vaziyatlarda qo‘llash usullari."}]}
    if layout == "process":
        return {"layout": "process", "title": title, "steps": [
            {"title": "Kuzatish", "text": "Hodisani o‘rganish va ma’lumot to‘plash."},
            {"title": "Tahlil", "text": "Sabab va natijalarni aniqlash."},
            {"title": "Xulosa", "text": "Natijalarni umumlashtirish va qo‘llash."}]}
    if layout == "icon_list":
        return {"layout": "icon_list", "title": title, "items": [
            {"icon": "sun", "title": "Tashqi muhit", "text": "Atrof-muhit sharoitlarining ta’siri."},
            {"icon": "users", "title": "Inson omili", "text": "Bilim, tajriba va qarorlar."},
            {"icon": "clock", "title": "Vaqt", "text": "Jarayonning davomiyligi va izchilligi."}],
                "visual": {"kind": "photo", "query": f"{t}", "icon": "settings"}}
    if layout == "comparison":
        return {"layout": "comparison", "title": title,
                "left": {"title": "Afzalliklari", "points": ["Tushunarli va tizimli", "Amaliy foydasi yuqori", "Keng qo‘llaniladi"]},
                "right": {"title": "Cheklovlari", "points": ["Chuqur bilim talab etadi", "Shart-sharoitga bog‘liq", "Doimiy yangilanib turadi"]},
                "verdict": f"{t}ni o‘rganishda ikkala tomonni ham hisobga olish kerak."}
    if layout == "highlight":
        return {"layout": "highlight", "eyebrow": "Muhim fikr", "statement": f"{t} — bilim va amaliyotni bog‘laydigan ko‘prik",
                "text": "Mavzuni chuqur tushunish yangi g‘oyalar va yechimlar uchun asos bo‘ladi.",
                "visual": {"kind": "photo", "query": f"{t} inspiration", "icon": "sparkles"}}
    if layout == "summary":
        return {"layout": "summary", "title": "Xulosa", "points": [
            f"{t} {subject} fanining muhim yo‘nalishidir", "Asosiy tushuncha va bosqichlar ko‘rib chiqildi",
            "Mavzu amaliy hayot bilan chambarchas bog‘liq"], "takeaway": f"{t}ni bilish — kelajakdagi muvaffaqiyat poydevori."}
    if layout == "references":
        return {"layout": "references", "title": "Foydalanilgan adabiyotlar", "sources": [
            f"{subject} fanidan darslik. — Toshkent.", "O‘zbekiston Milliy Ensiklopediyasi. — Toshkent."]}
    if layout == "closing":
        return {"layout": "closing", "visual": {"kind": "photo", "query": f"{t} landscape"}}
    return {"layout": "text_image", "title": title, "lead": f"{t} haqida asosiy ma’lumotlar.",
            "visual": {"kind": "photo", "query": t}}


def generate_mock_presentation(data: Dict[str, Any], outline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = dict(data or {})
    data.setdefault("slide_count", 10)
    data["slide_count"] = max(5, int(data.get("slide_count") or 10))
    data.setdefault("author_name", "Muallif")
    data.setdefault("institution", "O‘quv muassasasi")
    if not data.get("author_name"):
        data["author_name"] = "Muallif"
    if not data.get("institution"):
        data["institution"] = "O‘quv muassasasi"
    outline = copy.deepcopy(outline) if outline else generate_mock_outline(data)
    topic = data.get("topic") or "Tadqiqot va tahlil"
    subject = data.get("subject") or "Fan"
    titles = [s.get("title", "") for s in outline["slides"] if s["layout"] not in ("agenda", "summary", "references", "closing")]
    slides = [_mock_slide(s["layout"], s.get("title") or "", topic, subject, titles) for s in outline["slides"]]
    return _assemble(data, outline, slides, outline.get("subtitle", ""), {"kind": "photo", "query": topic}, "mock")


__all__ = [
    "get_openai_client", "plan_structure", "enforce_outline", "generate_outline", "outline_to_text",
    "generate_presentation_content", "parse_task_image", "generate_custom_design_spec",
    "generate_mock_outline", "generate_mock_presentation", "CONTENT_LAYOUTS", "BODY_LAYOUTS",
]
