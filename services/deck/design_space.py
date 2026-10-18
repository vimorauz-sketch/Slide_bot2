"""
Design space for the generated templates.

A template is one choice per dimension (art style, cover composition, mode, font pair, background,
cards, headings, icons, bullets, picture frame, decoration, corners, statement slides). The
generator (`generate()`) walks the art styles round-robin and, for every template, picks the
least-used compatible option in each dimension, so the 180 results spread over the whole space and
no two templates share their art style together with their cover composition or font pair.
The output is written to themes/templates.json by scripts/generate_templates.py.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List

from services.deck import palettes

# ------------------------------------------------------------------ art styles
# art: (allowed modes, font moods, categories, Uzbek description, names)
ARTS: Dict[str, dict] = {
    "circuit": dict(modes=["dark", "vivid"], fonts=["tech", "modern", "bold"], cats=["tech"], uz="neon sxema chiziqlari",
                    names=["Circuit Board", "Data Stream", "Silicon", "Neural Net", "Mainframe", "Quantum Grid"]),
    "academic": dict(modes=["light", "cream"], fonts=["academic", "modern", "elegant"], cats=["education"], uz="ilmiy orbita chizmasi",
                     names=["Lecture Hall", "Thesis", "Scholar", "Atlas", "Campus", "Seminar"]),
    "aurora": dict(modes=["dark", "vivid"], fonts=["modern", "bold", "elegant"], cats=["creative", "business"], uz="aurora gradientlari",
                   names=["Northern Lights", "Polar Glow", "Nebula Mist", "Velvet Sky", "Prism Haze", "Twilight"]),
    "editorial": dict(modes=["light", "cream"], fonts=["elegant", "academic", "display"], cats=["culture"], uz="jurnal kompozitsiyasi",
                      names=["Gazette", "Folio", "Monocle", "Salon", "Chronicle", "Vernissage"]),
    "botanical": dict(modes=["light", "cream"], fonts=["friendly", "elegant", "modern"], cats=["nature"], uz="botanik barglar",
                      names=["Herbarium", "Fern", "Greenhouse", "Meadow", "Eucalyptus", "Orchard"]),
    "corporate": dict(modes=["light", "cream"], fonts=["business", "modern", "academic"], cats=["business"], uz="o‘sish grafigi",
                      names=["Boardroom", "Quarterly", "Summit", "Ledger", "Keynote", "Venture"]),
    "neon": dict(modes=["dark"], fonts=["bold", "tech", "modern"], cats=["creative"], uz="neon lentalar",
                 names=["Neon Night", "Synthwave", "Arcade", "Cyber Pop", "Laser", "Electric"]),
    "medical": dict(modes=["light"], fonts=["academic", "modern", "business"], cats=["nature", "education"], uz="puls va to‘lqinlar",
                    names=["Clinic", "Pulse", "Vitals", "Healthline", "Lab Coat", "Wellness"]),
    "ikat": dict(modes=["cream", "vivid"], fonts=["elegant", "culture", "display"], cats=["culture"], uz="atlas-ikat naqshi",
                 names=["Adras", "Suzani", "Khiva", "Bukhara", "Samarkand Silk", "Atlas Silk"]),
    "glossy3d": dict(modes=["dark", "vivid"], fonts=["tech", "modern", "bold"], cats=["tech"], uz="yaltiroq 3D shakllar",
                     names=["Chrome", "Liquid Metal", "Hologram", "Glass Orb", "Gloss", "Future Form"]),
    "swiss": dict(modes=["light", "cream"], fonts=["modern", "bold", "business"], cats=["minimal", "business"], uz="Shveytsariya poster geometriyasi",
                  names=["Zurich", "Grid System", "Basel", "Modernist", "Poster School", "Form Follows"]),
    "blobs": dict(modes=["light", "cream"], fonts=["friendly", "hand", "bold"], cats=["education", "creative"], uz="yumaloq pastel dog‘lar",
                  names=["Bubblegum", "Jelly", "Lava Lamp", "Marshmallow", "Pebble", "Candy Pop"]),
    "chalk": dict(modes=["dark", "vivid"], fonts=["hand", "friendly"], cats=["education"], uz="bo‘r chizgilari",
                  names=["Classroom", "Blackboard", "Chalk Talk", "Math Club", "Lesson Plan", "Recess"]),
    "doodle": dict(modes=["light", "cream"], fonts=["hand", "friendly"], cats=["education"], uz="daftar va stikerlar",
                   names=["Sketchbook", "Scribble", "Margin Notes", "Doodle Pad", "Homework", "Notepad"]),
    "blueprint": dict(modes=["dark", "vivid"], fonts=["tech", "modern", "business"], cats=["tech"], uz="texnik chizma",
                      names=["Draftsman", "Schematic", "Engineer", "Prototype", "Workshop", "Technical"]),
    "magazine": dict(modes=["light", "cream", "dark"], fonts=["display", "bold", "elegant"], cats=["creative", "culture"], uz="jurnal rang bloklari",
                     names=["Cover Story", "Headline", "Tabloid", "Front Page", "Spread", "Masthead"]),
    "mesh": dict(modes=["light", "dark"], fonts=["modern", "bold", "elegant"], cats=["business", "tech"], uz="yumshoq gradient tuman",
                 names=["Gradient Flow", "Soft Mesh", "Holo Mist", "Pastel Fog", "Iris", "Opal"]),
    "retro": dict(modes=["cream", "light"], fonts=["friendly", "bold", "display"], cats=["creative", "culture"], uz="70-yillar quyosh chiziqlari",
                  names=["Seventies", "Disco Sun", "Vinyl", "Roadtrip", "Groovy", "Jukebox"]),
    "ink": dict(modes=["cream", "light"], fonts=["elegant", "academic", "culture"], cats=["culture", "minimal"], uz="siyoh va tog‘lar",
                names=["Sumi", "Haiku", "Brushstroke", "Ink Wash", "Calligraphy", "Zen Garden"]),
    "cosmos": dict(modes=["dark", "vivid"], fonts=["tech", "bold", "modern"], cats=["tech", "education"], uz="sayyoralar va orbitalar",
                   names=["Galaxy", "Orbit", "Stardust", "Supernova", "Apollo", "Deep Space"]),
    "bauhaus": dict(modes=["light", "cream", "dark"], fonts=["bold", "modern", "display"], cats=["creative", "minimal"], uz="Bauhaus geometrik plitkalari",
                    names=["Bauhaus", "Dessau", "Weimar", "Primary Forms", "Geometry Lab", "Constructivist"]),
    "stripes": dict(modes=["light", "cream", "vivid"], fonts=["bold", "modern", "business"], cats=["business", "creative"], uz="qiya rangli chiziqlar",
                    names=["Racing Stripe", "Candy Stripe", "Diagonal", "Momentum", "Velocity", "Signal"]),
    "rings": dict(modes=["light", "cream", "dark", "vivid"], fonts=["modern", "elegant", "bold"], cats=["business", "minimal"], uz="konsentrik halqalar",
                  names=["Ripple", "Echo", "Sonar", "Target", "Resonance", "Halo"]),
    "waves": dict(modes=["light", "dark", "vivid"], fonts=["friendly", "modern", "elegant"], cats=["nature"], uz="qatlamli to‘lqinlar",
                  names=["Tide", "Ocean Breeze", "Lagoon", "Surf", "Horizon", "Dune Sea"]),
    "lowpoly": dict(modes=["light", "dark", "vivid"], fonts=["tech", "modern", "bold"], cats=["tech", "creative"], uz="ko‘pburchakli kristall",
                    names=["Polygon", "Crystal", "Facet", "Origami", "Low Poly", "Mosaic"]),
    "halftone": dict(modes=["light", "cream", "vivid"], fonts=["bold", "display", "friendly"], cats=["creative"], uz="pop-art nuqtalari",
                     names=["Pop Art", "Comic Dot", "Newsprint", "Ben-Day", "Riso", "Screenprint"]),
    "confetti": dict(modes=["light", "cream"], fonts=["friendly", "hand", "bold"], cats=["education", "creative"], uz="bayramona konfetti",
                     names=["Party", "Fiesta", "Celebration", "Carnival", "Sprinkles", "Festival"]),
    "isometric": dict(modes=["light", "dark"], fonts=["tech", "business", "modern"], cats=["tech", "business"], uz="izometrik kublar",
                      names=["Isometric", "Blocks", "Pixel City", "Cube World", "Building Blocks", "Voxel"]),
    "sunburst": dict(modes=["cream", "vivid", "light"], fonts=["display", "bold", "friendly"], cats=["creative", "culture"], uz="quyosh nurlari",
                     names=["Sunburst", "Sunrise", "Solar", "Daybreak", "Golden Hour", "Radiance"]),
    "papercut": dict(modes=["light", "cream", "dark"], fonts=["friendly", "modern", "elegant"], cats=["nature", "creative"], uz="qog‘oz qatlamlari",
                     names=["Paper Craft", "Kirigami", "Layered Hills", "Cut Out", "Paper Mountains", "Collage"]),
    "topo": dict(modes=["light", "cream", "dark"], fonts=["academic", "modern", "tech"], cats=["education", "nature"], uz="topografik chiziqlar",
                 names=["Topography", "Contour", "Cartographer", "Terrain", "Expedition", "Altitude"]),
}

# Art styles whose SVG filters make vector PDF export slow -> raster PDF.
HEAVY_ART = {"circuit", "aurora", "glossy3d", "chalk", "ink", "cosmos", "mesh", "neon", "blobs"}

# ------------------------------------------------------------------ fonts
# (title, body, mood, type settings)
FONT_PAIRS = [
    ("inter", "inter", "modern", dict(w=800, tr="-0.04em", lh=1.0)),
    ("manrope", "inter", "modern", dict(w=800, tr="-0.035em")),
    ("onest", "onest", "modern", dict(w=800, tr="-0.03em")),
    ("golos-text", "golos-text", "modern", dict(w=800, tr="-0.03em")),
    ("raleway", "raleway", "modern", dict(w=800, tr="-0.02em")),
    ("unbounded", "onest", "bold", dict(w=700, tr="-0.02em", scale=.88)),
    ("oswald", "fira-sans", "bold", dict(w=600, tf="uppercase", tr="0.005em", scale=1.04)),
    ("montserrat", "ibm-plex-sans", "business", dict(w=800, tr="-0.02em")),
    ("fira-sans", "fira-sans", "business", dict(w=800, tr="-0.02em")),
    ("ibm-plex-sans", "ibm-plex-sans", "tech", dict(w=700, tr="-0.02em")),
    ("russo-one", "golos-text", "tech", dict(w=400, tf="uppercase", tr="0.02em", scale=.86)),
    ("tektur", "inter", "tech", dict(w=700, tr="-0.01em")),
    ("exo-2", "raleway", "tech", dict(w=800, tr="-0.02em")),
    ("jetbrains-mono", "inter", "tech", dict(w=700, tr="-0.04em", scale=.86)),
    ("rubik", "rubik", "friendly", dict(w=800, tr="-0.02em")),
    ("nunito", "nunito", "friendly", dict(w=800, tr="-0.01em")),
    ("comfortaa", "nunito", "friendly", dict(w=700, tr="-0.02em", scale=.94)),
    ("caveat", "nunito", "hand", dict(w=700, tr="0", scale=1.3, lh=.98)),
    ("caveat", "pt-sans", "hand", dict(w=600, tr="0", scale=1.3, lh=.98)),
    ("playfair-display", "lora", "elegant", dict(w=700, tr="-0.01em")),
    ("playfair-display", "source-sans-3", "elegant", dict(w=400, it=True, tr="-0.01em", scale=1.06)),
    ("cormorant-garamond", "alegreya", "elegant", dict(w=600, tr="0", scale=1.14, lh=1.0)),
    ("lora", "inter", "elegant", dict(w=700, tr="-0.01em")),
    ("source-serif-4", "source-sans-3", "academic", dict(w=600, tr="-0.01em")),
    ("merriweather", "source-sans-3", "academic", dict(w=800, tr="-0.01em", scale=.9)),
    ("pt-serif", "pt-sans", "academic", dict(w=700, tr="0")),
    ("alegreya", "source-sans-3", "culture", dict(w=800, tr="-0.01em")),
    ("cormorant-garamond", "source-sans-3", "culture", dict(w=700, tr="0", scale=1.12)),
    ("yeseva-one", "golos-text", "display", dict(w=400, tr="-0.01em")),
    ("playfair-display", "inter", "display", dict(w=800, tr="-0.03em")),
    ("unbounded", "inter", "display", dict(w=800, tr="-0.04em", scale=.84)),
]
_SERIF_BODY = {"lora", "alegreya", "pt-serif", "source-serif-4", "merriweather"}
_PPTX_SERIF_TITLES = {"playfair-display", "cormorant-garamond", "lora", "source-serif-4", "merriweather", "pt-serif", "alegreya", "yeseva-one"}

# ------------------------------------------------------------------ layout dimensions
COVERS = ["split", "split-left", "full", "center", "card", "band", "circle", "arch", "frame", "diagonal", "bottom", "poster"]
MODES = ["light", "cream", "dark", "vivid"]
DIMS = {
    "bg": ["plain", "dots", "grid", "lines", "diag", "blobs", "glow", "band", "corner", "topbar", "wave", "frame", "tint", "paper", "split"],
    "card": ["soft", "outline", "tint", "topbar", "leftbar", "sticker", "glass", "numbered", "minimal", "solid", "elevated", "dashed", "ticket"],
    "head": ["plain", "bar", "underline", "pill", "number", "caps", "marker", "slash", "center", "tag"],
    "icon": ["tint", "circle", "outline", "solid", "square", "hex", "plain", "ring", "gradient"],
    "bul": ["dot", "square", "dash", "diamond", "ring", "arrow", "check", "bar"],
    "fr": ["bleed", "inset", "round", "circle", "arch", "blob", "tilt", "diag", "offset", "window", "hex"],
    "dec": ["none", "tri", "bignum", "strip", "tricolor", "dots", "circles", "plus", "tab", "brackets", "pagebadge", "leaf"],
    "rad": ["sharp", "soft", "round", "pill"],
    "hl": ["overlay", "solid", "tint", "gradient"],
}

UZ = {
    "mode": {"light": "Yorug‘ fon", "cream": "Iliq qog‘oz fon", "dark": "Qorong‘i fon", "vivid": "To‘yingan rangli fon"},
    "cover": {"split": "o‘ngda katta rasm", "split-left": "chapda katta rasm", "full": "to‘liq ekranli muqova", "center": "markazdagi sarlavha",
              "card": "rasm ustidagi karta", "band": "rangli muqova bloki", "circle": "aylana rasm", "arch": "ravoq shaklidagi rasm",
              "frame": "ramkali rasm", "diagonal": "qiya kesilgan rasm", "bottom": "tepada rasm, pastda matn", "poster": "ulkan poster sarlavha"},
    "card": {"soft": "yumshoq soyali kartalar", "outline": "konturli kartalar", "tint": "rangli kartalar", "topbar": "rangli chiziqli kartalar",
             "leftbar": "yon chiziqli kartalar", "sticker": "stiker kartalar", "glass": "shisha kartalar", "numbered": "raqamli kartalar",
             "minimal": "minimal bloklar", "solid": "to‘q rangli kartalar", "elevated": "ko‘tarilgan kartalar", "dashed": "punktir kartalar",
             "ticket": "chipta shaklidagi kartalar"},
}

MOOD_TONE = {
    "tech": "Aniq va texnik: qisqa jumlalar, raqamlar va atamalar.",
    "education": "Tushunarli va izchil: ta’riflar, misollar va bosqichlar.",
    "nature": "Iliq va jonli: tabiatga oid misollar, ravon tushuntirish.",
    "business": "Ishbilarmon: aniq xulosalar, raqamlar, foyda va natijalar.",
    "creative": "Ijodiy va yorqin: qisqa, ta’sirli iboralar.",
    "culture": "Nafis va hikoyaviy: tarixiy kontekst, iqtiboslar.",
    "minimal": "Lo‘nda: har slaydda bitta asosiy fikr.",
}

SEED_KEY = {"light": "light", "cream": "cream", "dark": "dark", "vivid": "dark"}
COLORS_PER_TEMPLATE = 10


def recipe_for(mode: str, rnd: random.Random) -> dict:
    if mode == "light":
        return {"type": "light", "kwargs": {"tint": round(rnd.uniform(.004, .03), 3), "bg_L": round(rnd.uniform(.975, .995), 3),
                                            "prim_L": round(rnd.uniform(.44, .54), 2), "prim_C": round(rnd.uniform(.13, .19), 2)}}
    if mode == "cream":
        return {"type": "cream", "kwargs": {"prim_L": round(rnd.uniform(.33, .48), 2), "prim_C": round(rnd.uniform(.09, .16), 2),
                                            "bg_h": rnd.choice([70, 75, 80, 85, 90]), "bg_C": round(rnd.uniform(.018, .04), 3),
                                            "accent_gold": rnd.random() < .5}}
    if mode == "dark":
        return {"type": "dark", "kwargs": {"bg_L": round(rnd.uniform(.13, .19), 2), "bg_C": round(rnd.uniform(.02, .06), 2),
                                           "prim_L": round(rnd.uniform(.78, .88), 2), "prim_C": round(rnd.uniform(.13, .18), 2)}}
    return {"type": "dark", "kwargs": {"bg_L": round(rnd.uniform(.30, .35), 2), "bg_C": round(rnd.uniform(.10, .14), 2),
                                       "prim_L": round(rnd.uniform(.88, .93), 2), "prim_C": round(rnd.uniform(.12, .16), 2)}}


def colors_for(recipe: dict, seeds_key: str, offset: int, n: int = COLORS_PER_TEMPLATE) -> List[dict]:
    fn = {"light": palettes.light_recipe, "dark": palettes.dark_recipe, "cream": palettes.cream_recipe}[recipe["type"]]
    seeds = palettes.SEEDS[seeds_key]
    out = []
    for k in range(n):
        name, slug, h, h2, h3 = seeds[(offset + k) % len(seeds)]
        pal = fn(h, h2, h3, **recipe["kwargs"])
        out.append({"slug": slug, "name": name, "palette": pal})
    return out


def _pick(options, used: Counter, rnd: random.Random, avoid=()):
    cands = [o for o in options if o not in avoid] or list(options)
    m = min(used[o] for o in cands)
    best = [o for o in cands if used[o] == m]
    return rnd.choice(best)


def generate(count: int = 180, start_code: int = 21, seed: int = 2026) -> List[dict]:
    rnd = random.Random(seed)
    arts = list(ARTS)
    used = {k: Counter() for k in ["cover", "mode", "font", *DIMS]}
    per_art = {a: {"cover": set(), "font": set(), "mode": Counter(), "name": 0} for a in arts}
    seen_combos = set()
    out = []
    order = []
    while len(order) < count:
        block = arts[:]
        rnd.shuffle(block)
        order += block
    order = order[:count]
    for i, art in enumerate(order):
        info = ARTS[art]
        pa = per_art[art]
        mode = _pick([m for m in info["modes"]], Counter({m: used["mode"][m] + 3 * pa["mode"][m] for m in info["modes"]}), rnd)
        cover = _pick(COVERS, used["cover"], rnd, avoid=pa["cover"])
        fonts_ok = [k for k, f in enumerate(FONT_PAIRS) if f[2] in info["fonts"]]
        font = _pick(fonts_ok, used["font"], rnd, avoid=pa["font"])
        tr = {}
        for dim, opts in DIMS.items():
            avoid = set()
            if dim == "card" and font is not None and FONT_PAIRS[font][2] == "hand":
                avoid |= {"minimal", "ticket"}
            if dim == "rad" and FONT_PAIRS[font][2] == "hand":
                avoid |= {"sharp"}
            if dim == "rad" and art in ("swiss", "bauhaus", "magazine", "blueprint"):
                avoid |= {"pill", "round"}
            if dim == "fr" and cover in ("circle", "arch") :
                avoid |= {cover}
            tr[dim] = _pick(opts, used[dim], rnd, avoid=avoid)
        if tr["card"] == "glass" and tr["bg"] not in ("glow", "blobs", "wave", "tint"):
            tr["bg"] = rnd.choice(["glow", "blobs", "tint"])
        combo = (art, cover, font)
        assert combo not in seen_combos
        seen_combos.add(combo)
        used["mode"][mode] += 1
        pa["mode"][mode] += 1
        used["cover"][cover] += 1
        used["font"][font] += 1
        pa["cover"].add(cover)
        pa["font"].add(font)
        for dim, v in tr.items():
            used[dim][v] += 1

        title_f, body_f, mood, typ = FONT_PAIRS[font]
        name = info["names"][pa["name"] % len(info["names"])]
        pa["name"] += 1
        code = start_code + i
        recipe = recipe_for(mode, rnd)
        colors = colors_for(recipe, SEED_KEY[mode], offset=rnd.randrange(11))
        cats = list(dict.fromkeys(info["cats"]))
        tagline = f"{UZ['mode'][mode]}, {UZ['cover'][cover]}, {info['uz']} va {UZ['card'][tr['card']]}"
        out.append({
            "id": f"{code:03d}_{name.lower().replace(' ', '_').replace('-', '_')}",
            "code": str(code), "name": name, "tagline": tagline, "mode": "dark" if mode in ("dark", "vivid") else "light",
            "tone": mode, "art": art, "cover_variant": cover,
            "cards_variant": "grid" if tr["card"] in ("leftbar", "minimal", "solid") or i % 3 == 0 else "row",
            "fonts": {"title": title_f, "body": body_f},
            "pptx_fonts": {"title": "Cambria" if title_f in _PPTX_SERIF_TITLES else "Arial",
                           "body": "Cambria" if body_f in _SERIF_BODY else "Calibri"},
            "type": typ, "traits": tr, "categories": cats,
            "category": " • ".join({"tech": "Texnologiya", "education": "Ta’lim", "nature": "Tabiat", "business": "Biznes",
                                    "creative": "Ijod", "culture": "Madaniyat", "minimal": "Minimal"}[c] for c in cats),
            "writing_tone": MOOD_TONE[cats[0]],
            "pdf_mode": "raster" if art in HEAVY_ART or tr["card"] == "glass" else "vector",
            "recipe": recipe, "colors": colors,
        })
    assign_stickers(out)
    assign_packs(out)
    return out


STICKER_STYLES = {
    "light": ["diecut", "line", "riso", "doodle", "chunky", "badge", "flat", "mono"],
    "cream": ["diecut", "riso", "line", "doodle", "badge", "mono", "chunky", "flat"],
    "dark": ["glass", "diecut", "chunky", "badge", "line", "mono", "flat"],
    "vivid": ["diecut", "chunky", "glass", "badge", "line", "flat"],
}
STICKER_PLACES = ["corner", "cards", "both", "corner", "cards", "art"]
_CORNER_DECOR = {"tri", "dots", "circles", "plus"}


def assign_stickers(templates: List[dict], seed: int = 77) -> None:
    """Sticker style + placement per generated template (separate RNG: the designs stay as they are)."""
    rnd = random.Random(seed)
    used_style, used_place = Counter(), Counter()
    for t in templates:
        styles = STICKER_STYLES[t["tone"]]
        if FONT_MOOD.get(t["fonts"]["title"]) == "hand" and "doodle" in styles:
            styles = ["doodle", "diecut", "chunky"]
        style = _pick(styles, used_style, rnd)
        place = _pick(sorted(set(STICKER_PLACES)), Counter({p: used_place[p] * (2 if p == "art" else 1) for p in set(STICKER_PLACES)}), rnd)
        used_style[style] += 1
        used_place[place] += 1
        t["sticker_style"], t["sticker_place"] = style, place
        if place in ("corner", "both") and t["traits"]["dec"] in _CORNER_DECOR:
            t["traits"]["dec"] = rnd.choice(["bignum", "tab", "tricolor", "pagebadge", "brackets", "leaf"])


def assign_packs(templates: List[dict], seed: int = 91) -> None:
    """Decoration pack per generated template (most get one); its own RNG keeps designs unchanged."""
    from services.deck.packs import PACK_TONES
    rnd = random.Random(seed)
    used = Counter()
    for i, t in enumerate(templates):
        if i % 5 == 4:          # every fifth template stays clean
            t["pack"] = ""
            continue
        ok = [p for p, tones in PACK_TONES.items() if t["tone"] in tones.split()]
        if t["art"] in ("medical",) and "medical" in ok:
            ok = ["medical", "plexus", "bubbles"]
        p = _pick(ok, used, rnd)
        used[p] += 1
        t["pack"] = p
        if t["traits"]["dec"] not in ("none", "bignum", "pagebadge"):
            t["traits"]["dec"] = rnd.choice(["none", "bignum", "pagebadge"])
        if t["traits"]["bg"] in ("frame", "band") and p in ("ornate", "tropic", "floral", "ribbon", "waves", "halfcircles"):
            t["traits"]["bg"] = rnd.choice(["plain", "dots", "tint", "paper"])


FONT_MOOD = {}
for _t, _b, _m, _x in FONT_PAIRS:
    FONT_MOOD.setdefault(_t, _m)


def type_css(t: dict) -> str:
    """CSS custom properties for a template's typography settings."""
    scale = t.get("scale", 1)
    v = {
        "--title-weight": t.get("w", 700), "--title-tracking": t.get("tr", "-0.02em"), "--title-lh": t.get("lh", 1.05),
        "--title-transform": t.get("tf", "none"), "--title-style": "italic" if t.get("it") else "normal",
        "--num-weight": t.get("w", 700), "--item-weight": 700 if t.get("w", 700) >= 600 else 600,
        "--fs-title": f"{round(72 * scale)}px", "--fs-cover": f"{round(112 * scale)}px",
    }
    return ":root{" + "".join(f"{k}:{val};" for k, val in v.items()) + "}"
