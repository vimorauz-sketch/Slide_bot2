"""Theme loading.

200 templates, each with 10 colour sets:
  * 1-20   hand-made design families: themes/<id>/theme.json + theme.css (+ decor.j2)
  * 21-200 generated templates (themes/templates.json, scripts/generate_templates.py): one choice per
           design dimension, drawn with the trait classes in services/deck/templates/traits.css
A colour set is addressed as "<template id>~<colour slug>"; the bare id is the template's default
colours. All CSS reads the base palette through custom properties, so swapping colours only
appends a :root block.
"""
from __future__ import annotations

import copy
import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

THEMES_DIR = Path(__file__).resolve().parents[2] / "themes"
DEFAULT_THEME = "05_nature_organic"
COLOR_SEP = "~"

_ALIASES: Dict[str, str] = {}

# Gallery categories: (key, label, emoji, tags that put a theme in it)
CATEGORIES = [
    ("photo", "Real foto", "📷", {"photo"}),
    ("education", "Ta’lim va fan", "🎓", {"education", "school", "science", "academic", "math", "language", "notes", "kids"}),
    ("business", "Biznes", "💼", {"business", "finance", "economics", "modern"}),
    ("tech", "Texnologiya", "💻", {"tech", "it", "engineering", "space"}),
    ("creative", "Ijodiy", "🎨", {"creative", "media", "design", "art", "travel"}),
    ("nature", "Tabiat va tibbiyot", "🌿", {"nature", "biology", "medicine", "health"}),
    ("culture", "Madaniyat va tarix", "🏛", {"culture", "literature", "history", "uzbek", "philosophy"}),
    ("minimal", "Minimal", "◻️", {"minimal"}),
    ("dark", "Qorong‘i", "🌙", set()),
    ("light", "Yorug‘", "☀️", set()),
]

_PALETTE_VARS = {"bg": "--bg", "bg2": "--bg2", "surface": "--surface", "text": "--text", "muted": "--muted",
                 "primary": "--primary", "secondary": "--secondary", "accent": "--accent", "ink": "--ink",
                 "on_primary": "--on-primary"}


def _hex(c: str, default: str) -> str:
    c = str(c or "").strip()
    if not c.startswith("#"):
        c = "#" + c
    return c if len(c) == 7 else default


def palette_css(p: Dict[str, str]) -> str:
    return ":root{" + "".join(f"{v}:{p[k]};" for k, v in _PALETTE_VARS.items() if p.get(k)) + "}"


def theme_categories(t: Dict[str, Any]) -> List[str]:
    tags = set(t.get("tags") or []) | set(t.get("categories_raw") or [])
    cats = [key for key, _, _, ctags in CATEGORIES if (ctags | {key}) & tags]
    cats.append("dark" if t.get("mode") == "dark" else "light")
    return cats


