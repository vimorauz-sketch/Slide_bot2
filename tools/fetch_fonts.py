"""
Downloads the font library users choose from (Google Fonts, SIL OFL / Apache) into assets/fonts_lib
and writes assets/fonts_lib/catalog.json.

    python tools/fetch_fonts.py            # fetch what is missing
    python tools/fetch_fonts.py --check    # only rebuild the catalog from the files already here

Only fonts that draw Uzbek Latin completely (o‘ g‘ ’ sh ch, latin-ext) are kept; "cyrillic" tells
whether Russian decks can use the font. Variable fonts are kept as they are (all weights in one
file); for static families the Regular and Bold files are taken.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1] / "assets" / "fonts_lib"
RAW = "https://raw.githubusercontent.com/google/fonts/main/{lic}/{dir}/{file}"

# (google/fonts directory, our category)
FONTS = [
    # ---- modern sans
    ("inter", "modern"), ("roboto", "modern"), ("opensans", "modern"), ("montserrat", "modern"),
    ("raleway", "modern"), ("nunito", "modern"), ("poppins", "modern"), ("rubik", "modern"),
    ("manrope", "modern"), ("worksans", "modern"), ("lato", "modern"), ("sourcesans3", "modern"),
    ("firasans", "modern"), ("ptsans", "modern"), ("notosans", "modern"), ("ibmplexsans", "modern"),
    ("mulish", "modern"), ("quicksand", "modern"), ("karla", "modern"), ("dmsans", "modern"),
    ("plusjakartasans", "modern"), ("outfit", "modern"), ("urbanist", "modern"), ("lexend", "modern"),
    ("onest", "modern"), ("golostext", "modern"), ("exo2", "modern"), ("ubuntu", "modern"),
    ("josefinsans", "modern"), ("barlow", "modern"), ("cabin", "modern"), ("titilliumweb", "modern"),
    ("arimo", "modern"), ("heebo", "modern"), ("sora", "modern"), ("spacegrotesk", "modern"),
    ("redhatdisplay", "modern"), ("figtree", "modern"), ("albertsans", "modern"), ("publicsans", "modern"),
    ("archivo", "modern"), ("robotocondensed", "modern"), ("oswald", "modern"), ("commissioner", "modern"),
    ("jost", "modern"), ("montserratalternates", "modern"), ("mplusrounded1c", "modern"), ("varelaround", "modern"),
    ("comfortaa", "modern"), ("alumnisans", "modern"), ("geologica", "modern"), ("wixmadefordisplay", "modern"),
    # ---- classic serif
    ("playfairdisplay", "classic"), ("lora", "classic"), ("merriweather", "classic"), ("ptserif", "classic"),
    ("sourceserif4", "classic"), ("cormorantgaramond", "classic"), ("ebgaramond", "classic"),
    ("librebaskerville", "classic"), ("crimsontext", "classic"), ("notoserif", "classic"), ("alegreya", "classic"),
    ("robotoslab", "classic"), ("bitter", "classic"), ("spectral", "classic"), ("prata", "classic"),
    ("oldstandardtt", "classic"), ("cormorant", "classic"), ("frankruhllibre", "classic"),
    ("dmserifdisplay", "classic"), ("zillaslab", "classic"), ("arvo", "classic"), ("literata", "classic"),
    ("vollkorn", "classic"), ("gelasio", "classic"), ("cardo", "classic"), ("ibmplexserif", "classic"),
    ("tinos", "classic"), ("rozhaone", "classic"), ("forum", "classic"), ("marcellus", "classic"),
    ("cinzel", "classic"), ("tenorsans", "classic"),
    # ---- display / bold
    ("bebasneue", "display"), ("anton", "display"), ("russoone", "display"), ("unbounded", "display"),
    ("righteous", "display"), ("lobster", "display"), ("alfaslabone", "display"), ("bungee", "display"),
    ("fredoka", "display"), ("blackopsone", "display"), ("rubikmonoone", "display"), ("tektur", "display"),
    ("orbitron", "display"), ("audiowide", "display"), ("monoton", "display"), ("yesevaone", "display"),
    ("abrilfatface", "display"), ("philosopher", "display"), ("poiretone", "display"), ("kellyslab", "display"),
    ("ruslandisplay", "display"), ("pressstart2p", "display"), ("archivoblack", "display"), ("dela-gothic-one", "display"),
    ("delagothicone", "display"), ("rampartone", "display"), ("bowlbyonesc", "display"), ("chakrapetch", "display"),
    ("rubikglitch", "display"), ("rubikbeastly", "display"), ("rubikmoonrocks", "display"), ("climatecrisis", "display"),
    ("staatliches", "display"), ("passionone", "display"), ("squadaone", "display"), ("bangers", "display"),
    # ---- handwriting
    ("caveat", "hand"), ("dancingscript", "hand"), ("greatvibes", "hand"), ("satisfy", "hand"),
    ("kaushanscript", "hand"), ("amaticsc", "hand"), ("marckscript", "hand"), ("shadowsintolight", "hand"),
    ("indieflower", "hand"), ("patrickhand", "hand"), ("gloriahallelujah", "hand"), ("sacramento", "hand"),
    ("permanentmarker", "hand"), ("neucha", "hand"), ("badscript", "hand"), ("pangolin", "hand"),
    ("comforter", "hand"), ("caveatbrush", "hand"), ("pacifico", "hand"), ("courgette", "hand"),
    ("cookie", "hand"), ("yellowtail", "hand"), ("kalam", "hand"), ("architectsdaughter", "hand"),
    ("handlee", "hand"), ("gochihand", "hand"), ("alexbrush", "hand"), ("allura", "hand"), ("parisienne", "hand"),
    ("tangerine", "hand"), ("pinyonscript", "hand"), ("greatvibes", "hand"), ("ruthie", "hand"),
    # ---- technical / mono
    ("jetbrainsmono", "tech"), ("firacode", "tech"), ("spacemono", "tech"), ("robotomono", "tech"),
    ("ibmplexmono", "tech"), ("sourcecodepro", "tech"), ("ubuntumono", "tech"), ("ptmono", "tech"),
    ("sharetechmono", "tech"), ("majormonodisplay", "tech"), ("vt323", "tech"), ("syncopate", "tech"),
    ("michroma", "tech"), ("saira", "tech"), ("rajdhani", "tech"), ("electrolize", "tech"),
]

CATEGORIES = {
    "modern": "Zamonaviy",
    "classic": "Klassik",
    "display": "Ko‘zga tashlanadigan",
    "hand": "Qo‘lyozma",
    "tech": "Texnik",
}

UZ_NEED = "AaBbDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvXxYyZz0123456789‘’.,:;!?()«»–—"
RU_NEED = "АаБбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя"
MAX_BYTES = 2_500_000


def _get(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def _metadata(dir_: str):
    for lic in ("ofl", "apache", "ufl"):
        raw = _get(RAW.format(lic=lic, dir=dir_, file="METADATA.pb"))
        if raw:
            return lic, raw.decode("utf-8", "replace")
    return None, None


def _pick_files(meta: str) -> list[dict]:
    fonts = []
    for block in re.findall(r"fonts\s*\{(.*?)\n\}", meta, flags=re.S):
        style = re.search(r'style:\s*"(\w+)"', block)
        weight = re.search(r"weight:\s*(\d+)", block)
        fname = re.search(r'filename:\s*"([^"]+)"', block)
        if fname and style and style.group(1) == "normal":
            fonts.append({"file": fname.group(1), "weight": int(weight.group(1)) if weight else 400})
    variable = [f for f in fonts if "[" in f["file"]]
    if variable:
        return variable[:1]
    out = []
    for want in (400, 700):
        best = min(fonts, key=lambda f: abs(f["weight"] - want), default=None)
        if best and best not in out:
            out.append(best)
    return out


def _cmap(path: Path) -> set:
    f = TTFont(path, lazy=True)
    return set(f.getBestCmap() or {})


def _family(path: Path) -> str:
    f = TTFont(path, lazy=True)
    names = f["name"]
    for nid in (16, 1):
        rec = names.getName(nid, 3, 1, 0x409) or names.getName(nid, 1, 0, 0)
        if rec:
            return str(rec)
    return path.stem


def _axes(path: Path):
    f = TTFont(path, lazy=True)
    if "fvar" not in f:
        return None
    for a in f["fvar"].axes:
        if a.axisTag == "wght":
            return int(a.minValue), int(a.maxValue)
    return None


def fetch(only_check: bool = False) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    seen = set()
    for dir_, cat in FONTS:
        if dir_ in seen:
            continue
        seen.add(dir_)
        dest = ROOT / dir_
        if only_check or (dest.exists() and any(dest.glob("*.ttf"))):
            continue
        lic, meta = _metadata(dir_)
        if not meta:
            print("  -- not found:", dir_)
            continue
        files = _pick_files(meta)
        dest.mkdir(exist_ok=True)
        for f in files:
            data = _get(RAW.format(lic=lic, dir=dir_, file=f["file"]))
            if not data or len(data) > MAX_BYTES:
                print("  -- skipped file:", dir_, f["file"], len(data or b""))
                continue
            name = re.sub(r"[\[\],]", "_", f["file"]).replace("__", "_")
            (dest / name).write_bytes(data)
        if not any(dest.glob("*.ttf")):
            dest.rmdir()
        print("ok", dir_)

    catalog = []
    for dir_, cat in FONTS:
        dest = ROOT / dir_
        files = sorted(dest.glob("*.ttf")) if dest.exists() else []
        if not files or any(e["id"] == dir_ for e in catalog):
            continue
        cmap = set().union(*(_cmap(p) for p in files))
        if not all(ord(c) in cmap for c in UZ_NEED):
            missing = "".join(c for c in UZ_NEED if ord(c) not in cmap)
            print("  -- no Uzbek Latin, removed:", dir_, missing)
            for p in files:
                p.unlink()
            dest.rmdir()
            continue
        entry = {"id": dir_, "name": _family(files[0]), "category": cat,
                 "cyrillic": all(ord(c) in cmap for c in RU_NEED), "files": []}
        for p in files:
            ax = _axes(p)
            if ax:
                entry["files"].append({"file": p.name, "weight": f"{ax[0]} {ax[1]}", "variable": True})
            else:
                w = TTFont(p, lazy=True)["OS/2"].usWeightClass
                entry["files"].append({"file": p.name, "weight": str(w), "variable": False})
        catalog.append(entry)
    (ROOT / "catalog.json").write_text(json.dumps({"categories": CATEGORIES, "fonts": catalog},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(catalog)} fonts in the catalog")


if __name__ == "__main__":
    fetch(only_check="--check" in sys.argv)
