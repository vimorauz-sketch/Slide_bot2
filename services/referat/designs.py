"""
Referat templates (100): a title-page layout (and its mirrored / recoloured variant), a heading
style, a page decoration for the inner pages, a colour palette, a font pair and a sample topic.

Inner pages always keep the academic standard teachers expect (A4, 14 pt body text, 1.5 line
spacing, margins 3 / 1.5 / 2 / 2 cm, first-line indent, page numbers at the bottom); templates
change the title page, the headings, the page decoration and the colours.
"""
from __future__ import annotations

from typing import Dict, List

PALETTES: Dict[str, Dict[str, str]] = {
    # ink = body text, accent = main colour, accent2 = second colour, soft = light tint
    "navy":       {"name": "To‘q ko‘k", "ink": "#1B2430", "accent": "#1E3A8A", "accent2": "#3B82F6", "soft": "#E8EEFB"},
    "burgundy":   {"name": "Bordo", "ink": "#2A1A1F", "accent": "#7F1D1D", "accent2": "#B45309", "soft": "#F8ECEC"},
    "emerald":    {"name": "Zumrad", "ink": "#13241D", "accent": "#065F46", "accent2": "#10B981", "soft": "#E6F4EE"},
    "black":      {"name": "Klassik qora", "ink": "#111111", "accent": "#111111", "accent2": "#6B6B6B", "soft": "#F1F1F1"},
    "teal":       {"name": "Moviy-yashil", "ink": "#102A2E", "accent": "#0F766E", "accent2": "#14B8A6", "soft": "#E3F4F2"},
    "purple":     {"name": "Binafsha", "ink": "#1F1630", "accent": "#5B21B6", "accent2": "#A78BFA", "soft": "#EFEAFB"},
    "gold":       {"name": "Oltin", "ink": "#2B2416", "accent": "#92400E", "accent2": "#D4A017", "soft": "#FBF3E2"},
    "crimson":    {"name": "Qirmizi", "ink": "#22151A", "accent": "#BE123C", "accent2": "#FB7185", "soft": "#FDECEF"},
    "sky":        {"name": "Osmon", "ink": "#0F2233", "accent": "#0369A1", "accent2": "#38BDF8", "soft": "#E5F3FB"},
    "olive":      {"name": "Zaytun", "ink": "#22251A", "accent": "#4D7C0F", "accent2": "#A3B18A", "soft": "#EEF2E3"},
    "coral":      {"name": "Marjon", "ink": "#2A1B17", "accent": "#C2410C", "accent2": "#FB923C", "soft": "#FDEEE5"},
    "slate":      {"name": "Grafit", "ink": "#1E2430", "accent": "#334155", "accent2": "#94A3B8", "soft": "#EEF1F5"},
    "lazurit":    {"name": "Lazurit va oltin", "ink": "#14213D", "accent": "#1D4ED8", "accent2": "#F59E0B", "soft": "#E9EEFB"},
    "rose":       {"name": "Pushti", "ink": "#2A1621", "accent": "#BE185D", "accent2": "#F9A8D4", "soft": "#FCEAF3"},
    "brown":      {"name": "Jigarrang", "ink": "#2B2018", "accent": "#78350F", "accent2": "#C08A52", "soft": "#F5EDE3"},
    "midnight":   {"name": "Tun", "ink": "#0F172A", "accent": "#0B1739", "accent2": "#60A5FA", "soft": "#E6ECF7"},
    "forest":     {"name": "O‘rmon", "ink": "#14231A", "accent": "#14532D", "accent2": "#84CC16", "soft": "#ECF5E8"},
    "plum":       {"name": "Olxo‘ri", "ink": "#24142A", "accent": "#6B21A8", "accent2": "#F0ABFC", "soft": "#F6EAFB"},
    "ocean":      {"name": "Okean", "ink": "#0C2230", "accent": "#155E75", "accent2": "#22D3EE", "soft": "#E2F5F9"},
    "terracotta": {"name": "Terrakota", "ink": "#2B1A14", "accent": "#9A3412", "accent2": "#FDBA74", "soft": "#FBEEE6"},
    "charcoal":   {"name": "Ko‘mir", "ink": "#18181B", "accent": "#27272A", "accent2": "#EAB308", "soft": "#F4F4F5"},
    "sunflower":  {"name": "Kungaboqar", "ink": "#2A2310", "accent": "#A16207", "accent2": "#FACC15", "soft": "#FDF7DD"},
    "indigo":     {"name": "Indigo", "ink": "#16173A", "accent": "#3730A3", "accent2": "#818CF8", "soft": "#ECEDFC"},
    "wine":       {"name": "Vino", "ink": "#2A1418", "accent": "#5B0E1F", "accent2": "#E11D48", "soft": "#F8E8EC"},
    "mint":       {"name": "Yalpiz", "ink": "#11261F", "accent": "#047857", "accent2": "#6EE7B7", "soft": "#E3F7EF"},
    "chalkboard": {"name": "Doska", "ink": "#16241D", "accent": "#1F3B2D", "accent2": "#F5E6A8", "soft": "#E9F0EA"},
    "blueprint":  {"name": "Chizma", "ink": "#0E1C33", "accent": "#123A6B", "accent2": "#9CC8FF", "soft": "#E7F0FB"},
}