# ------------------------------------------------------------------ data files
@lru_cache(maxsize=1)
def _data() -> Dict[str, Any]:
    path = THEMES_DIR / "templates.json"
    if not path.exists():
        return {"family_colors": {}, "templates": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _generated() -> Dict[str, Dict[str, Any]]:
    return {t["id"]: t for t in _data()["templates"]}


def list_family_ids() -> List[str]:
    return sorted(p.name for p in THEMES_DIR.iterdir() if (p / "theme.json").exists())


def list_theme_ids() -> List[str]:
    """All 200 templates ordered by number (colour sets are not separate entries)."""
    return list_family_ids() + list(_generated())


# ------------------------------------------------------------------ building themes
def _load_family(theme_id: str) -> Dict[str, Any]:
    d = THEMES_DIR / theme_id
    with open(d / "theme.json", encoding="utf-8") as f:
        t = json.load(f)
    t["id"] = theme_id
    t["css"] = (d / "theme.css").read_text(encoding="utf-8") if (d / "theme.css").exists() else ""
    t["has_decor"] = (d / "decor.j2").exists()
    t["family"] = theme_id
    t["trait_classes"] = ""
    t["categories"] = theme_categories(t)
    cols = copy.deepcopy(_data()["family_colors"].get(theme_id) or [{"slug": "asl", "name": "Asl", "palette": None}])
    for c in cols:
        if c["palette"] is None:
            c["palette"] = dict(t["palette"])
    t["colors"] = cols
    return t


def _load_generated(spec: Dict[str, Any]) -> Dict[str, Any]:
    from services.deck.design_space import type_css

    t = copy.deepcopy(spec)
    pal = dict(t["colors"][0]["palette"])
    t["palette"] = pal
    tr = t["traits"]
    t["trait_classes"] = " ".join(f"tr-{dim}-{val}" for dim, val in tr.items()) + f" tone-{t['tone']}"
    if t.get("photo"):
        t["trait_classes"] += " photo-mode" + (" tr-eyebrow-num" if t.get("eyebrow_num") else "")
    extra = ""
    if t["tone"] in ("light", "cream"):
        extra = ":root{--ov:color-mix(in srgb, var(--primary) 62%, var(--ink));}"
    t["css"] = type_css(t.get("type", {})) + extra + palette_css(pal)
    t["has_decor"] = False
    t["family"] = t["id"]
    t["categories_raw"] = t.get("categories", [])
    t["categories"] = theme_categories(t)
    t["image_style"] = t.get("image_style", "photo")
    return t


@lru_cache(maxsize=None)
def _load_base(theme_id: str) -> Dict[str, Any]:
    spec = _generated().get(theme_id)
    return _load_generated(spec) if spec else _load_family(theme_id)


def split_key(key: str) -> Tuple[str, str]:
    base, _, color = str(key).partition(COLOR_SEP)
    return base, color


@lru_cache(maxsize=None)
def _load(theme_key: str) -> Dict[str, Any]:
    base_id, color = split_key(theme_key)
    t = _load_base(base_id)
    if not color:
        t = copy.deepcopy(t)
        t["color_name"] = t["colors"][0]["name"]
        t["color_slug"] = t["colors"][0]["slug"]
        return t
    c = next((c for c in t["colors"] if c["slug"] == color), None)
    t = copy.deepcopy(t)
    if c is None or c is t["colors"][0] or c["slug"] == t["colors"][0]["slug"]:
        c = t["colors"][0]
    t["palette"] = {**t["palette"], **c["palette"]}
    t["css"] += "\n/* colours */\n" + palette_css(c["palette"])
    t["id"] = theme_key if c is not t["colors"][0] else base_id
    t["color_name"], t["color_slug"] = c["name"], c["slug"]
    return t


def _build_aliases() -> Dict[str, str]:
    if not _ALIASES:
        for tid in list_theme_ids():
            t = _load_base(tid)
            code = str(int(t["code"]))
            for k in (tid, code, f"{int(code):02d}", f"{int(code):03d}", f"tpl_{tid}", f"tpl_{code}"):
                _ALIASES.setdefault(k, tid)
            for c in t["colors"][1:]:
                _ALIASES[f"{tid}{COLOR_SEP}{c['slug']}"] = f"{tid}{COLOR_SEP}{c['slug']}"
                _ALIASES[f"tpl_{tid}{COLOR_SEP}{c['slug']}"] = f"{tid}{COLOR_SEP}{c['slug']}"
            _ALIASES[f"{tid}{COLOR_SEP}{t['colors'][0]['slug']}"] = tid
    return _ALIASES


def resolve_theme_id(key: Any) -> str:
    k = str(key or "").strip()
    return _build_aliases().get(k, DEFAULT_THEME)


def is_known_theme(key: Any) -> bool:
    return str(key or "").strip() in _build_aliases()


def get_theme(key_or_spec: Any = DEFAULT_THEME) -> Dict[str, Any]:
    """Returns a theme dict. A dict argument is an AI custom design spec (colours/fonts), or a
    style choice on top of a template: {"base": key-or-spec, "fonts": {"title", "body"}, "text_color"}."""
    if isinstance(key_or_spec, dict):
        if "base" in key_or_spec:
            return apply_style(get_theme(key_or_spec["base"]), key_or_spec)
        return theme_from_custom_spec(key_or_spec)
    return copy.deepcopy(_load(resolve_theme_id(key_or_spec)))


def apply_style(t: Dict[str, Any], style: Dict[str, Any]) -> Dict[str, Any]:
    """The user's own fonts (from the font library) and text colour on top of a template."""
    from services.deck import fonts as _fonts
    chosen = style.get("fonts") or {}
    for role in ("title", "body"):
        fid = chosen.get(role)
        if fid and _fonts.is_library_font(fid):
            t.setdefault("fonts", {})[role] = fid
            # the PowerPoint file names the same font (the customer gets its TTF files to install)
            t.setdefault("pptx_fonts", {})[role] = _fonts.family_name(fid)
            if role == "title" and (_fonts.library_font(fid) or {}).get("category") == "hand":
                # handwriting must not be spaced out in capitals (theme titles often are)
                t["css"] = t.get("css", "") + ("\n:root{--title-transform:none !important;"
                                               "--title-tracking:0 !important;}")
    color = style.get("text_color")
    if color and re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color)):
        t.setdefault("palette", {})["text"] = color
        t["css"] = t.get("css", "") + (f"\n:root{{--text:{color} !important;--title-color:{color} !important;"
                                       f"--muted:color-mix(in srgb, {color} 74%, var(--bg)) !important;}}")
    t["style"] = {k: v for k, v in (("fonts", chosen), ("text_color", color)) if v}
    return t


