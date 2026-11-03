"""
Templates made in the dashboard's AI studio.

Slide templates are points of the same design space the 380 generated templates come from
(services/deck/design_space.py): an art style, a cover composition, a mode, a font pair, one option per
trait and a colour seed. Referat templates are a title-page layout, a heading style, a page decoration,
colours and fonts. The AI only *chooses* among these options, so every result renders correctly; without
an OpenAI key the same choices are made from the prompt's keywords (and a seeded shuffle).

Published templates are stored in the database (table custom_templates) and loaded at start; drafts
live in memory until the admin saves or forgets them.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select

from database.connection import AsyncSessionLocal
from database.models import CustomTemplate
from services.deck import design_space as ds
from services.deck import palettes, themes

logger = logging.getLogger(__name__)

SLIDE_START = 401     # codes of published AI slide templates
REFERAT_START = 201   # codes of published AI referat templates
DRAFT_START = 9001

CAT_UZ = {"tech": "Texnologiya", "education": "Ta’lim", "nature": "Tabiat", "business": "Biznes",
          "creative": "Ijod", "culture": "Madaniyat", "minimal": "Minimal"}
SEED_SLUGS = {k: [s[1] for s in v] for k, v in palettes.SEEDS.items()}

# keyword → (preferred arts, preferred modes, colour seeds) for the offline chooser
KEYWORDS = [
    (("kosmos", "koinot", "space", "astronom", "sayyora", "planet", "galak"), ["cosmos"], ["dark", "vivid"], ["violet", "lapis"]),
    (("texno", "tech", "ai", "sun’iy", "sun'iy", "kompyuter", "dastur", "it ", "robot", "kiber"), ["circuit", "glossy3d", "isometric", "blueprint", "lowpoly"], ["dark", "vivid"], ["turquoise", "lapis", "violet"]),
    (("bola", "maktab", "kids", "o‘quvchi", "o'quvchi", "dars", "sinf"), ["doodle", "confetti", "blobs", "chalk"], ["light", "cream"], ["sky", "amber", "peach"]),
    (("tabiat", "eko", "o‘simlik", "o'simlik", "bio", "yashil", "nature", "barg"), ["botanical", "waves", "papercut", "topo"], ["light", "cream"], ["emerald", "olive", "mint"]),
    (("tibbiy", "tibbiyot", "medic", "salomat", "shifo", "yurak", "kasal"), ["medical"], ["light"], ["sky", "turquoise", "emerald"]),
    (("biznes", "business", "iqtisod", "marketing", "startap", "moliya", "korporativ"), ["corporate", "swiss", "stripes", "mesh", "rings"], ["light", "cream"], ["lapis", "graphite", "sky"]),
    (("tarix", "milliy", "o‘zbek", "o'zbek", "sharq", "madaniyat", "an’ana", "naqsh", "atlas"), ["ikat", "editorial", "ink"], ["cream", "vivid"], ["lapis", "pomegranate", "coffee"]),
    (("adabiyot", "she’r", "she'r", "kitob", "jurnal", "san’at", "san'at", "art"), ["editorial", "magazine", "ink"], ["cream", "light"], ["cherry", "ink", "chestnut"]),
    (("ijod", "yorqin", "creative", "pop", "retro", "bayram", "quvnoq"), ["halftone", "retro", "sunburst", "bauhaus", "confetti", "magazine"], ["vivid", "light", "cream"], ["peach", "amber", "pomegranate"]),
    (("minimal", "oddiy", "toza", "qat’iy", "qat'iy", "rasmiy"), ["swiss", "rings", "academic"], ["light"], ["graphite", "lapis"]),
    (("ilm", "akadem", "universitet", "fan", "tadqiqot", "ilmiy"), ["academic", "topo", "editorial"], ["light", "cream"], ["lapis", "sky", "ink"]),
    (("qorong", "dark", "tun", "kecha", "neon"), ["neon", "aurora", "cosmos"], ["dark"], ["violet", "rose", "turquoise"]),
]


# ====================================================================== helpers
def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:28] or "ai"


def _rnd(prompt: str, salt: Any = 0) -> random.Random:
    return random.Random(hashlib.sha1(f"{prompt}|{salt}".encode()).hexdigest())


def font_pairs_for(art: str) -> List[int]:
    moods = ds.ARTS[art]["fonts"]
    return [i for i, f in enumerate(ds.FONT_PAIRS) if f[2] in moods] or list(range(len(ds.FONT_PAIRS)))


# ====================================================================== slide templates
def normalize_slide_choice(raw: Dict[str, Any], rnd: random.Random) -> Dict[str, Any]:
    """Any AI answer → a valid point of the design space (unknown values are replaced)."""
    raw = raw if isinstance(raw, dict) else {}
    art = raw.get("art") if raw.get("art") in ds.ARTS else rnd.choice(list(ds.ARTS))
    info = ds.ARTS[art]
    mode = raw.get("mode") if raw.get("mode") in info["modes"] else rnd.choice(info["modes"])
    cover = raw.get("cover") if raw.get("cover") in ds.COVERS else rnd.choice(ds.COVERS)
    ok_fonts = font_pairs_for(art)
    try:
        font = int(raw.get("font_pair"))
    except (TypeError, ValueError):
        font = -1
    if font not in ok_fonts:
        font = rnd.choice(ok_fonts)
    traits_in = raw.get("traits") if isinstance(raw.get("traits"), dict) else {}
    traits = {dim: (traits_in.get(dim) if traits_in.get(dim) in opts else rnd.choice(opts)) for dim, opts in ds.DIMS.items()}
    if ds.FONT_PAIRS[font][2] == "hand":
        if traits["card"] in ("minimal", "ticket"):
            traits["card"] = "soft"
        if traits["rad"] == "sharp":
            traits["rad"] = "round"
    if traits["card"] == "glass" and traits["bg"] not in ("glow", "blobs", "wave", "tint"):
        traits["bg"] = "glow"
    if traits["fr"] == cover:
        traits["fr"] = "round"
    seeds = SEED_SLUGS[ds.SEED_KEY[mode]]
    color = raw.get("color") if raw.get("color") in seeds else rnd.choice(seeds)
    cats = [c for c in (raw.get("categories") or []) if c in CAT_UZ][:2] or list(dict.fromkeys(info["cats"]))[:2]
    name = str(raw.get("name") or "").strip()[:40] or rnd.choice(info["names"])
    tagline = str(raw.get("tagline") or "").strip()[:160]
    return {"name": name, "tagline": tagline, "mode": mode, "art": art, "cover": cover, "font_pair": font,
            "traits": traits, "color": color, "categories": cats}


def build_slide_spec(choice: Dict[str, Any], code: int, tid: str = "") -> Dict[str, Any]:
    """A template spec in the same shape as themes/templates.json entries."""
    mode, art, cover, tr = choice["mode"], choice["art"], choice["cover"], dict(choice["traits"])
    title_f, body_f, mood, typ = ds.FONT_PAIRS[choice["font_pair"]]
    rnd = random.Random(code)
    recipe = ds.recipe_for(mode, rnd)
    seeds_key = ds.SEED_KEY[mode]
    offset = SEED_SLUGS[seeds_key].index(choice["color"]) if choice["color"] in SEED_SLUGS[seeds_key] else 0
    colors = ds.colors_for(recipe, seeds_key, offset=offset)
    cats = choice["categories"]
    tagline = choice["tagline"] or (f"{ds.UZ['mode'][mode]}, {ds.UZ['cover'][cover]}, {ds.ARTS[art]['uz']} "
                                    f"va {ds.UZ['card'][tr['card']]}")
    spec = {
        "id": tid or f"{code:03d}_{_slug(choice['name'])}", "code": str(code), "name": choice["name"],
        "tagline": tagline, "mode": "dark" if mode in ("dark", "vivid") else "light", "tone": mode, "art": art,
        "cover_variant": cover, "cards_variant": "grid" if tr["card"] in ("leftbar", "minimal", "solid") else "row",
        "fonts": {"title": title_f, "body": body_f},
        "pptx_fonts": {"title": "Cambria" if title_f in ds._PPTX_SERIF_TITLES else "Arial",
                       "body": "Cambria" if body_f in ds._SERIF_BODY else "Calibri"},
        "type": typ, "traits": tr, "categories": cats,
        "category": " • ".join(CAT_UZ[c] for c in cats) + " • AI",
        "writing_tone": ds.MOOD_TONE.get(cats[0], ds.MOOD_TONE["education"]),
        "pdf_mode": "raster" if art in ds.HEAVY_ART or tr["card"] == "glass" else "vector",
        "recipe": recipe, "colors": colors, "ai": True,
    }
    ds.assign_stickers([spec], seed=code)
    ds.assign_packs([spec], seed=code)
    return spec


STYLE_GROUPS = {8, 9, 11}   # keyword groups that only describe a style (bright, minimal, dark): they weigh less


def heuristic_slide_choices(prompt: str, n: int = 3) -> List[Dict[str, Any]]:
    """Offline chooser: keywords of the prompt pick the art styles, modes and colours. Every matched
    group (subject first, then style) leads one variant, so the variants differ the way the wish does."""
    low = f" {(prompt or '').lower()} "
    scored = []
    for i, (words, arts, modes, colors) in enumerate(KEYWORDS):
        hit = sum(w in low for w in words)
        if hit:
            scored.append((-(hit * (1 if i in STYLE_GROUPS else 2)), i))
    groups = [KEYWORDS[i] for _, i in sorted(scored)] or [((), list(ds.ARTS), [], [])]
    out, used = [], set()
    for k in range(n):
        rnd = _rnd(prompt, k)
        _, g_arts, g_modes, g_colors = groups[k % len(groups)]
        pool = [a for a in g_arts if a not in used] or [a for a in ds.ARTS if a not in used] or list(ds.ARTS)
        art = pool[0] if len(groups) > 1 or k == 0 else rnd.choice(pool)
        if not scored:
            art = rnd.choice(pool)
        used.add(art)
        ok_modes = [m for m in g_modes if m in ds.ARTS[art]["modes"]] or ds.ARTS[art]["modes"]
        mode = ok_modes[0] if g_modes else rnd.choice(ok_modes)
        seeds = SEED_SLUGS[ds.SEED_KEY[mode]]
        cols = [c for c in g_colors if c in seeds]
        col = cols[k % len(cols)] if cols else rnd.choice(seeds)
        out.append(normalize_slide_choice({"art": art, "mode": mode, "color": col}, rnd))
    return out


def slide_options_text() -> str:
    arts = "\n".join(f"- {k}: {v['uz']} (modes: {', '.join(v['modes'])}; font moods: {', '.join(v['fonts'])})"
                     for k, v in ds.ARTS.items())
    fonts = "\n".join(f"- {i}: {t} / {b} ({m})" for i, (t, b, m, _) in enumerate(ds.FONT_PAIRS))
    dims = "\n".join(f"- {d}: {', '.join(o)}" for d, o in ds.DIMS.items())
    seeds = "\n".join(f"- {k} mode colours: {', '.join(v)}" for k, v in SEED_SLUGS.items())
    return (f"ART STYLES:\n{arts}\n\nCOVERS: {', '.join(ds.COVERS)}\n\nFONT PAIRS (index: title / body (mood)):\n{fonts}\n\n"
            f"TRAITS (pick one per line):\n{dims}\n\nCOLOURS (main colour seed; vivid mode uses the dark list):\n{seeds}\n\n"
            f"CATEGORIES: {', '.join(CAT_UZ)}")


async def ai_slide_choices(prompt: str, n: int = 3) -> Tuple[List[Dict[str, Any]], str]:
    """[choice] and the source ("ai" / "offline")."""
    from services import ai_service
    client = ai_service.get_openai_client()
    if client is not None:
        system = ("You are the art director of a presentation template studio. From the admin's wish, design "
                  f"{n} clearly different slide templates by choosing ONLY from the options below. Every template "
                  "must fit the wish; make them differ in art style, cover and mood. Mode must be one of the art "
                  "style's modes and the font pair's mood one of its font moods.\n\n" + slide_options_text() +
                  '\n\nAnswer JSON: {"templates": [{"name": "2-3 word English name", "tagline": "one Uzbek sentence '
                  'describing the look", "mode": "...", "art": "...", "cover": "...", "font_pair": 0, '
                  '"traits": {"bg": "...", "card": "...", "head": "...", "icon": "...", "bul": "...", "fr": "...", '
                  '"dec": "...", "rad": "...", "hl": "..."}, "color": "...", "categories": ["..."]}]}')
        try:
            data = await ai_service._chat_json(client, system, prompt[:600])
            raw = data.get("templates") if isinstance(data, dict) else None
            if isinstance(raw, list) and raw:
                return [normalize_slide_choice(r, _rnd(prompt, k)) for k, r in enumerate(raw[:n])], "ai"
        except Exception:  # noqa: BLE001 - the studio still works offline
            logger.exception("AI slide template choice failed")
    return heuristic_slide_choices(prompt, n), "offline"


def make_slide_draft(choice: Dict[str, Any]) -> Dict[str, Any]:
    """Registers a draft (previewable, not listed) and returns its spec."""
    key = hashlib.sha1(json.dumps(choice, sort_keys=True).encode()).hexdigest()[:8]
    code = DRAFT_START + int(key[:4], 16) % 900
    spec = build_slide_spec(choice, code, tid=f"draft_{key}")
    spec["choice"] = choice
    themes.add_draft(spec)
    return spec


# ====================================================================== referat templates
def _hex(v: Any) -> Optional[str]:
    v = str(v or "").strip()
    return v.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", v) else None


def _lum(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _darken(h: str, k: float) -> str:
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(round(c * k) for c in (r, g, b)))


def referat_options_text() -> str:
    from services.referat import designs
    lays = "\n".join(f"- {k}: {v['name']}" for k, v in designs.LAYOUTS.items())
    pals = "\n".join(f"- {k}: {v['name']} ({v['accent']}, {v['accent2']})" for k, v in designs.PALETTES.items())
    from services.deck import fonts
    fl = ", ".join(sorted(f["key"] for f in fonts.library_fonts()))
    return (f"TITLE PAGE LAYOUTS:\n{lays}\n\nHEADINGS: {', '.join(designs.HEADINGS)}\nPAGE DECORATIONS: "
            f"{', '.join(designs.PAGES)}\n\nPALETTES:\n{pals}\n\nFONTS: {fl}\n\nSAMPLE TOPICS: {', '.join(designs.TOPICS)}")


def normalize_referat_choice(raw: Dict[str, Any], rnd: random.Random) -> Dict[str, Any]:
    from services.deck import fonts
    from services.referat import designs
    raw = raw if isinstance(raw, dict) else {}
    layout = raw.get("layout") if raw.get("layout") in designs.LAYOUTS else rnd.choice(list(designs.LAYOUTS))
    heading = raw.get("heading") if raw.get("heading") in designs.HEADINGS else rnd.choice(list(designs.HEADINGS))
    page = raw.get("page") if raw.get("page") in designs.PAGES else rnd.choice(list(designs.PAGES))
    pal_id = raw.get("palette") if raw.get("palette") in designs.PALETTES else rnd.choice(list(designs.PALETTES))
    pal = dict(designs.PALETTES[pal_id])
    acc, acc2 = _hex(raw.get("accent")), _hex(raw.get("accent2"))
    if acc:
        while _lum(acc) > .42:            # headings must stay readable on white paper
            acc = _darken(acc, .85)
        pal.update(accent=acc, soft=designs._mix(acc, .12), name="AI rangi")
        pal_id = "ai"
    if acc2:
        pal["accent2"] = acc2
    tf = raw.get("title_font") if fonts.is_library_font(str(raw.get("title_font") or "")) else None
    bf = raw.get("body_font") if fonts.is_library_font(str(raw.get("body_font") or "")) else None
    pool = [t for t in designs.TEMPLATES if t["cover"] == layout] or designs.TEMPLATES
    ref = rnd.choice(pool)
    topic = raw.get("topic") if raw.get("topic") in designs.TOPICS else ref["topic"]
    try:
        variant = 1 if int(raw.get("variant") or 0) % 2 else 0
    except (TypeError, ValueError):
        variant = 0
    name = str(raw.get("name") or "").strip()[:40] or f"AI {designs.LAYOUTS[layout]['name']}"
    return {"name": name, "layout": layout, "variant": variant, "heading": heading, "page": page, "palette_id": pal_id,
            "palette": pal, "fonts": {"title": tf or ref["fonts"]["title"], "body": bf or ref["fonts"]["body"]},
            "topic": topic}


def heuristic_referat_choices(prompt: str, n: int = 3) -> List[Dict[str, Any]]:
    from services.referat import designs
    low = f" {(prompt or '').lower()} "
    groups = []
    for words, group in ((("milliy", "o‘zbek", "o'zbek", "sharq", "tarix", "naqsh"), "Milliy"),
                         (("klassik", "rasmiy", "universitet", "akadem", "diplom"), "Klassik"),
                         (("zamonaviy", "modern", "biznes", "yorqin"), "Zamonaviy"),
                         (("qorong", "tun", "dark", "neon"), "To‘q fon"),
                         (("tabiat", "eko", "bio"), "Tabiat"),
                         (("ilm", "fizika", "kimyo", "matem", "texno"), "Ilmiy"),
                         (("maktab", "bola", "o‘quvchi", "o'quvchi", "dars"), "Maktab"),
                         (("rasm", "foto", "surat"), "Rasmli")):
        if any(w in low for w in words):
            groups.append(group)
    lays = [k for k in designs.LAYOUTS if not groups or designs.GROUP_OF.get(k) in groups]
    out, used = [], set()
    for k in range(n):
        rnd = _rnd(prompt, f"r{k}")
        pool = [x for x in lays if x not in used] or lays
        lay = rnd.choice(pool)
        used.add(lay)
        out.append(normalize_referat_choice({"layout": lay, "variant": k % 2}, rnd))
    return out


async def ai_referat_choices(prompt: str, n: int = 3) -> Tuple[List[Dict[str, Any]], str]:
    from services import ai_service
    client = ai_service.get_openai_client()
    if client is not None:
        system = ("You design title pages and styles for Uzbek school/university papers (referat). From the admin's "
                  f"wish, design {n} clearly different templates choosing ONLY from the options below. You may also give "
                  "your own main colour (accent, dark enough for text on white) and second colour.\n\n" + referat_options_text() +
                  '\n\nAnswer JSON: {"templates": [{"name": "1-3 word Uzbek name", "layout": "...", "variant": 0, '
                  '"heading": "...", "page": "...", "palette": "...", "accent": "#RRGGBB", "accent2": "#RRGGBB", '
                  '"title_font": "g:...", "body_font": "g:...", "topic": "..."}]}')
        try:
            data = await ai_service._chat_json(client, system, prompt[:600])
            raw = data.get("templates") if isinstance(data, dict) else None
            if isinstance(raw, list) and raw:
                return [normalize_referat_choice(r, _rnd(prompt, f"r{k}")) for k, r in enumerate(raw[:n])], "ai"
        except Exception:  # noqa: BLE001
            logger.exception("AI referat template choice failed")
    return heuristic_referat_choices(prompt, n), "offline"


def referat_entry(choice: Dict[str, Any], code: int, tid: str = "") -> Dict[str, Any]:
    from services.referat import designs
    return {"id": tid or f"r{code}", "code": code, "name": choice["name"], "cover": choice["layout"],
            "variant": choice["variant"], "heading": choice["heading"], "page": choice["page"],
            "palette_id": choice["palette_id"], "palette": dict(choice["palette"]), "fonts": dict(choice["fonts"]),
            "topic": choice["topic"], "layout": designs.geometry(choice["layout"], choice["variant"]), "ai": True}


def make_referat_draft(choice: Dict[str, Any]) -> Dict[str, Any]:
    from services.referat import designs
    key = hashlib.sha1(json.dumps(choice, sort_keys=True).encode()).hexdigest()[:8]
    entry = referat_entry(choice, DRAFT_START + int(key[:4], 16) % 900, tid=f"rd{key}")
    entry["choice"] = choice
    designs.add_draft(entry)
    return entry


# ====================================================================== storage
async def load() -> None:
    """Publishes the enabled templates from the database (at start and after every change)."""
    from services.referat import designs
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(CustomTemplate).where(CustomTemplate.enabled.is_(True))
                                .order_by(CustomTemplate.code))).scalars().all()
    slides, refs = [], []
    for r in rows:
        try:
            data = json.loads(r.data)
        except ValueError:
            continue
        (slides if r.kind == "slide" else refs).append(data)
    themes.set_custom(slides)
    designs.set_custom(refs)


async def _next_code(kind: str) -> int:
    start = SLIDE_START if kind == "slide" else REFERAT_START
    async with AsyncSessionLocal() as s:
        mx = (await s.execute(select(func.max(CustomTemplate.code)).where(CustomTemplate.kind == kind))).scalar()
    return max(start, (mx or 0) + 1)


async def publish(kind: str, choice: Dict[str, Any], prompt: str = "", admin: str = "") -> Dict[str, Any]:
    """Saves a chosen draft as a real template; it appears in the bot at once."""
    code = await _next_code(kind)
    if kind == "slide":
        data = build_slide_spec(choice, code)
    else:
        data = referat_entry(choice, code)
    data["choice"] = choice
    async with AsyncSessionLocal() as s:
        s.add(CustomTemplate(id=data["id"], kind=kind, code=code, name=choice["name"][:120],
                             data=json.dumps(data, ensure_ascii=False), prompt=(prompt or "")[:1000],
                             enabled=True, created_by=(admin or "")[:64], created_at=datetime.utcnow()))
        await s.commit()
    await load()
    return data


async def list_all(kind: Optional[str] = None) -> List[CustomTemplate]:
    async with AsyncSessionLocal() as s:
        q = select(CustomTemplate).order_by(CustomTemplate.code.desc())
        if kind:
            q = q.where(CustomTemplate.kind == kind)
        return list((await s.execute(q)).scalars().all())


async def set_enabled(tid: str, enabled: bool) -> bool:
    async with AsyncSessionLocal() as s:
        row = await s.get(CustomTemplate, tid)
        if row is None:
            return False
        row.enabled = enabled
        await s.commit()
    await load()
    return True


async def delete(tid: str) -> bool:
    async with AsyncSessionLocal() as s:
        row = await s.get(CustomTemplate, tid)
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
    await load()
    return True
