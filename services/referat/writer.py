"""
Writes a referat with AI: a plan first (chapters, sections, where pictures and tables go), then
every part in parallel. Without an OpenAI key a readable placeholder text is produced (tests,
local runs).

The result is the document used by services/referat/render.py:
  {"language", "meta": {...title page...}, "sections": [...], "references": [...], "cover_image": {...}}
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from services import ai_service

logger = logging.getLogger(__name__)

# pages -> (chapters, sections per chapter, paragraphs per section, intro/conclusion paragraphs)
SIZES = {
    "short": {"label": "5–7 bet", "pages": 6, "chapters": 2, "subs": 2, "paras": 2, "frame": 2},
    "medium": {"label": "8–10 bet", "pages": 9, "chapters": 2, "subs": 3, "paras": 3, "frame": 3},
    "long": {"label": "12–15 bet", "pages": 13, "chapters": 3, "subs": 3, "paras": 3, "frame": 3},
    "xl": {"label": "18–20 bet", "pages": 19, "chapters": 3, "subs": 4, "paras": 4, "frame": 4},
}
DEFAULT_SIZE = "medium"

MINISTRY = {
    "uz": {"school": "O‘ZBEKISTON RESPUBLIKASI MAKTABGACHA VA MAKTAB TA’LIMI VAZIRLIGI",
           "higher": "O‘ZBEKISTON RESPUBLIKASI OLIY TA’LIM, FAN VA INNOVATSIYALAR VAZIRLIGI"},
    "ru": {"school": "МИНИСТЕРСТВО ДОШКОЛЬНОГО И ШКОЛЬНОГО ОБРАЗОВАНИЯ РЕСПУБЛИКИ УЗБЕКИСТАН",
           "higher": "МИНИСТЕРСТВО ВЫСШЕГО ОБРАЗОВАНИЯ, НАУКИ И ИННОВАЦИЙ РЕСПУБЛИКИ УЗБЕКИСТАН"},
    "en": {"school": "MINISTRY OF PRESCHOOL AND SCHOOL EDUCATION OF THE REPUBLIC OF UZBEKISTAN",
           "higher": "MINISTRY OF HIGHER EDUCATION, SCIENCE AND INNOVATIONS OF THE REPUBLIC OF UZBEKISTAN"},
}
KIND = {"uz": "REFERAT", "ru": "РЕФЕРАТ", "en": "ESSAY"}
FRAME_TITLES = {"uz": ("Kirish", "Xulosa"), "ru": ("Введение", "Заключение"), "en": ("Introduction", "Conclusion")}
SCHOOL_WORDS = ("maktab", "school", "школ", "sinf", "класс")


def size_of(key: str) -> Dict[str, Any]:
    return SIZES.get(key or DEFAULT_SIZE, SIZES[DEFAULT_SIZE])


def ministry_for(level: str, lang: str) -> str:
    names = MINISTRY.get(lang, MINISTRY["uz"])
    return names["school"] if any(w in (level or "").lower() for w in SCHOOL_WORDS) else names["higher"]


def build_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    lang = data.get("language") or "uz"
    year = str(data.get("year") or "")
    if not year:
        import datetime as _dt
        year = str(_dt.date.today().year)
    group = data.get("group") or data.get("course") or ""
    return {
        "ministry": ministry_for(data.get("level", ""), lang),
        "institution": data.get("institution") or "",
        "faculty": data.get("faculty") or "",
        "kind": KIND.get(lang, "REFERAT"),
        "subject": data.get("subject") or "",
        "topic": data.get("topic") or "",
        "author": data.get("author_name") or "",
        "group": group,
        "group_label": ({"uz": "Sinf", "ru": "Класс", "en": "Class"}.get(lang, "Sinf")
                        if any(w in (data.get("level") or "").lower() for w in SCHOOL_WORDS) else ""),
        "teacher": data.get("teacher_name") or "",
        "city": data.get("city") or ("Toshkent" if lang == "uz" else "Ташкент" if lang == "ru" else "Tashkent"),
        "year": year,
    }


# ---------------------------------------------------------------------- prompts
PLAN_SYSTEM = """You plan an academic essay (referat) for a student in Uzbekistan.
Topic: {topic}
Subject: {subject}
Level of the student: {level}
Language of all titles: {lang}
{notes_line}
Make a plan with exactly {chapters} chapters, each with exactly {subs} sections. Titles are specific to the
topic (max 80 characters), logically ordered, nothing repeats, no generic words like "Main part".
{images_line}
Mark "table": true for at most one section where a small factual comparison table really fits.
Return JSON:
{{"chapters": [{{"title": "...", "sections": [{{"title": "...", "image": "English photo search query or empty",
"image_caption": "short caption in the essay language or empty", "table": false}}]}}],
"cover_image": "English photo search query for the title page"}}"""

PART_SYSTEM = """You write part of an academic essay (referat) for a student in Uzbekistan.
Essay topic: {topic}
Subject: {subject}
Student level: {level}
Language: {lang}
{notes_line}
Plan of the whole essay (for context; do not repeat other parts):
{plan}