def contrast(c1: str, c2: str) -> float:
    """WCAG contrast ratio of two #rrggbb colours."""
    def lum(h):
        h = h.lstrip("#")
        ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = lum(c1), lum(c2)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def theme_colors(theme_id: str) -> List[Dict[str, Any]]:
    """Colour sets of a template: [{key, slug, name, palette}], the first being the default."""
    base = split_key(resolve_theme_id(theme_id))[0]
    t = _load_base(base)
    return [{"key": base if i == 0 else f"{base}{COLOR_SEP}{c['slug']}", "slug": c["slug"], "name": c["name"], "palette": c["palette"]}
            for i, c in enumerate(t["colors"])]


def all_theme_keys() -> List[str]:
    return [c["key"] for tid in list_theme_ids() for c in theme_colors(tid)]


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def theme_from_custom_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Builds a theme from the colours an AI design prompt produced, on top of a base theme
    whose structure (light or dark) matches the requested background."""
    bg = _hex(spec.get("background_color") or spec.get("background"), "#F7FAFC")
    dark = _luminance(bg) < 0.45
    base = copy.deepcopy(_load("01_midnight_tech" if dark else "02_clean_academic"))
    p = base["palette"]
    p["bg"] = bg
    p["primary"] = _hex(spec.get("primary_color") or spec.get("primary"), p["primary"])
    p["secondary"] = _hex(spec.get("accent_color") or spec.get("accent"), p["secondary"])
    p["surface"] = _hex(spec.get("card_color") or spec.get("card"), p["surface"])
    p["text"] = _hex(spec.get("text_color") or spec.get("text"), p["text"])
    base["id"] = "custom_ai"
    base["name"] = spec.get("name") or "Custom AI Design"
    base["css"] += (
        "\n:root{" + f"--bg:{p['bg']};--primary:{p['primary']};--secondary:{p['secondary']};"
        f"--surface:{p['surface']};--card-bg:{p['surface']};--text:{p['text']};--title-color:{p['text']};" + "}"
    )
    return base


def theme_summary(theme_id: str) -> Optional[Dict[str, Any]]:
    try:
        t = _load(resolve_theme_id(theme_id))
    except OSError:
        return None
    return {k: t.get(k) for k in ("id", "code", "name", "category", "tagline", "family", "color_name")}


def catalog() -> List[Dict[str, Any]]:
    """Light-weight list of the 200 templates (with their colour sets) for galleries and menus."""
    out = []
    for tid in list_theme_ids():
        t = _load_base(tid)
        cols = theme_colors(tid)
        out.append({
            "id": tid, "code": int(t["code"]), "name": t["name"], "category": t.get("category", ""),
            "tagline": t.get("tagline", ""), "mode": t.get("mode", "light"), "categories": t["categories"],
            "handmade": tid in list_family_ids(),
            "colors": [{"key": c["key"], "slug": c["slug"], "name": c["name"],
                        "swatch": [c["palette"].get(k) for k in ("bg", "primary", "secondary", "accent")]} for c in cols],
        })
    return out


def clear_cache() -> None:
    for fn in (_load, _load_base, _data, _generated):
        fn.cache_clear()
    _ALIASES.clear()