# Title-page layouts: text geometry in mm (top block, middle block, info block, side margins,
# alignment, left edge of the info block, distance of the city line from the bottom) and colour tone
# ("light" = white text on a dark page; "top_light" = white text only in the top block).
_D = dict(top=22, mid=112, info=206, left=22, right=22, align="center", info_left=100, city=20, tone="dark")
LAYOUTS: Dict[str, Dict] = {
    "frame": dict(name="Klassik ramka"),
    "double": dict(name="Qo‘sh chiziqli ramka"),
    "ornament": dict(name="Milliy naqsh burchaklari", top=30, left=36, right=36),
    "band": dict(name="Yon rangli tasma", left=60, right=18, align="left", info_left=60, mirror=True),
    "header": dict(name="Yuqori rangli blok", top=16, mid=118, city=17, tone="top_light"),
    "corners": dict(name="Geometrik burchaklar", top=30, left=40, right=40, mirror=True),
    "minimal": dict(name="Minimal", top=30, mid=140, info=214, left=28, right=28, align="left", info_left=28, city=30),
    "wave": dict(name="To‘lqinlar", city=34),
    "photo": dict(name="Muqovada rasm", top=7, mid=140, info=214, city=15, tone="top_light", photo="top"),
    "dots": dict(name="Nuqtali ramka", left=26, right=26),
    "diagonal": dict(name="Qiya tasma", top=26, left=18, right=70, align="left", info_left=102, mirror=True),
    "emblem": dict(name="Gerb-medalyon", top=24, mid=134, info=212),
    "split": dict(name="Ikki rangli sahifa", mid=104, left=18, right=76, align="left", info_left=18, mirror=True),
    "arch": dict(name="Ravoq", top=46, mid=124, info=208, left=36, right=36, info_left=92, city=25),
    "dark_full": dict(name="To‘q fon", top=26, left=26, right=26, tone="light"),
    "gradient": dict(name="Gradient fon", tone="light"),
    "blueprint": dict(name="Texnik chizma", left=24, right=24, tone="light"),
    "chalk": dict(name="Bo‘r doska", left=28, right=28, top=28, tone="light"),
    "notebook": dict(name="Daftar varag‘i", left=40, right=18, align="left", info_left=40),
    "graph": dict(name="Katakli qog‘oz"),
    "circle_big": dict(name="Katta doira", left=22, right=60, align="left", info_left=22, mirror=True),
    "arcs": dict(name="Konsentrik yoylar", mirror=True),
    "hexagons": dict(name="Olti burchaklar", top=66, mid=124, info=212),
    "triangles": dict(name="Uchburchak mozaika", top=62, mid=122, info=210),
    "stripes_h": dict(name="Gorizontal chiziqlar", top=50, mid=120, info=210),
    "stripes_v": dict(name="Vertikal chiziqlar", left=46, right=18, align="left", info_left=46, mirror=True),
    "sash": dict(name="Burchak lentasi", top=46, mid=120, left=30, right=30, mirror=True),
    "book": dict(name="Kitob muqovasi", left=52, right=18, align="left", info_left=52, mirror=True),
    "certificate": dict(name="Sertifikat ramkasi", top=30, left=32, right=32, info_left=96, city=42),
    "lace": dict(name="To‘r chekka", top=30, left=30, right=30, city=26),
    "art_deco": dict(name="Art-deko", top=58, mid=124, info=212),
    "bauhaus": dict(name="Bauhaus shakllari", left=22, right=40, align="left", info_left=22, mirror=True),
    "botanical": dict(name="Barglar", top=30, left=34, right=34),
    "watercolor": dict(name="Akvarel dog‘lari", top=28),
    "mountains": dict(name="Tog‘lar", mid=74, info=148, city=14, city_tone="light"),
    "skyline": dict(name="Shahar manzarasi", mid=100, info=170, city=80),
    "sunrays": dict(name="Quyosh nurlari", city=54),
    "halftone": dict(name="Nuqtali gradient", top=52, mid=120, left=22, right=56, align="left", info_left=22, mirror=True),
    "waves_top": dict(name="Yuqori to‘lqinlar", top=8, mid=116, tone="top_light"),
    "tab_frame": dict(name="Yorliqli ramka", top=34, left=28, right=28),
    "card": dict(name="Markaziy karta", top=48, mid=122, info=200, left=36, right=36, info_left=92, city=40),
    "side_photo": dict(name="Yon tomonda rasm", left=92, right=16, align="left", info_left=92, photo="side", mirror=True),
    "bottom_photo": dict(name="Pastda rasm", mid=60, info=124, city=134, photo="bottom"),
    "circle_photo": dict(name="Doira ichida rasm", top=16, mid=160, info=222, city=16, photo="circle"),
    "magazine": dict(name="Jurnal muqovasi", top=22, mid=74, info=214, left=20, right=20, align="left", info_left=20,
                     city=22, big_kind=True),
    "timeline": dict(name="Vaqt chizig‘i", left=42, right=20, align="left", info_left=42, mirror=True),
    "brackets": dict(name="Burchak qavslari"),
    "double_band": dict(name="Ikki keng tasma", top=28, city=24),
    "girih_band": dict(name="Girih tasmasi", top=50, mid=120, info=210),
    "mosaic": dict(name="Kvadrat mozaika", left=22, right=60, align="left", info_left=22, mirror=True),
    "orbits": dict(name="Orbitalar", left=22, right=60, mid=118, align="left", info_left=22, mirror=True),
    "molecule": dict(name="Molekula to‘ri", top=40, mid=118),
    "stamp": dict(name="Shtamp va muhr", left=30, right=30, info_left=34),
    "diag_split": dict(name="Qiya bo‘linish", info=186, city=16, city_tone="light"),
}
for _k, _v in LAYOUTS.items():
    LAYOUTS[_k] = {**_D, **_v}

