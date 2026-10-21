import pytest
from services.deck import themes
from services.deck.fonts import FAMILY_NAMES, font_face_css

REQUIRED = ["bg", "bg2", "surface", "text", "muted", "primary", "secondary", "accent", "on_primary"]


def test_there_are_400_templates_numbered_1_to_400():
    assert len(themes.list_family_ids()) == 20
    ids = themes.list_theme_ids()
    assert len(ids) == 400 and len(set(ids)) == 400
    assert [int(themes.get_theme(t)["code"]) for t in ids] == list(range(1, 401))
    assert all(themes.get_theme(t).get("photo") for t in ids[200:])
    assert not any(themes.get_theme(t).get("photo") for t in ids[:200])


SAMPLE_IDS = themes.list_family_ids() + themes.list_theme_ids()[20::23]


@pytest.mark.parametrize("tid", SAMPLE_IDS)
def test_theme_has_palette_fonts_css_and_art(tid):
    t = themes.get_theme(tid)
    for key in REQUIRED:
        assert t["palette"][key].startswith("#"), (tid, key)
    assert t["fonts"]["title"] in FAMILY_NAMES and t["fonts"]["body"] in FAMILY_NAMES
    assert t["pptx_fonts"]["title"] in ("Arial", "Calibri", "Cambria", "Times New Roman")
    assert "--primary" in t["css"]
    from services.deck.art import STYLES
    from services.deck.design_space import COVERS
    assert t["art"] in STYLES
    assert t["cover_variant"] in COVERS
    assert "@font-face" in font_face_css([t["fonts"]["title"]])
    assert len(t["colors"]) == 10


@pytest.mark.parametrize("key", ["5", "05", "05_nature_organic", "tpl_05_nature_organic"])
def test_theme_aliases_resolve(key):
    assert themes.resolve_theme_id(key) == "05_nature_organic"


def test_unknown_theme_falls_back_to_default():
    assert themes.get_theme("nope")["id"] == themes.DEFAULT_THEME


def test_custom_spec_picks_a_dark_or_light_base():
    dark = themes.get_theme({"background_color": "#0A0A12", "primary_color": "#FF0000"})
    light = themes.get_theme({"background_color": "#FAFAFA", "primary_color": "#FF0000"})
    assert dark["mode"] == "dark" and light["mode"] == "light"
    assert "--primary:#FF0000" in dark["css"]


def test_get_theme_returns_independent_copies():
    a = themes.get_theme("01")
    a["palette"]["primary"] = "#000000"
    assert themes.get_theme("01")["palette"]["primary"] != "#000000"


def test_colour_set_swaps_only_the_palette():
    base = themes.get_theme("150")
    key = themes.theme_colors("150")[4]["key"]
    v = themes.get_theme(key)
    assert v["id"] == key and v["art"] == base["art"] and v["trait_classes"] == base["trait_classes"]
    assert v["css"].startswith(base["css"])
    assert f"--primary:{v['palette']['primary']}" in v["css"]
    assert v["palette"]["primary"] != base["palette"]["primary"]
    assert v["color_name"] == themes.theme_colors("150")[4]["name"]


def test_family_colour_sets_keep_the_family_design():
    fam = themes.get_theme("12_pastel_playful")
    v = themes.get_theme("12_pastel_playful~pomegranate")
    assert v["family"] == "12_pastel_playful" and v["css"].startswith(fam["css"])
    assert themes.theme_colors("12")[0]["key"] == "12_pastel_playful" and themes.theme_colors("12")[0]["name"] == "Asl"


def test_every_colour_set_passes_contrast_checks():
    from services.deck.palettes import check_palette
    for tid in themes.list_theme_ids():
        for c in themes.theme_colors(tid)[1:]:
            assert check_palette(c["palette"]) == [], c["key"]


def test_generated_templates_are_all_different():
    specs = [themes.get_theme(t) for t in themes.list_theme_ids()[20:200]]
    combos = {(t["art"], t["cover_variant"], t["fonts"]["title"], t["fonts"]["body"]) for t in specs}
    assert len(combos) == len(specs)
    names = [t["name"] for t in specs]
    assert len(set(names)) == len(names)
    for a in range(len(specs)):
        for b in range(a + 1, len(specs)):
            sa, sb = specs[a], specs[b]
            diff = sum(sa["traits"][k] != sb["traits"][k] for k in sa["traits"])
            diff += (sa["art"] != sb["art"]) * 3 + (sa["cover_variant"] != sb["cover_variant"]) * 2 + (sa["fonts"] != sb["fonts"]) * 2
            assert diff >= 5, (sa["id"], sb["id"])


@pytest.mark.parametrize("key,expected", [("21", "021_paper_craft"), ("021", "021_paper_craft"), ("200", "200_electric"),
                                          ("tpl_150_apollo~emerald", "150_apollo~emerald"), ("12_pastel_playful~asl", "12_pastel_playful")])
def test_template_and_colour_aliases(key, expected):
    assert themes.resolve_theme_id(key) == expected
    assert themes.is_known_theme(key)


def test_unknown_numbers_are_not_known():
    assert not themes.is_known_theme("401") and not themes.is_known_theme("0") and not themes.is_known_theme("21~nope")


def test_catalog_has_categories_and_colours():
    cat = themes.catalog()
    assert len(cat) == 400
    keys = {k for k, *_ in themes.CATEGORIES}
    for t in cat:
        assert t["categories"] and set(t["categories"]) <= keys
        assert ("dark" in t["categories"]) == (t["mode"] == "dark")
        assert len(t["colors"]) == 10 and t["colors"][0]["key"] == t["id"]
        assert all(len(c["swatch"]) == 4 for c in t["colors"])



def test_photo_templates_are_all_different():
    specs = [themes.get_theme(t) for t in themes.list_theme_ids()[200:]]
    combos = {(t["cover_variant"], t["fonts"]["title"], t["fonts"]["body"], t["traits"]["pc"]) for t in specs}
    assert len(combos) == len(specs) == 200
    assert len({t["name"] for t in specs}) == 200
    for t in specs:
        assert "photo-mode" in t["trait_classes"] and "photo" in t["categories"]
        assert len(t["colors"]) == 10