Rules:
- Academic but readable style, like a good student essay; full paragraphs of 80-130 words.
- Facts, terms, names and dates must be accurate. Never invent statistics, quotations or sources;
  if unsure of a number describe it qualitatively.
- No markdown, no bullet lists, no headings inside paragraphs.
Return ONLY JSON with exactly this shape:
{shape}"""


def _plan_text(plan: Dict[str, Any]) -> str:
    lines = []
    for i, ch in enumerate(plan.get("chapters") or [], start=1):
        lines.append(f"{i}. {ch.get('title', '')}")
        for j, s in enumerate(ch.get("sections") or [], start=1):
            lines.append(f"   {i}.{j}. {s.get('title', '')}")
    return "\n".join(lines)


def _clean_plan(raw: Any, chapters: int, subs: int, topic: str) -> Dict[str, Any]:
    out = {"chapters": [], "cover_image": ""}
    if isinstance(raw, dict):
        out["cover_image"] = str(raw.get("cover_image") or "")[:80]
        for ch in (raw.get("chapters") or [])[:chapters]:
            if not isinstance(ch, dict) or not ch.get("title"):
                continue
            secs = []
            for s in (ch.get("sections") or [])[:subs]:
                if isinstance(s, dict) and s.get("title"):
                    secs.append({"title": str(s["title"])[:120], "image": str(s.get("image") or "")[:80],
                                 "image_caption": str(s.get("image_caption") or "")[:140], "table": bool(s.get("table"))})
            if secs:
                out["chapters"].append({"title": str(ch["title"])[:120], "sections": secs})
    if not out["chapters"]:
        out = mock_plan(topic, chapters, subs)
    return out


def mock_plan(topic: str, chapters: int, subs: int) -> Dict[str, Any]:
    heads = ["Nazariy asoslari", "Asosiy jihatlari", "Amaliy ahamiyati", "Rivojlanish istiqbollari"]
    subs_t = ["Asosiy tushunchalar", "Tarixiy rivojlanishi", "Xususiyatlari", "Hozirgi holati", "Misollar"]
    return {"cover_image": topic, "chapters": [
        {"title": f"{topic}: {heads[i % len(heads)].lower()}",
         "sections": [{"title": subs_t[(i + j) % len(subs_t)], "image": topic if j == 0 else "",
                       "image_caption": topic if j == 0 else "", "table": False} for j in range(subs)]}
        for i in range(chapters)]}


def _mock_paragraphs(topic: str, title: str, n: int) -> List[str]:
    base = [f"«{title}» masalasi «{topic}» mavzusini o‘rganishda muhim o‘rin tutadi. Ushbu qismda mavzuga oid asosiy "
            "tushunchalar, ularning o‘zaro bog‘liqligi va amaliy ahamiyati ilmiy manbalar asosida yoritiladi.",
            "Tadqiqotchilarning fikricha, bu yo‘nalishdagi bilimlar ta’lim, fan va ishlab chiqarishda keng qo‘llaniladi. "
            "Mavzuni chuqur o‘rganish talabalarga nazariy bilimlarni amaliyot bilan bog‘lash imkonini beradi.",
            "Shuningdek, mazkur masala bo‘yicha olib borilayotgan zamonaviy izlanishlar yangi yondashuvlarni "
            "shakllantirmoqda va ularning natijalari kundalik hayotda tobora ko‘proq namoyon bo‘lmoqda.",
            "Xulosa qilib aytganda, ushbu jihatlarni bilish mavzuni yaxlit tushunish va undan to‘g‘ri foydalanish uchun zarur."]
    return [base[k % len(base)] for k in range(n)]


def mock_document(data: Dict[str, Any], plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    size = size_of(data.get("size"))
    topic = data.get("topic") or "Mavzu"
    lang = data.get("language") or "uz"
    plan = plan or mock_plan(topic, size["chapters"], size["subs"])
    intro_t, concl_t = FRAME_TITLES.get(lang, FRAME_TITLES["uz"])
    sections = [{"kind": "intro", "title": intro_t, "paragraphs": _mock_paragraphs(topic, intro_t, size["frame"])}]
    for ch in plan["chapters"]:
        sections.append({"kind": "chapter", "title": ch["title"], "subsections": [
            {"title": s["title"], "paragraphs": _mock_paragraphs(topic, s["title"], size["paras"]),
             **({"image": {"query": s["image"], "caption": s.get("image_caption") or s["title"]}}
                if data.get("with_images") and s.get("image") else {})}
            for s in ch["sections"]]})
    sections.append({"kind": "conclusion", "title": concl_t, "paragraphs": _mock_paragraphs(topic, concl_t, size["frame"])})
    return {"language": lang, "meta": build_meta(data), "sections": sections,
            "references": [f"{data.get('subject') or 'Fan'} bo‘yicha o‘quv qo‘llanma. — Toshkent, 2022.",
                           "www.ziyonet.uz — Axborot-ta’lim portali."],
            "cover_image": {"query": plan.get("cover_image") or topic} if data.get("with_images") else None,
            "source": "mock"}


# ---------------------------------------------------------------------- AI
async def make_plan(data: Dict[str, Any]) -> Dict[str, Any]:
    size = size_of(data.get("size"))
    client = ai_service.get_openai_client()
    topic = data.get("topic") or ""
    if client is None:
        return mock_plan(topic, size["chapters"], size["subs"])
    lang = data.get("language") or "uz"
    images_line = ("For about one section in each chapter, give an English stock-photo query ('image') of something "
                   "real and photographable that illustrates it, and a caption; leave 'image' empty elsewhere."
                   if data.get("with_images") else "Leave every 'image' and 'image_caption' empty.")
    notes = data.get("additional_notes") or ""
    system = PLAN_SYSTEM.format(topic=topic, subject=data.get("subject") or "", level=data.get("level") or "student",
                                lang=ai_service.LANG_RULES.get(lang, ai_service.LANG_RULES["uz"]),
                                notes_line=f"Student's wishes: {notes}" if notes else "",
                                chapters=size["chapters"], subs=size["subs"], images_line=images_line)
    try:
        raw = await ai_service._chat_json(client, system, "Return the plan as JSON.")
    except Exception:  # noqa: BLE001
        logger.exception("referat plan failed; using a simple plan")
        raw = None
    return _clean_plan(raw, size["chapters"], size["subs"], topic)


async def _write(client, data, plan_text, task: str, shape: str) -> Dict[str, Any]:
    lang = data.get("language") or "uz"
    notes = data.get("additional_notes") or ""
    system = PART_SYSTEM.format(topic=data.get("topic") or "", subject=data.get("subject") or "",
                                level=data.get("level") or "student",
                                lang=ai_service.LANG_RULES.get(lang, ai_service.LANG_RULES["uz"]),
                                notes_line=f"Student's wishes: {notes}" if notes else "", plan=plan_text, shape=shape)
    return await ai_service._chat_json(client, system, task)


def _paras(raw: Any, n: int) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [str(p).strip() for p in raw if str(p).strip()][: max(n, 1) + 1]


async def write_document(data: Dict[str, Any], plan: Optional[Dict[str, Any]] = None, progress=None) -> Dict[str, Any]:
    """The whole referat. progress(done, total) is called as parts are finished."""
    size = size_of(data.get("size"))
    plan = plan or await make_plan(data)
    client = ai_service.get_openai_client()
    if client is None:
        return mock_document(data, plan)
    lang = data.get("language") or "uz"
    topic = data.get("topic") or ""
    intro_t, concl_t = FRAME_TITLES.get(lang, FRAME_TITLES["uz"])
    plan_text = _plan_text(plan)
    sem = asyncio.Semaphore(max(2, int(getattr(ai_service.settings, "AI_PARALLEL_REQUESTS", 6) or 6)))
    total = len(plan["chapters"]) + 2
    done = 0

    async def job(coro):
        nonlocal done
        async with sem:
            try:
                return await coro
            except Exception:  # noqa: BLE001 - one failed part becomes placeholder text, not a failed order
                logger.exception("referat part failed")
                return None
            finally:
                done += 1
                if progress:
                    try:
                        await progress(done, total)
                    except Exception:  # noqa: BLE001
                        pass

    intro_shape = f'{{"paragraphs": ["{size["frame"]} paragraphs: relevance of the topic, aim and tasks of the essay"]}}'
    concl_shape = (f'{{"paragraphs": ["{size["frame"]} paragraphs of conclusions"], '
                   '"references": ["5-7 real, existing books, textbooks or official websites on the topic, '
                   'formatted as in Uzbek academic works: Author. Title. — City: Publisher, Year."]}')
    tasks = [job(_write(client, data, plan_text, f"Write the introduction ('{intro_t}').", intro_shape))]
    for i, ch in enumerate(plan["chapters"], start=1):
        secs = "\n".join(f'{i}.{j}. {s["title"]}' + (" (also give a small factual table)" if s.get("table") else "")
                         for j, s in enumerate(ch["sections"], start=1))
        shape = ('{"sections": [{"paragraphs": ["' + str(size["paras"]) + ' paragraphs"], '
                 '"table": {"caption": "...", "head": ["col1", "col2", "col3"], "rows": [["...", "...", "..."]]} or null}]}'
                 f' (exactly {len(ch["sections"])} sections, in this order)')
        tasks.append(job(_write(client, data, plan_text, f"Write chapter {i} '{ch['title']}' with its sections:\n{secs}",
                                shape)))
    tasks.append(job(_write(client, data, plan_text, f"Write the conclusion ('{concl_t}') and the references.", concl_shape)))
    results = await asyncio.gather(*tasks)

    intro, chapters_raw, concl = results[0], results[1:-1], results[-1]
    sections = [{"kind": "intro", "title": intro_t,
                 "paragraphs": _paras((intro or {}).get("paragraphs"), size["frame"]) or _mock_paragraphs(topic, intro_t, size["frame"])}]
    for ch, raw in zip(plan["chapters"], chapters_raw):
        raw_secs = (raw or {}).get("sections") if isinstance(raw, dict) else None
        subs = []
        for j, s in enumerate(ch["sections"]):
            src = raw_secs[j] if isinstance(raw_secs, list) and j < len(raw_secs) and isinstance(raw_secs[j], dict) else {}
            sub = {"title": s["title"],
                   "paragraphs": _paras(src.get("paragraphs"), size["paras"]) or _mock_paragraphs(topic, s["title"], size["paras"])}
            if data.get("with_images") and s.get("image"):
                sub["image"] = {"query": s["image"], "caption": s.get("image_caption") or s["title"]}
            t = src.get("table")
            if isinstance(t, dict) and isinstance(t.get("rows"), list) and t.get("head"):
                rows = [[str(c)[:120] for c in r][:6] for r in t["rows"] if isinstance(r, list)][:12]
                if rows:
                    sub["table"] = {"caption": str(t.get("caption") or s["title"])[:140],
                                    "head": [str(h)[:60] for h in t["head"]][:6], "rows": rows}
            subs.append(sub)
        sections.append({"kind": "chapter", "title": ch["title"], "subsections": subs})
    sections.append({"kind": "conclusion", "title": concl_t,
                     "paragraphs": _paras((concl or {}).get("paragraphs"), size["frame"]) or _mock_paragraphs(topic, concl_t, size["frame"])})
    refs = [str(r).strip() for r in ((concl or {}).get("references") or []) if str(r).strip()][:10]
    return {"language": lang, "meta": build_meta(data), "sections": sections,
            "references": refs or ["www.ziyonet.uz — Axborot-ta’lim portali."],
            "cover_image": {"query": plan.get("cover_image") or topic} if data.get("with_images") else None,
            "source": "ai"}
