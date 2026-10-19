"""
Layout catalog: the single source of truth for every slide layout the engine can draw.

The AI pipeline sends this catalog to the model (names + "use when" + field limits),
and the renderer uses `normalize_slide()` to coerce whatever the model returned into a
shape the Jinja templates can rely on (lists clamped to their allowed sizes, strings
trimmed to their character budgets, missing optional fields filled with safe defaults).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

# Character budgets are tuned for a 1920x1080 canvas at the theme's default type scale.
# They are deliberately a little generous: the renderer's auto-fit shrinks text first,
# and only trims content when shrinking alone is not enough.
T_TITLE = 70
T_LEAD = 220
T_ITEM_TITLE = 48
T_ITEM_TEXT = 170
T_BULLET = 150
T_PHOTO = 60  # English stock-photo query for one card / step (photo templates show it)

LAYOUTS: Dict[str, Dict[str, Any]] = {
    "cover": {
        "use_when": "Title slide only (always slide 1).",
        "has_visual": True,
        "fields": {"title": T_TITLE + 30, "subtitle": 160},
    },
    "agenda": {
        "use_when": "Plan / table of contents listing the sections of the talk (usually slide 2).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "items": {"min": 3, "max": 6, "fields": {"title": T_ITEM_TITLE, "text": 90}}},
    },
    "text_image": {
        "use_when": "Explaining one concept in a short paragraph plus a few bullets, next to a large picture.",
        "has_visual": True,
        "fields": {"title": T_TITLE, "lead": T_LEAD, "bullets": {"min": 2, "max": 5, "len": T_BULLET}},
    },
    "cards": {
        "use_when": "3-4 parallel components, types, features or parts of something, each with an icon.",
        "has_visual": False,
        "fields": {"title": T_TITLE, "lead": 160,
                   "items": {"min": 3, "max": 4, "fields": {"icon": 40, "title": T_ITEM_TITLE, "text": T_ITEM_TEXT, "photo": T_PHOTO}}},
    },
    "icon_list": {
        "use_when": "3-5 facts, reasons, properties or rules, listed vertically with icons, next to a picture.",
        "has_visual": True,
        "fields": {"title": T_TITLE,
                   "items": {"min": 3, "max": 5, "fields": {"icon": 40, "title": T_ITEM_TITLE, "text": 140, "photo": T_PHOTO}}},
    },
    "process": {
        "use_when": "3-5 sequential steps or stages that happen in order (a mechanism, a method, a procedure).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "lead": 160,
                   "steps": {"min": 3, "max": 5, "fields": {"title": T_ITEM_TITLE, "text": 150, "photo": T_PHOTO}}},
    },
    "timeline": {
        "use_when": "3-6 dated events in history or a chronology (years, centuries, periods).",
        "has_visual": False,
        "fields": {"title": T_TITLE,
                   "events": {"min": 3, "max": 6, "fields": {"date": 24, "title": T_ITEM_TITLE, "text": 120}}},
    },
    "cycle": {
        "use_when": "3-6 stages that repeat in a loop (a biological/chemical/economic cycle).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "center": 40,
                   "stages": {"min": 3, "max": 6, "fields": {"title": 36, "text": 110}}},
    },
    "stats": {
        "use_when": "2-4 key numbers with short explanations (real, well-known figures only).",
        "has_visual": True,
        "fields": {"title": T_TITLE, "lead": 160,
                   "stats": {"min": 2, "max": 4, "fields": {"value": 14, "label": 40, "text": 120}}},
    },
    "chart": {
        "use_when": "A numeric series worth plotting: a comparison of 3-8 categories, a trend over time, or shares of a whole.",
        "has_visual": False,
        "fields": {"title": T_TITLE, "insights": {"min": 1, "max": 3, "len": 140}, "source": 90},
    },
    "comparison": {
        "use_when": "Two things compared side by side (A vs B, before/after, advantages/disadvantages).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "verdict": 160,
                   "left": {"title": 40, "points": {"min": 2, "max": 5, "len": 110}},
                   "right": {"title": 40, "points": {"min": 2, "max": 5, "len": 110}}},
    },
    "pyramid": {
        "use_when": "3-5 levels of a hierarchy, from the top (smallest/most important) to the base.",
        "has_visual": False,
        "fields": {"title": T_TITLE,
                   "levels": {"min": 3, "max": 5, "fields": {"title": 36, "text": 120}}},
    },
    "quote": {
        "use_when": "A real, attributable quotation by a known person related to the topic.",
        "has_visual": True,
        "fields": {"quote": 220, "author": 60, "role": 80},
    },
    "formula": {
        "use_when": "A formula or chemical/physical equation, with its terms explained.",
        "has_visual": False,
        "fields": {"title": T_TITLE, "formula": 90, "caption": 160,
                   "terms": {"min": 2, "max": 5, "fields": {"symbol": 16, "meaning": 90}}},
    },
    "highlight": {
        "use_when": "One big idea, definition or striking fact, shown large over a full-bleed picture.",
        "has_visual": True,
        "fields": {"eyebrow": 40, "statement": 150, "text": 220},
    },
    "section": {
        "use_when": "A divider that opens a major part of a long talk (only in presentations of 12+ slides).",
        "has_visual": True,
        "fields": {"number": 4, "title": T_TITLE, "subtitle": 140},
    },
    "table": {
        "use_when": "Structured facts in rows and 2-4 columns (classification, properties, comparison of several items).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "note": 140},
    },
    "summary": {
        "use_when": "Conclusion: 3-5 key takeaways and one final message (usually the last content slide).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "points": {"min": 3, "max": 5, "len": 150}, "takeaway": 180},
    },
    "references": {
        "use_when": "List of literature / sources used (only if the user asked for references).",
        "has_visual": False,
        "fields": {"title": T_TITLE, "sources": {"min": 2, "max": 8, "len": 200}},
    },
    "closing": {
        "use_when": "Final 'Thank you / Questions' slide.",
        "has_visual": True,
        "fields": {"title": 50, "subtitle": 140},
    },
}

# Layouts the AI may pick for content slides (cover is forced on slide 1).
CONTENT_LAYOUTS = [k for k in LAYOUTS if k != "cover"]

# Old layout names produced by the previous generator (and stored orders) -> new names.
LEGACY_ALIASES = {
    "hero": "cover", "title": "cover", "split": "text_image", "image_text": "text_image",
    "text_image_left": "text_image", "statistics": "stats", "data": "chart", "conclusion": "summary",
    "image_full": "highlight", "quote_slide": "quote",
}

CHART_TYPES = {"bar", "column", "line", "donut", "pie"}
VISUAL_KINDS = {"photo", "illustration", "none"}


def _trim(value: Any, limit: int) -> str:
    if value is None:
        return ""
    s = " ".join(str(value).split())
    if len(s) <= limit:
        return s
    cut = s[: limit - 1]
    # Prefer cutting at a word boundary.
    if " " in cut[limit // 2:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-") + "…"


def _clamp_list(values: Any, spec: Dict[str, Any]) -> List[Any]:
    items = values if isinstance(values, list) else []
    items = items[: spec.get("max", len(items))]
    if "fields" in spec:
        out = []
        for it in items:
            if isinstance(it, str):
                # A bare string where an object was expected: use it as the title.
                first = next(iter(spec["fields"]))
                it = {first: it}
            if not isinstance(it, dict):
                continue
            out.append({f: _trim(it.get(f, ""), lim) for f, lim in spec["fields"].items()})
        return out
    return [_trim(v, spec.get("len", T_BULLET)) for v in items if str(v).strip()]


def resolve_layout_name(name: Any) -> str:
    n = str(name or "").strip().lower()
    n = LEGACY_ALIASES.get(n, n)
    return n if n in LAYOUTS else "text_image"


def _legacy_to_new(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Maps the old generator's field names onto the new schema so old content still renders."""
    s = dict(slide)
    if "layout" not in s and "layout_type" in s:
        s["layout"] = s["layout_type"]
    if "cards_data" in s and "items" not in s:
        s["items"] = [{"title": c.get("title", ""), "text": c.get("desc", ""), "icon": c.get("icon", "")}
                      for c in s.get("cards_data") or []]
    if "agenda_items" in s and "items" not in s:
        s["items"] = [{"title": c.get("title", ""), "text": c.get("desc", "")} for c in s.get("agenda_items") or []]
    if "stats_data" in s and "stats" not in s:
        s["stats"] = [{"value": c.get("value", ""), "label": c.get("label", ""), "text": c.get("desc", "")}
                      for c in s.get("stats_data") or []]
    if "process_steps" in s and "steps" not in s:
        s["steps"] = [{"title": c.get("title", ""), "text": c.get("desc", "")} for c in s.get("process_steps") or []]
    if "quote_data" in s and "quote" not in s:
        s["quote"] = (s.get("quote_data") or {}).get("quote", "")
        s["author"] = (s.get("quote_data") or {}).get("author", "")
    if "bullet_points" in s and "bullets" not in s:
        s["bullets"] = s.get("bullet_points") or []
    if "lead" not in s and s.get("subtitle"):
        s["lead"] = s.get("subtitle")
    if "image_query" in s and "visual" not in s:
        s["visual"] = {"kind": "photo", "query": s.get("image_query", "")}
    return s


