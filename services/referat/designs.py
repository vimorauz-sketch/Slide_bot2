"""
Referat templates: a title-page layout, a heading style, a colour palette and a font pair.

Inner pages always keep the academic standard teachers expect (A4, 14 pt body text, 1.5 line
spacing, margins 3 / 1.5 / 2 / 2 cm, first-line indent, page numbers at the bottom); templates
change the title page, the headings, the running header and the colours.
"""
from __future__ import annotations

from typing import Dict, List

PALETTES: Dict[str, Dict[str, str]] = {
    # ink = body text, accent = main colour, accent2 = second colour, soft = light tint
    "navy":     {"name": "To‘q ko‘k", "ink": "#1B2430", "accent": "#1E3A8A", "accent2": "#3B82F6", "soft": "#E8EEFB"},
    "burgundy": {"name": "Bordo", "ink": "#2A1A1F", "accent": "#7F1D1D", "accent2": "#B45309", "soft": "#F8ECEC"},
    "emerald":  {"name": "Zumrad", "ink": "#13241D", "accent": "#065F46", "accent2": "#10B981", "soft": "#E6F4EE"},
    "black":    {"name": "Klassik qora", "ink": "#111111", "accent": "#111111", "accent2": "#6B6B6B", "soft": "#F1F1F1"},
    "teal":     {"name": "Moviy-yashil", "ink": "#102A2E", "accent": "#0F766E", "accent2": "#14B8A6", "soft": "#E3F4F2"},
    "purple":   {"name": "Binafsha", "ink": "#1F1630", "accent": "#5B21B6", "accent2": "#A78BFA", "soft": "#EFEAFB"},
    "gold":     {"name": "Oltin", "ink": "#2B2416", "accent": "#92400E", "accent2": "#D4A017", "soft": "#FBF3E2"},
    "crimson":  {"name": "Qirmizi", "ink": "#22151A", "accent": "#BE123C", "accent2": "#FB7185", "soft": "#FDECEF"},
    "sky":      {"name": "Osmon", "ink": "#0F2233", "accent": "#0369A1", "accent2": "#38BDF8", "soft": "#E5F3FB"},
    "olive":    {"name": "Zaytun", "ink": "#22251A", "accent": "#4D7C0F", "accent2": "#A3B18A", "soft": "#EEF2E3"},
    "coral":    {"name": "Marjon", "ink": "#2A1B17", "accent": "#C2410C", "accent2": "#FB923C", "soft": "#FDEEE5"},
    "slate":    {"name": "Grafit", "ink": "#1E2430", "accent": "#334155", "accent2": "#94A3B8", "soft": "#EEF1F5"},
    "lazurit":  {"name": "Lazurit va oltin", "ink": "#14213D", "accent": "#1D4ED8", "accent2": "#F59E0B", "soft": "#E9EEFB"},
    "rose":     {"name": "Pushti", "ink": "#2A1621", "accent": "#BE185D", "accent2": "#F9A8D4", "soft": "#FCEAF3"},
    "brown":    {"name": "Jigarrang", "ink": "#2B2018", "accent": "#78350F", "accent2": "#C08A52", "soft": "#F5EDE3"},
}

COVERS = {
    "frame": "Klassik ramka",
    "double": "Qo‘sh chiziqli ramka",
    "ornament": "Milliy naqsh burchaklari",
    "band": "Yon rangli tasma",
    "header": "Yuqori rangli blok",
    "corners": "Geometrik burchaklar",
    "minimal": "Minimal",
    "wave": "To‘lqinlar",
    "photo": "Muqovada rasm",
    "dots": "Nuqtali ramka",
    "diagonal": "Qiya tasma",
    "emblem": "Gerb-medalyon",
    "split": "Ikki rangli sahifa",
    "arch": "Ravoq",
}

HEADINGS = {
    "bar": "Yon chiziqli",
    "underline": "Tagiga chizilgan",
    "caps": "Markazda, bosh harflar",
    "badge": "Raqamli doiracha",
    "box": "Rangli fon",
    "rule": "Ikki tomonida chiziq",
}

