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


# ---------------------------------------------------------------------- the library users choose from
# assets/fonts_lib (tools/fetch_fonts.py): full TTF files, so the same font can also be given to
# the customer for the editable PowerPoint file. Ids are "g:<google fonts directory>".
_LIB_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts_lib"
LIB_PREFIX = "g:"
_GENERIC = {"classic": "Georgia, serif", "hand": "cursive", "tech": "monospace"}


@lru_cache(maxsize=1)
def _library() -> dict:
    try:
        with open(_LIB_DIR / "catalog.json", encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return {"categories": {}, "fonts": []}
    for e in data["fonts"]:
        e["key"] = LIB_PREFIX + e["id"]
    return data


def library_fonts() -> list:
    """[{key, id, name, category, cyrillic, files}] in catalog order (the index is used in buttons)."""
    return _library()["fonts"]


def library_categories() -> dict:
    return _library()["categories"]


def library_font(font_id: str):
    if not str(font_id or "").startswith(LIB_PREFIX):
        return None
    fid = font_id[len(LIB_PREFIX):]
    return next((e for e in library_fonts() if e["id"] == fid), None)


def is_library_font(font_id: str) -> bool:
    return library_font(font_id) is not None


def family_name(font_id: str) -> str:
    e = library_font(font_id)
    if e:
        return e["name"]
    return FAMILY_NAMES.get(font_id, "")


def supports_cyrillic(font_id: str) -> bool:
    e = library_font(font_id)
    return True if e is None else bool(e.get("cyrillic"))


def cyrillic_fallback(font_id: str) -> str:
    """A Russian deck cannot use a Latin-only font: the first Cyrillic font of the same kind."""
    e = library_font(font_id)
    if e is None or e.get("cyrillic"):
        return font_id
    same = [f for f in library_fonts() if f["category"] == e["category"] and f.get("cyrillic")]
    return (same or [f for f in library_fonts() if f.get("cyrillic")] or [e])[0]["key"]


def font_paths(font_id: str) -> list:
    e = library_font(font_id)
    return [os.fspath(_LIB_DIR / e["id"] / f["file"]) for f in e["files"]] if e else []


def _library_face_css(e: dict) -> str:
    rules = []
    for f in e["files"]:
        path = (_LIB_DIR / e["id"] / f["file"]).as_uri()
        rules.append('@font-face{font-family:"%s";font-style:normal;font-weight:%s;font-display:block;'
                     'src:url("%s") format("truetype");}' % (e["name"], f["weight"], path))
    return "\n".join(rules)


_css_family_bundled = css_family
_font_face_css_bundled = font_face_css


def css_family(font_id: str) -> str:  # noqa: F811 - extends the bundled-font version above
    e = library_font(font_id)
    if e:
        return f'"{e["name"]}", {_GENERIC.get(e["category"], "Arial, sans-serif")}'
    return _css_family_bundled(font_id)


def font_face_css(font_ids: Iterable[str]) -> str:  # noqa: F811
    ids = list(dict.fromkeys(font_ids))
    lib = [library_font(i) for i in ids]
    rules = [_library_face_css(e) for e in lib if e]
    rules.append(_font_face_css_bundled([i for i, e in zip(ids, lib) if not e]))
    return "\n".join(r for r in rules if r)


# ---------------------------------------------------------------------- fonts for the customer
def _static_instance(src: str, weight: int, family: str, out_path: str) -> str:
    """A static Regular/Bold TTF named so that Windows/macOS group them as one family: PowerPoint's
    Bold button then uses the real bold instead of a smeared imitation."""
    from fontTools.ttLib import TTFont

    font = TTFont(src)
    if "fvar" in font:
        from fontTools.varLib import instancer
        axes = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
        if "wght" in axes:
            w = next(a for a in font["fvar"].axes if a.axisTag == "wght")
            axes["wght"] = max(w.minValue, min(w.maxValue, weight))
        font = instancer.instantiateVariableFont(font, axes)
    style = "Bold" if weight >= 600 else "Regular"
    ps = (family.replace(" ", "") + "-" + style)[:60]
    name = font["name"]
    for rec in list(name.names):
        if rec.nameID in (16, 17, 21, 22, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, value in ((1, family), (2, style), (3, f"SlideLab;{ps}"), (4, f"{family} {style}".replace(" Regular", "")),
                       (6, ps)):
        name.setName(value, nid, 3, 1, 0x409)
        name.setName(value, nid, 1, 0, 0)
    os2 = font["OS/2"]
    os2.usWeightClass = 700 if style == "Bold" else 400
    sel = os2.fsSelection & ~(1 | 32 | 64)  # italic, bold, regular bits
    os2.fsSelection = sel | (32 if style == "Bold" else 64)
    font["head"].macStyle = 1 if style == "Bold" else 0
    font.save(out_path)
    return out_path


def customer_font_files(font_ids: Iterable[str], out_dir: str) -> list:
    """Regular and Bold TTF files of the chosen library fonts (for installing on the computer)."""
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for fid in dict.fromkeys(font_ids):
        e = library_font(fid)
        if not e:
            continue
        files = e["files"]
        for weight in (400, 700):
            if files[0].get("variable"):
                src = _LIB_DIR / e["id"] / files[0]["file"]
            else:
                src = _LIB_DIR / e["id"] / min(files, key=lambda f: abs(int(f["weight"]) - weight))["file"]
            dst = os.path.join(out_dir, f"{e['name'].replace(' ', '')}-{'Bold' if weight == 700 else 'Regular'}.ttf")
            if not os.path.exists(dst):
                try:
                    _static_instance(os.fspath(src), weight, e["name"], dst)
                except Exception:  # noqa: BLE001 - the original file still installs fine
                    import shutil
                    shutil.copyfile(src, dst)
            out.append(dst)
    return list(dict.fromkeys(out))
