import xml.etree.ElementTree as ET

import pytest

from services.deck import art, stickers, themes
from services.deck.sticker_art import ART, SUBJECTS

PAL = {"primary": "#2F6BFF", "secondary": "#13B48A", "accent": "#FFB020"}


@pytest.mark.parametrize("style", stickers.STYLES)
def test_every_sticker_renders_valid_svg_in_every_style(style):
    for name in ART:
        svg = stickers.render(name, PAL, style, 120)
        ET.fromstring(svg)
        assert "$" not in svg, (name, style)


def test_every_subject_lists_existing_stickers():
    for key, (_, names) in SUBJECTS.items():
        assert len(names) >= 8, key
        assert set(names) <= set(ART), key


@pytest.mark.parametrize("subject,expected", [
    ("Biologiya", "biology"), ("Matematika", "math"), ("Tarix", "history"), ("Informatika", "it"),
    ("Iqtisodiyot", "economics"), ("Kimyo", "chemistry"), ("История", "history"), ("Physics", "physics"),
    ("Ona tili va adabiyot", "literature"), ("Tibbiyot", "medicine"), ("Nimadir", "general"),
])
def test_subject_detection(subject, expected):
    assert stickers.detect_subject({"title_slide": {"subject": subject}}) == expected


def test_sticker_replaces_the_art_icon_badge():
    svg = art.render_art("bauhaus", {**PAL, "bg": "#fff", "bg2": "#eee", "surface": "#fff", "text": "#111"}, "leaf", "",
                         845, 1080, 1, overlay=stickers.render("atom", PAL, "diecut", 300))
    ET.fromstring(svg)
    assert "<!--B-->" not in svg and svg.count("<svg") == 2


def test_templates_have_sticker_style_and_placement():
    for tid in themes.list_theme_ids()[:200]:  # photo templates (201-400) use real photos instead
        t = themes.get_theme(tid)
        assert t["sticker_style"] in stickers.STYLES, tid
        assert t["sticker_place"] in ("corner", "cards", "both", "art"), tid


def test_build_slides_adds_subject_stickers():
    from services.deck.render import build_slides
    content = {"language": "uz", "title_slide": {"title": "Kasrlar", "subject": "Matematika"},
               "slides": [{"layout": "cards", "title": "T", "items": [{"title": "A", "text": "a", "icon": "star"}] * 3},
                          {"layout": "process", "title": "P", "steps": [{"title": "S", "text": "s"}] * 3}]}
    tid = next(t for t in themes.list_theme_ids() if themes.get_theme(t)["sticker_place"] == "both")
    slides = build_slides(content, themes.get_theme(tid))
    cards, process = slides[1], slides[2]
    assert len(cards["item_stickers"]) == 3 and all(s.startswith("<svg") for s in cards["item_stickers"])
    assert process["sticker"].startswith("<svg")
