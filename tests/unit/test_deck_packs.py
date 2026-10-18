import xml.etree.ElementTree as ET

import pytest

from services.deck import packs, themes

PAL = {"bg": "#FFF8F0", "bg2": "#F2E6D8", "surface": "#FFFFFF", "text": "#1E1B18", "muted": "#666666",
       "primary": "#2F6BFF", "secondary": "#13B48A", "accent": "#FFB020", "ink": "#101318"}


@pytest.mark.parametrize("name", list(packs.PACKS))
@pytest.mark.parametrize("kind", ["cover", "cover-mirror", "content"])
def test_every_pack_renders_valid_svg(name, kind):
    ET.fromstring(packs.pack_svg(name, PAL, kind, seed=3))


def test_packs_are_spread_over_templates():
    used = [themes.get_theme(t).get("pack", "") for t in themes.list_theme_ids()[20:]]
    assert set(packs.PACKS) <= set(used)
    assert used.count("") <= len(used) // 4
