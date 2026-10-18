"""
Colour sets for the templates.

Each template has a *recipe* that turns a few seed hues into a full palette in
OKLCH space (perceptually even lightness, so every variant of a family has the same contrast and
mood), and a curated list of named seeds. Every generated palette is checked for WCAG contrast
(body text >= 7:1 on the background, titles/icons >= 3:1) and nudged until it passes.

`scripts/generate_templates.py` writes the colour sets to themes/templates.json, which themes.py loads.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple


# ------------------------------------------------------------------ colour maths
def _lin_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklch_to_rgb(L: float, C: float, h: float) -> Tuple[float, float, float]:
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bl


def _in_gamut(rgb) -> bool:
    return all(-0.0005 <= c <= 1.0005 for c in rgb)


def oklch(L: float, C: float, h: float) -> str:
    """OKLCH -> hex, reducing chroma until the colour fits in sRGB."""
    C = max(0.0, C)
    rgb = oklch_to_rgb(L, C, h)
    while not _in_gamut(rgb) and C > 0:
        C -= 0.005
        rgb = oklch_to_rgb(L, C, h)
    r, g, b = (round(_lin_to_srgb(c) * 255) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    vals = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        vals.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _fix(L: float, C: float, h: float, against: str, minimum: float, step: float) -> str:
    """Moves lightness by `step` until the colour reaches `minimum` contrast against `against`."""
    col = oklch(L, C, h)
    for _ in range(60):
        if contrast(col, against) >= minimum:
            break
        L = max(0.02, min(0.99, L + step))
        col = oklch(L, C, h)
    return col


def on_color(bg: str) -> str:
    dark, light = "#0B0B12", "#FFFFFF"
    return light if contrast(light, bg) >= contrast(dark, bg) else dark


# ------------------------------------------------------------------ recipes
def light_recipe(h: float, h2: float, h3: float, *, tint: float = 0.012, prim_L: float = 0.47, prim_C: float = 0.14,
                 bg_L: float = 0.985, surface: str = "#FFFFFF") -> Dict[str, str]:
    bg = oklch(bg_L, tint, h)
    p = {
        "bg": bg, "bg2": oklch(bg_L - 0.05, tint * 3 + 0.02, h), "surface": surface,
        "text": _fix(0.24, 0.045, h, bg, 11, -0.02), "muted": _fix(0.50, 0.03, h, bg, 5, -0.02),
        "primary": _fix(prim_L, prim_C, h, bg, 4.5, -0.02), "secondary": _fix(0.60, 0.13, h2, bg, 2.6, -0.02),
        "accent": oklch(0.78, 0.14, h3), "ink": oklch(0.2, 0.05, h),
    }
    p["on_primary"] = on_color(p["primary"])
    return p


def dark_recipe(h: float, h2: float, h3: float, *, bg_L: float = 0.15, bg_C: float = 0.04, prim_L: float = 0.84,
                prim_C: float = 0.15) -> Dict[str, str]:
    bg = oklch(bg_L, bg_C, h)
    p = {
        "bg": bg, "bg2": oklch(bg_L + 0.08, bg_C + 0.02, h), "surface": oklch(bg_L + 0.06, bg_C + 0.01, h),
        "text": oklch(0.97, 0.012, h), "muted": _fix(0.78, 0.035, h, bg, 6, 0.02),
        "primary": _fix(prim_L, prim_C, h, bg, 6, 0.02), "secondary": _fix(0.72, 0.15, h2, bg, 4, 0.02),
        "accent": _fix(0.75, 0.16, h3, bg, 4, 0.02), "ink": bg,
    }
    p["on_primary"] = on_color(p["primary"])
    return p


def cream_recipe(h: float, h2: float, h3: float, *, prim_L: float = 0.36, prim_C: float = 0.11, bg_h: float = 80,
                 bg_C: float = 0.025, accent_gold: bool = True) -> Dict[str, str]:
    """Warm paper backgrounds with a deep primary (editorial, heritage, zen)."""
    bg = oklch(0.955, bg_C, bg_h)
    p = {
        "bg": bg, "bg2": oklch(0.91, bg_C + 0.015, bg_h), "surface": oklch(0.98, bg_C * 0.6, bg_h),
        "text": _fix(0.27, 0.035, h, bg, 11, -0.02), "muted": _fix(0.50, 0.035, h, bg, 5, -0.02),
        "primary": _fix(prim_L, prim_C, h, bg, 6, -0.02), "secondary": _fix(0.50, 0.09, h2, bg, 4, -0.02),
        "accent": oklch(0.70, 0.12, 80) if accent_gold else oklch(0.66, 0.13, h3), "ink": oklch(0.24, 0.05, h),
    }
    p["on_primary"] = on_color(p["primary"])
    return p


# Colour names (Uzbek) with seed hues: (name, slug, primary hue, secondary hue, accent hue)
SEEDS: Dict[str, List[Tuple[str, str, float, float, float]]] = {
    "dark": [
        ("Yoqut", "ruby", 15, 340, 70), ("Zumrad", "emerald", 155, 195, 90), ("Kahrabo", "amber", 70, 40, 200),
        ("Binafsha", "violet", 300, 260, 340), ("Feruza", "turquoise", 195, 240, 150), ("Marjon", "coral", 35, 10, 190),
        ("Lojuvard", "lapis", 262, 220, 300), ("Lola", "tulip", 355, 20, 280), ("Oltin", "gold", 90, 60, 250),
        ("Yalpiz", "mint", 165, 130, 300), ("Pushti", "rose", 340, 300, 30),
    ],
    "light": [
        ("Osmon", "sky", 240, 210, 60), ("Zumrad", "emerald", 155, 185, 70), ("Anor", "pomegranate", 20, 350, 80),
        ("Lavanda", "lavender", 295, 260, 70), ("Feruza", "turquoise", 200, 170, 30), ("Kahrabo", "amber", 60, 35, 230),
        ("Olcha", "cherry", 5, 330, 90), ("Zaytun", "olive", 120, 90, 30), ("Lojuvard", "lapis", 265, 230, 80),
        ("Grafit", "graphite", 250, 220, 50), ("Shaftoli", "peach", 45, 20, 200),
    ],
    "cream": [
        ("Qahva", "coffee", 50, 70, 80), ("Lojuvard", "lapis", 262, 200, 80), ("Zumrad", "emerald", 160, 120, 80),
        ("Anor", "pomegranate", 18, 40, 80), ("Siyoh", "ink", 280, 250, 80), ("Feruza", "turquoise", 200, 170, 80),
        ("Olcha", "cherry", 0, 30, 80), ("Zaytun", "olive", 115, 80, 80), ("Kumush", "silver", 250, 220, 80),
        ("Binafsha", "violet", 305, 340, 80), ("Kashtan", "chestnut", 35, 60, 80),
    ],
}


def family_variants(family_id: str, recipe: str, kwargs: Dict, seeds_key: str, limit: int = 10) -> List[Dict]:
    fn = {"light": light_recipe, "dark": dark_recipe, "cream": cream_recipe}[recipe]
    out = []
    for name, slug, h, h2, h3 in SEEDS[seeds_key][:limit]:
        out.append({"color_name": name, "slug": slug, "palette": fn(h, h2, h3, **kwargs)})
    return out


def check_palette(p: Dict[str, str]) -> List[str]:
    """Returns contrast problems (empty list = palette is fine)."""
    problems = []
    if contrast(p["text"], p["bg"]) < 7:
        problems.append("text/bg")
    if contrast(p["text"], p["surface"]) < 7:
        problems.append("text/surface")
    if contrast(p["muted"], p["bg"]) < 4.2:
        problems.append("muted/bg")
    if contrast(p["primary"], p["bg"]) < 3:
        problems.append("primary/bg")
    if contrast(p["on_primary"], p["primary"]) < 4.2:
        problems.append("on_primary/primary")
    return problems
