import xml.etree.ElementTree as ET
import pytest
from services.deck import art, charts


@pytest.mark.parametrize("ctype", ["column", "bar", "line", "donut", "pie"])
def test_chart_svgs_are_well_formed(ctype):
    svg = charts.chart_svg({"type": ctype, "labels": ["A", "B", "C"],
                            "series": [{"name": "s", "values": [3, 7.5, 1]}], "unit": "%"})
    ET.fromstring(svg)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_cycle_and_pyramid_geometry(n):
    ET.fromstring(charts.cycle_svg(n))
    levels = charts.pyramid_geometry(n)
    assert len(levels) == n and levels[0]["w"] < levels[-1]["w"]


PALETTE = {"bg": "#000000", "bg2": "#111111", "surface": "#FFFFFF", "primary": "#00FF00",
           "secondary": "#0000FF", "accent": "#FF0000", "text": "#FFFFFF"}


@pytest.mark.parametrize("style", list(art.STYLES))
def test_every_art_style_renders_valid_svg_with_and_without_badge(style):
    with_badge = art.render_art(style, PALETTE, "leaf", "", 845, 1080, 1)
    without = art.render_art(style, PALETTE, "leaf", "", 1920, 1080, 1, badge=False)
    ET.fromstring(with_badge)
    ET.fromstring(without)
    assert "<!--B-->" in with_badge and "<!--B-->" not in without


def test_art_is_deterministic():
    assert art.render_art("aurora", PALETTE, "sun", "", 800, 800, 3) == art.render_art("aurora", PALETTE, "sun", "", 800, 800, 3)