# (name, cover, heading, palette, title font, body font)
_TEMPLATES = [
    ("Akademik", "frame", "caps", "black", "g:tinos", "g:tinos"),
    ("Universitet", "double", "caps", "navy", "g:ptserif", "g:ptserif"),
    ("Milliy naqsh", "ornament", "rule", "lazurit", "g:cormorantgaramond", "g:ptserif"),
    ("Zamonaviy ko‘k", "band", "bar", "navy", "g:montserrat", "g:opensans"),
    ("Ilmiy", "header", "underline", "slate", "g:sourceserif4", "g:sourceserif4"),
    ("Geometriya", "corners", "badge", "teal", "g:inter", "g:inter"),
    ("Minimal", "minimal", "bar", "black", "g:inter", "g:sourceserif4"),
    ("Dengiz", "wave", "box", "sky", "g:raleway", "g:lato"),
    ("Tabiat surati", "photo", "bar", "emerald", "g:playfairdisplay", "g:sourcesans3"),
    ("Nuqtalar", "dots", "badge", "purple", "g:jost", "g:ibmplexsans"),
    ("Dinamik", "diagonal", "box", "coral", "g:oswald", "g:ptsans"),
    ("Oliygoh", "emblem", "caps", "burgundy", "g:cinzel", "g:cardo"),
    ("Ikki rang", "split", "bar", "lazurit", "g:montserrat", "g:notosans"),
    ("Sharq ravog‘i", "arch", "rule", "gold", "g:prata", "g:ptserif"),
    ("Bordo klassik", "double", "rule", "burgundy", "g:playfairdisplay", "g:lora"),
    ("Zumrad naqsh", "ornament", "caps", "emerald", "g:cormorantgaramond", "g:ebgaramond"),
    ("Biznes", "header", "box", "navy", "g:manrope", "g:notosans"),
    ("Grafit", "band", "underline", "slate", "g:rubik", "g:rubik"),
    ("Marjon", "corners", "bar", "coral", "g:raleway", "g:lato"),
    ("Toza varaq", "minimal", "underline", "navy", "g:lora", "g:lora"),
    ("Yashil to‘lqin", "wave", "badge", "emerald", "g:exo2", "g:roboto"),
    ("Shahar surati", "photo", "box", "slate", "g:oswald", "g:roboto"),
    ("Pushti nuqta", "dots", "rule", "rose", "g:playfairdisplay", "g:lato"),
    ("Qirmizi tasma", "diagonal", "bar", "crimson", "g:montserrat", "g:opensans"),
    ("Oltin medal", "emblem", "rule", "gold", "g:cinzel", "g:ebgaramond"),
    ("Kontrast", "split", "box", "black", "g:bebasneue", "g:roboto"),
    ("Moviy ravoq", "arch", "caps", "teal", "g:tenorsans", "g:ptsans"),
    ("Klassik ko‘k", "frame", "underline", "navy", "g:tinos", "g:tinos"),
    ("Adabiyot", "frame", "rule", "brown", "g:ebgaramond", "g:ebgaramond"),
    ("Tarix", "ornament", "rule", "brown", "g:cinzel", "g:ptserif"),
    ("Texnika", "header", "badge", "sky", "g:exo2", "g:ibmplexsans"),
    ("Binafsha tasma", "band", "box", "purple", "g:unbounded", "g:golostext"),
    ("Tibbiyot", "corners", "underline", "teal", "g:sourcesans3", "g:sourceserif4"),
    ("Iqtisod", "minimal", "badge", "slate", "g:manrope", "g:inter"),
    ("Osmon to‘lqini", "wave", "rule", "sky", "g:lora", "g:lora"),
    ("Kitob surati", "photo", "rule", "brown", "g:cormorantgaramond", "g:ptserif"),
    ("Zaytun", "dots", "underline", "olive", "g:literata", "g:literata"),
    ("Sport", "diagonal", "badge", "navy", "g:oswald", "g:roboto"),
    ("Akademiya", "emblem", "underline", "navy", "g:prata", "g:ptserif"),
    ("Yashil-oq", "split", "underline", "emerald", "g:raleway", "g:lato"),
    ("Oltin ravoq", "arch", "rule", "burgundy", "g:playfairdisplay", "g:ptserif"),
    ("Ekologiya", "corners", "box", "olive", "g:jost", "g:notosans"),
    ("Kimyo", "header", "badge", "crimson", "g:inter", "g:inter"),
    ("Pedagogika", "frame", "box", "rose", "g:lora", "g:lora"),
    ("Lazurit", "double", "badge", "lazurit", "g:montserrat", "g:ptserif"),
    ("Qadimiy", "ornament", "underline", "gold", "g:yesevaone", "g:ptserif"),
    ("Marjon tasma", "band", "rule", "coral", "g:playfairdisplay", "g:sourcesans3"),
    ("Monoxrom", "minimal", "caps", "black", "g:tenorsans", "g:ptserif"),
    ("Informatika", "dots", "box", "teal", "g:sora", "g:firasans"),
    ("Tantanali", "emblem", "box", "purple", "g:dmserifdisplay", "g:sourceserif4"),
]


def _build() -> List[Dict]:
    out = []
    for n, (name, cover, heading, pal, tf, bf) in enumerate(_TEMPLATES, start=1):
        out.append({"id": f"r{n:02d}", "code": n, "name": name, "cover": cover, "heading": heading,
                    "palette_id": pal, "palette": dict(PALETTES[pal]), "fonts": {"title": tf, "body": bf}})
    return out


TEMPLATES = _build()
BY_ID = {t["id"]: t for t in TEMPLATES}
DEFAULT = "r01"


def get(template_id: str) -> Dict:
    return dict(BY_ID.get(str(template_id), BY_ID[DEFAULT]))


def by_number(n) -> Dict:
    try:
        return get(f"r{int(n):02d}")
    except (TypeError, ValueError):
        return get(DEFAULT)