def _normalize_chart(chart: Any) -> Dict[str, Any]:
    c = chart if isinstance(chart, dict) else {}
    ctype = str(c.get("type", "column")).lower()
    if ctype not in CHART_TYPES:
        ctype = "column"
    labels = [_trim(x, 22) for x in (c.get("labels") or [])][:8]
    series_in = c.get("series") or []
    if not series_in and c.get("values"):
        series_in = [{"name": c.get("name", ""), "values": c.get("values")}]
    series = []
    for s in series_in[:3]:
        vals = []
        for v in (s.get("values") or [])[: len(labels)]:
            try:
                vals.append(float(str(v).replace(",", ".").replace("%", "").strip()))
            except ValueError:
                vals.append(0.0)
        if vals:
            series.append({"name": _trim(s.get("name", ""), 30), "values": vals})
    if ctype in ("donut", "pie"):
        series = series[:1]
    n = min([len(labels)] + [len(s["values"]) for s in series]) if series else 0
    labels = labels[:n]
    for s in series:
        s["values"] = s["values"][:n]
    return {"type": ctype, "labels": labels, "series": series, "unit": _trim(c.get("unit", ""), 12)}


def _normalize_table(slide: Dict[str, Any]) -> Dict[str, Any]:
    headers = [_trim(h, 30) for h in (slide.get("headers") or [])][:4]
    rows = []
    for r in (slide.get("rows") or [])[:6]:
        if isinstance(r, dict):
            r = list(r.values())
        if not isinstance(r, list):
            continue
        rows.append([_trim(c, 80) for c in r[: max(1, len(headers) or 4)]])
    ncols = len(headers) or (max((len(r) for r in rows), default=0))
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    return {"headers": headers, "rows": rows}


