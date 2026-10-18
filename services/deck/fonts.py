"""@font-face CSS for the bundled fonts (assets/fonts, from Fontsource, SIL OFL)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Fontsource id -> CSS family name.
FAMILY_NAMES = {
    "tektur": "Tektur", "inter": "Inter", "source-serif-4": "Source Serif 4", "source-sans-3": "Source Sans 3",
    "unbounded": "Unbounded", "onest": "Onest", "playfair-display": "Playfair Display", "lora": "Lora",
    "comfortaa": "Comfortaa", "nunito": "Nunito", "montserrat": "Montserrat", "ibm-plex-sans": "IBM Plex Sans",
    "oswald": "Oswald", "fira-sans": "Fira Sans", "merriweather": "Merriweather",
    "cormorant-garamond": "Cormorant Garamond", "alegreya": "Alegreya", "exo-2": "Exo 2", "raleway": "Raleway",
    "caveat": "Caveat", "yeseva-one": "Yeseva One", "rubik": "Rubik", "manrope": "Manrope",
    "jetbrains-mono": "JetBrains Mono", "golos-text": "Golos Text", "pt-serif": "PT Serif", "pt-sans": "PT Sans",
    "russo-one": "Russo One",
}

SERIF = {"source-serif-4", "playfair-display", "lora", "merriweather", "cormorant-garamond", "alegreya", "yeseva-one", "pt-serif"}


@lru_cache(maxsize=1)
def _manifest() -> dict:
    with open(_FONTS_DIR / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def css_family(font_id: str) -> str:
    name = FAMILY_NAMES.get(font_id, "Inter")
    generic = "Georgia, serif" if font_id in SERIF else "Arial, sans-serif"
    return f'"{name}", {generic}'


def font_face_css(font_ids: Iterable[str]) -> str:
    man = _manifest()
    rules = []
    for fid in dict.fromkeys(font_ids):
        entry = man.get(fid)
        if not entry:
            continue
        name = FAMILY_NAMES.get(fid, fid)
        for f in entry["files"]:
            path = (_FONTS_DIR / fid / f["file"]).as_uri()
            rng = entry["ranges"].get(f["subset"])
            rules.append(
                "@font-face{"
                f'font-family:"{name}";font-style:{f["style"]};font-weight:{f["weight"]};font-display:block;'
                f'src:url("{path}") format("woff2");' + (f"unicode-range:{rng};" if rng else "") + "}"
            )
    return "\n".join(rules)


def fonts_dir() -> str:
    return os.fspath(_FONTS_DIR)
