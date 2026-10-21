"""Lucide icon lookup (ISC licence, bundled in assets/icons)."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icons")

# A curated set the model picks from. Sending all ~2100 names would waste tokens and
# invite obscure picks; these cover school and university subjects well.
CURATED = [
    "leaf", "sprout", "tree-pine", "trees", "flower-2", "sun", "cloud-sun", "cloud-rain", "droplet", "droplets",
    "wind", "snowflake", "mountain", "waves", "globe", "earth", "map", "compass", "flame", "zap",
    "atom", "flask-conical", "test-tube", "microscope", "dna", "beaker", "orbit", "magnet", "thermometer", "gauge",
    "brain", "heart-pulse", "heart", "activity", "stethoscope", "pill", "syringe", "bone", "eye", "hand",
    "bug", "fish", "bird", "rabbit", "paw-print", "shell", "egg", "apple", "wheat", "salad",
    "recycle", "battery-charging", "factory", "car", "plane", "ship", "train-front", "rocket", "satellite", "telescope",
    "cpu", "code", "database", "server", "cloud", "wifi", "smartphone", "laptop", "monitor", "bot",
    "shield-check", "lock", "key", "network", "git-branch", "layers", "boxes", "puzzle", "settings", "wrench",
    "book-open", "graduation-cap", "school", "library", "pen-tool", "pencil", "notebook-pen", "languages", "quote", "scroll",
    "landmark", "castle", "crown", "swords", "flag", "scale", "gavel", "users", "user", "handshake",
    "building-2", "briefcase", "chart-column", "chart-line", "chart-pie", "trending-up", "trending-down", "coins", "wallet", "banknote",
    "shopping-cart", "store", "target", "lightbulb", "sparkles", "star", "award", "trophy", "medal", "rocket",
    "calendar", "clock", "hourglass", "timer", "history", "route", "milestone", "map-pin", "home", "tent",
    "music", "palette", "camera", "film", "mic", "megaphone", "message-circle", "mail", "newspaper", "tv",
    "calculator", "sigma", "pi", "percent", "ruler", "triangle", "circle-dot", "infinity", "binary", "function-square",
    "check-circle-2", "x-circle", "alert-triangle", "info", "help-circle", "search", "filter", "list-checks", "clipboard-list", "file-text",
    "arrow-right", "refresh-cw", "repeat", "link", "share-2", "workflow", "split", "merge", "circle-plus", "circle-minus",
]


@lru_cache(maxsize=1)
def _icons() -> Dict[str, str]:
    with open(os.path.join(_ASSETS, "lucide.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _tags() -> Dict[str, List[str]]:
    try:
        with open(os.path.join(_ASSETS, "lucide_tags.json"), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


# Lucide renamed a number of icons over time; the model often uses the older names.
_RENAMES = {
    "bar-chart": "chart-column", "bar-chart-2": "chart-column", "bar-chart-3": "chart-column",
    "line-chart": "chart-line", "pie-chart": "chart-pie", "alert-triangle": "triangle-alert",
    "check-circle": "circle-check", "check-circle-2": "circle-check-big", "x-circle": "circle-x",
    "help-circle": "circle-help", "function-square": "square-function", "home": "house",
    "flask": "flask-conical", "test-tube-2": "test-tube", "graduation": "graduation-cap",
}


def resolve(name: Optional[str], fallback_text: str = "") -> str:
    """Returns an existing Lucide icon name for `name`, or a best guess from `fallback_text`."""
    icons = _icons()
    n = (name or "").strip().lower().replace("_", "-").replace(" ", "-")
    n = _RENAMES.get(n, n)
    if n in icons:
        return n
    words = [w for w in re.split(r"[^a-z0-9]+", f"{n} {fallback_text}".lower()) if len(w) > 2]
    if words:
        best, best_score = None, 0
        for icon, tags in _tags().items():
            hay = set(icon.split("-")) | {t.lower() for t in tags}
            score = sum(2 if w in icon.split("-") else 1 for w in words if w in hay)
            if score > best_score:
                best, best_score = icon, score
        if best and best in icons:
            return best
    return "sparkles"


def svg(name: Optional[str], fallback_text: str = "", stroke_width: float = 1.75, extra_attrs: str = "") -> str:
    """Inline SVG markup for an icon, coloured by `currentColor`."""
    key = resolve(name, fallback_text)
    inner = _icons().get(key, "")
    return (
        f'<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" {extra_attrs}>{inner}</svg>'
    )


def inner_markup(name: Optional[str], fallback_text: str = "") -> str:
    return _icons().get(resolve(name, fallback_text), "")


def curated_names() -> List[str]:
    icons = _icons()
    out, seen = [], set()
    for n in CURATED:
        r = _RENAMES.get(n, n)
        if r in icons and r not in seen:
            out.append(r)
            seen.add(r)
    return out