def normalize_visual(v: Any, fallback_query: str = "") -> Dict[str, Any]:
    if isinstance(v, str):
        v = {"kind": "photo", "query": v}
    v = v if isinstance(v, dict) else {}
    kind = str(v.get("kind", "photo")).lower()
    if kind not in VISUAL_KINDS:
        kind = "photo"
    return {
        "kind": kind,
        "query": _trim(v.get("query") or fallback_query, 100),
        "prompt": _trim(v.get("prompt", ""), 400),
        "icon": _trim(v.get("icon", ""), 40),
    }


def normalize_slide(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a deep-copied, schema-conformant version of one slide dict."""
    s = _legacy_to_new(copy.deepcopy(slide or {}))
    layout = resolve_layout_name(s.get("layout"))
    spec = LAYOUTS[layout]
    out: Dict[str, Any] = {"layout": layout, "variant": str(s.get("variant", "") or "")}

    for field, rule in spec["fields"].items():
        if isinstance(rule, int):
            out[field] = _trim(s.get(field, ""), rule)
        elif "min" in rule:
            out[field] = _clamp_list(s.get(field), rule)
        else:  # nested object (comparison sides)
            src = s.get(field) if isinstance(s.get(field), dict) else {}
            obj = {}
            for f2, r2 in rule.items():
                obj[f2] = _trim(src.get(f2, ""), r2) if isinstance(r2, int) else _clamp_list(src.get(f2), r2)
            out[field] = obj

    if layout == "chart":
        out["chart"] = _normalize_chart(s.get("chart"))
    if layout == "table":
        out.update(_normalize_table(s))
    if layout == "comparison":
        for side in ("left", "right"):
            out[side].setdefault("points", [])

    out["visual"] = normalize_visual(s.get("visual"), fallback_query=s.get("title", ""))
    out["notes"] = _trim(s.get("notes", ""), 1200)
    out["section"] = _trim(s.get("section", ""), 40)
    return out


def is_slide_usable(slide: Dict[str, Any]) -> bool:
    """A slide whose required lists came back empty would render as a blank shell."""
    layout = slide["layout"]
    spec = LAYOUTS[layout]["fields"]
    for field, rule in spec.items():
        # A list may come back one item short (it renders fine), but a core list must not be empty.
        if isinstance(rule, dict) and rule.get("min", 0) >= 2 and len(slide.get(field) or []) < rule["min"] - 1:
            return False
    if layout == "chart":
        return bool(slide["chart"]["series"]) and len(slide["chart"]["labels"]) >= 2
    if layout == "table":
        return bool(slide.get("rows"))
    if layout == "comparison":
        return bool(slide["left"]["points"]) and bool(slide["right"]["points"])
    if layout == "quote":
        return bool(slide.get("quote"))
    if layout == "formula":
        return bool(slide.get("formula"))
    return True


def downgrade_to_text_image(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback for an unusable slide: keep its words, show them as text + picture."""
    bullets: List[str] = []
    for key in ("items", "steps", "events", "stages", "levels", "stats", "points"):
        for it in slide.get(key) or []:
            if isinstance(it, dict):
                t = " — ".join(x for x in [it.get("title") or it.get("value") or it.get("date"), it.get("text")] if x)
            else:
                t = str(it)
            if t:
                bullets.append(t)
    return normalize_slide({
        "layout": "text_image",
        "title": slide.get("title") or slide.get("statement") or slide.get("quote") or "",
        "lead": slide.get("lead") or slide.get("text") or slide.get("caption") or "",
        "bullets": bullets[:5],
        "visual": slide.get("visual"),
        "notes": slide.get("notes", ""),
    })


def catalog_for_prompt() -> str:
    """Compact human-readable catalog for the model's system prompt."""
    lines = []
    for name in CONTENT_LAYOUTS:
        spec = LAYOUTS[name]
        lines.append(f"- {name}: {spec['use_when']}" + (" Has a large picture." if spec["has_visual"] else ""))
    return "\n".join(lines)