COVERS = {k: v["name"] for k, v in LAYOUTS.items()}

# Mini App filter groups
GROUPS = {
    "Klassik": ("frame", "double", "emblem", "arch", "certificate", "lace", "book", "brackets", "stamp", "tab_frame", "card"),
    "Milliy": ("ornament", "girih_band", "mosaic", "art_deco"),
    "Zamonaviy": ("band", "header", "corners", "minimal", "diagonal", "split", "stripes_h", "stripes_v", "sash",
                  "double_band", "diag_split", "bauhaus", "magazine", "timeline", "triangles", "hexagons"),
    "To‘q fon": ("dark_full", "gradient", "blueprint", "chalk"),
    "Rasmli": ("photo", "side_photo", "bottom_photo", "circle_photo"),
    "Tabiat": ("wave", "waves_top", "botanical", "watercolor", "mountains", "skyline", "sunrays"),
    "Ilmiy": ("notebook", "graph", "dots", "halftone", "circle_big", "arcs", "orbits", "molecule"),
}
GROUP_OF = {lay: g for g, lays in GROUPS.items() for lay in lays}
assert set(GROUP_OF) == set(LAYOUTS), set(LAYOUTS) ^ set(GROUP_OF)

HEADINGS = {
    "bar": "Yon chiziqli",
    "underline": "Tagiga chizilgan",
    "caps": "Markazda, bosh harflar",
    "badge": "Raqamli doiracha",
    "box": "Rangli fon",
    "rule": "Ikki tomonida chiziq",
    "pill": "Yumaloq yorliq",
    "numbig": "Katta raqam",
    "overline": "Ustki chiziq",
    "marker": "Marker bilan",
    "block": "Rangli raqam bloki",
}

PAGES = {
    "none": "Bezaksiz",
    "band_top": "Yuqorida rangli tasma",
    "rule_top": "Yuqorida ingichka chiziq",
    "side_line": "Chapda chiziq",
    "side_band": "Chapda rangli tasma",
    "frame": "Sahifa ramkasi",
    "band_bottom": "Pastda rangli tasma",
    "corners": "Burchak belgilari",
}

TOPICS = ("photosynthesis", "timur", "heart", "ai", "startup", "navoi", "climate", "pedagogy")

# (name, layout, variant, heading, page decoration, palette, title font, body font, topic)
_TEMPLATES = [
    ("Akademik", "frame", 0, "caps", "none", "black", "g:tinos", "g:tinos", "photosynthesis"),
    ("Universitet", "double", 0, "caps", "rule_top", "navy", "g:ptserif", "g:ptserif", "pedagogy"),
    ("Milliy naqsh", "ornament", 0, "rule", "corners", "lazurit", "g:cormorantgaramond", "g:ptserif", "timur"),
    ("Zamonaviy ko‘k", "band", 0, "bar", "side_line", "navy", "g:montserrat", "g:opensans", "ai"),
    ("Ilmiy", "header", 0, "underline", "rule_top", "slate", "g:sourceserif4", "g:sourceserif4", "climate"),
    ("Geometriya", "corners", 0, "badge", "none", "teal", "g:inter", "g:inter", "startup"),
    ("Minimal", "minimal", 0, "bar", "none", "black", "g:inter", "g:sourceserif4", "navoi"),
    ("Dengiz", "wave", 0, "box", "band_bottom", "sky", "g:raleway", "g:lato", "climate"),
    ("Tabiat surati", "photo", 0, "bar", "rule_top", "emerald", "g:playfairdisplay", "g:sourcesans3", "photosynthesis"),
    ("Nuqtalar", "dots", 0, "badge", "none", "purple", "g:jost", "g:ibmplexsans", "pedagogy"),
    ("Dinamik", "diagonal", 0, "box", "band_top", "coral", "g:oswald", "g:ptsans", "startup"),
    ("Oliygoh", "emblem", 0, "caps", "frame", "burgundy", "g:cinzel", "g:cardo", "navoi"),
    ("Ikki rang", "split", 0, "bar", "side_band", "lazurit", "g:montserrat", "g:notosans", "ai"),
    ("Sharq ravog‘i", "arch", 0, "rule", "corners", "gold", "g:prata", "g:ptserif", "timur"),
    ("Tungi ko‘k", "dark_full", 0, "pill", "band_top", "midnight", "g:sora", "g:inter", "ai"),
    ("Shafaq", "gradient", 0, "numbig", "none", "plum", "g:outfit", "g:dmsans", "startup"),
    ("Muhandis", "blueprint", 0, "block", "frame", "blueprint", "g:chakrapetch", "g:ibmplexsans", "ai"),
    ("Sinf doskasi", "chalk", 0, "marker", "none", "chalkboard", "g:caveatbrush", "g:ptsans", "pedagogy"),
    ("Daftar", "notebook", 0, "underline", "side_line", "navy", "g:caveat", "g:ptsans", "pedagogy"),
    ("Katakli", "graph", 0, "badge", "rule_top", "indigo", "g:spacegrotesk", "g:ibmplexsans", "ai"),
    ("Quyosh doirasi", "circle_big", 0, "overline", "none", "sunflower", "g:dmserifdisplay", "g:lato", "climate"),
    ("Yoylar", "arcs", 0, "numbig", "band_bottom", "teal", "g:urbanist", "g:notosans", "heart"),
    ("Asal kataklari", "hexagons", 0, "block", "none", "gold", "g:exo2", "g:roboto", "photosynthesis"),
    ("Kristall", "triangles", 0, "pill", "side_band", "indigo", "g:lexend", "g:inter", "ai"),
    ("Ufq", "stripes_h", 0, "overline", "rule_top", "terracotta", "g:bebasneue", "g:sourcesans3", "startup"),
    ("Retro chiziq", "stripes_v", 0, "marker", "none", "coral", "g:righteous", "g:nunito", "pedagogy"),
    ("Lenta", "sash", 0, "box", "band_top", "crimson", "g:poppins", "g:opensans", "startup"),
    ("Kitob", "book", 0, "caps", "frame", "brown", "g:ebgaramond", "g:ebgaramond", "navoi"),
    ("Sertifikat", "certificate", 0, "rule", "frame", "emerald", "g:cinzel", "g:cormorant", "timur"),
    ("Nafis to‘r", "lace", 0, "overline", "corners", "rose", "g:greatvibes", "g:lora", "navoi"),
    ("Art-deko", "art_deco", 0, "rule", "rule_top", "charcoal", "g:poiretone", "g:josefinsans", "navoi"),
    ("Bauhaus", "bauhaus", 0, "block", "side_band", "crimson", "g:archivoblack", "g:worksans", "startup"),
    ("Bog‘", "botanical", 0, "overline", "none", "forest", "g:lora", "g:lora", "photosynthesis"),
    ("Akvarel", "watercolor", 0, "marker", "none", "plum", "g:dancingscript", "g:quicksand", "pedagogy"),
    ("Tog‘ cho‘qqisi", "mountains", 0, "underline", "band_bottom", "ocean", "g:montserrat", "g:opensans", "climate"),
    ("Metropol", "skyline", 0, "bar", "rule_top", "slate", "g:oswald", "g:roboto", "startup"),
    ("Tong", "sunrays", 0, "caps", "none", "sunflower", "g:playfairdisplay", "g:ptserif", "climate"),
    ("Pop-art", "halftone", 0, "pill", "band_top", "crimson", "g:bangers", "g:nunito", "startup"),
    ("Okean to‘lqini", "waves_top", 0, "numbig", "band_bottom", "ocean", "g:quicksand", "g:nunito", "climate"),
    ("Papka", "tab_frame", 0, "badge", "frame", "sky", "g:figtree", "g:figtree", "pedagogy"),
    ("Karta", "card", 0, "overline", "none", "mint", "g:manrope", "g:notosans", "heart"),
    ("Panorama", "side_photo", 0, "bar", "side_line", "forest", "g:playfairdisplay", "g:sourcesans3", "photosynthesis"),
    ("Manzara", "bottom_photo", 0, "underline", "rule_top", "terracotta", "g:dmserifdisplay", "g:lato", "timur"),
    ("Linza", "circle_photo", 0, "rule", "none", "teal", "g:marcellus", "g:ptsans", "heart"),
    ("Jurnal", "magazine", 0, "numbig", "band_top", "black", "g:anton", "g:sourceserif4", "navoi"),
    ("Xronologiya", "timeline", 0, "block", "side_line", "brown", "g:alegreya", "g:alegreya", "timur"),
    ("Qavslar", "brackets", 0, "overline", "corners", "indigo", "g:ibmplexserif", "g:ibmplexsans", "ai"),
    ("Ikki tasma", "double_band", 0, "box", "band_top", "wine", "g:prata", "g:ptserif", "navoi"),
    ("Girih", "girih_band", 0, "rule", "frame", "lazurit", "g:yesevaone", "g:ptserif", "timur"),
    ("Piksel", "mosaic", 0, "block", "none", "ocean", "g:pressstart2p", "g:ibmplexsans", "ai"),
    ("Orbita", "orbits", 0, "pill", "rule_top", "midnight", "g:audiowide", "g:exo2", "ai"),
    ("Molekula", "molecule", 0, "badge", "side_line", "mint", "g:sora", "g:notosans", "heart"),
    ("Muhr", "stamp", 0, "caps", "frame", "wine", "g:oldstandardtt", "g:oldstandardtt", "timur"),
    ("Qiya bo‘lak", "diag_split", 0, "marker", "band_bottom", "coral", "g:montserratalternates", "g:nunito", "startup"),
    # second variants: mirrored or recoloured layouts with different type, headings and pages
    ("Klassik ko‘k", "frame", 1, "underline", "rule_top", "navy", "g:ptserif", "g:ptserif", "pedagogy"),
    ("Adabiyot", "double", 1, "rule", "corners", "brown", "g:ebgaramond", "g:ebgaramond", "navoi"),
    ("Zumrad naqsh", "ornament", 1, "caps", "frame", "emerald", "g:cormorantgaramond", "g:ebgaramond", "timur"),
    ("Kimyo laboratoriyasi", "header", 1, "badge", "side_line", "crimson", "g:inter", "g:inter", "heart"),
    ("Toza varaq", "minimal", 1, "overline", "rule_top", "navy", "g:lora", "g:lora", "photosynthesis"),
    ("Yashil to‘lqin", "wave", 1, "badge", "none", "emerald", "g:exo2", "g:roboto", "photosynthesis"),
    ("Qirmizi tasma", "diagonal", 1, "bar", "side_band", "crimson", "g:montserrat", "g:opensans", "ai"),
    ("Oltin medal", "emblem", 1, "rule", "corners", "gold", "g:cinzel", "g:ebgaramond", "timur"),
    ("Moviy ravoq", "arch", 1, "caps", "frame", "teal", "g:tenorsans", "g:ptsans", "heart"),
    ("Qizil vino", "dark_full", 1, "rule", "corners", "wine", "g:playfairdisplay", "g:lora", "navoi"),
    ("Okean gradienti", "gradient", 1, "pill", "band_bottom", "ocean", "g:poppins", "g:opensans", "climate"),
    ("Arxitektor", "blueprint", 1, "overline", "rule_top", "navy", "g:michroma", "g:robotomono", "startup"),
    ("Formula doskasi", "chalk", 1, "box", "frame", "chalkboard", "g:patrickhand", "g:nunito", "ai"),
    ("Konspekt", "notebook", 1, "marker", "none", "purple", "g:kalam", "g:nunito", "navoi"),
    ("Millimetrovka", "graph", 1, "numbig", "side_line", "olive", "g:robotoslab", "g:robotoslab", "photosynthesis"),
    ("Oy doirasi", "circle_big", 1, "pill", "band_top", "indigo", "g:fredoka", "g:nunito", "pedagogy"),
    ("Ritm", "arcs", 1, "underline", "none", "crimson", "g:syncopate", "g:inter", "startup"),
    ("Sota", "hexagons", 1, "badge", "rule_top", "teal", "g:titilliumweb", "g:titilliumweb", "heart"),
    ("Poligon", "triangles", 1, "block", "band_bottom", "coral", "g:russoone", "g:ptsans", "startup"),
    ("Yetmishinchi", "stripes_h", 1, "pill", "side_band", "sunflower", "g:righteous", "g:nunito", "pedagogy"),
    ("Neon chiziq", "stripes_v", 1, "numbig", "band_top", "plum", "g:unbounded", "g:golostext", "ai"),
    ("Sovg‘a lentasi", "sash", 1, "overline", "corners", "emerald", "g:cookie", "g:lora", "navoi"),
    ("Daftar muqovasi", "book", 1, "bar", "side_band", "navy", "g:bitter", "g:bitter", "pedagogy"),
    ("Diplom", "certificate", 1, "caps", "rule_top", "gold", "g:cinzel", "g:ptserif", "pedagogy"),
    ("Kumush to‘r", "lace", 1, "rule", "frame", "slate", "g:parisienne", "g:cormorantgaramond", "timur"),
    ("Gatsbi", "art_deco", 1, "box", "frame", "gold", "g:marcellus", "g:josefinsans", "startup"),
    ("Konstruktiv", "bauhaus", 1, "badge", "band_top", "lazurit", "g:jost", "g:jost", "ai"),
    ("Herbariy", "botanical", 1, "marker", "corners", "olive", "g:cormorant", "g:literata", "photosynthesis"),
    ("Pastel", "watercolor", 1, "pill", "band_bottom", "sky", "g:comfortaa", "g:nunito", "heart"),
    ("Qorli cho‘qqi", "mountains", 1, "caps", "none", "indigo", "g:cinzel", "g:ptsans", "climate"),
    ("Tungi shahar", "skyline", 1, "block", "side_band", "midnight", "g:audiowide", "g:inter", "ai"),
    ("Kungaboqar", "sunrays", 1, "numbig", "band_top", "coral", "g:fredoka", "g:quicksand", "photosynthesis"),
    ("Komiks", "halftone", 1, "block", "side_band", "sky", "g:bangers", "g:patrickhand", "pedagogy"),
    ("Moviy to‘lqin", "waves_top", 1, "overline", "rule_top", "navy", "g:lexend", "g:lexend", "climate"),
    ("Tibbiy karta", "card", 1, "badge", "band_top", "teal", "g:figtree", "g:figtree", "heart"),
    ("Yon manzara", "side_photo", 1, "overline", "none", "ocean", "g:marcellus", "g:lato", "climate"),
    ("Tarixiy manzara", "bottom_photo", 1, "caps", "frame", "burgundy", "g:cinzel", "g:cardo", "timur"),
    ("Mikroskop", "circle_photo", 1, "block", "rule_top", "emerald", "g:exo2", "g:notosans", "photosynthesis"),
    ("Moda jurnali", "magazine", 1, "overline", "none", "rose", "g:abrilfatface", "g:lato", "navoi"),
    ("Taraqqiyot", "timeline", 1, "numbig", "band_bottom", "sky", "g:outfit", "g:dmsans", "ai"),
    ("Kod", "brackets", 1, "block", "rule_top", "charcoal", "g:jetbrainsmono", "g:ibmplexsans", "ai"),
    ("Ikki chiziq", "double_band", 1, "underline", "side_line", "forest", "g:sourceserif4", "g:sourceserif4", "climate"),
    ("Islimiy", "girih_band", 1, "caps", "corners", "emerald", "g:cormorantgaramond", "g:ptserif", "navoi"),
    ("Rangli mozaika", "mosaic", 1, "pill", "band_top", "coral", "g:rubik", "g:rubik", "pedagogy"),
    ("Galaktika", "orbits", 1, "overline", "frame", "purple", "g:tektur", "g:exo2", "ai"),
    ("Biokimyo", "molecule", 1, "numbig", "band_bottom", "sky", "g:lexend", "g:inter", "heart"),
]



def _build() -> List[Dict]:
    out = []
    for n, (name, cover, variant, heading, page, pal, tf, bf, topic) in enumerate(_TEMPLATES[:100], start=1):
        out.append({"id": f"r{n:02d}", "code": n, "name": name, "cover": cover, "variant": variant, "heading": heading,
                    "page": page, "palette_id": pal, "palette": dict(PALETTES[pal]), "fonts": {"title": tf, "body": bf},
                    "topic": topic, "layout": geometry(cover, variant)})
    return out


def geometry(cover: str, variant: int = 0) -> Dict:
    """Text positions of a title page; a mirrored variant mirrors them too."""
    g = dict(LAYOUTS.get(cover, LAYOUTS["frame"]))
    if variant % 2 and g.get("mirror"):
        g["left"], g["right"] = g["right"], g["left"]
        g["info_left"] = 210 - g["info_left"] - 86
        g["mirrored"] = True
    return g


TEMPLATES = _build()
BY_ID = {t["id"]: t for t in TEMPLATES}
DEFAULT = "r01"


def get(template_id: str) -> Dict:
    t = BY_ID.get(str(template_id), BY_ID[DEFAULT])
    return {**t, "palette": dict(t["palette"]), "fonts": dict(t["fonts"]), "layout": dict(t["layout"])}


def by_number(n) -> Dict:
    try:
        return get(f"r{int(n):02d}")
    except (TypeError, ValueError):
        return get(DEFAULT)
