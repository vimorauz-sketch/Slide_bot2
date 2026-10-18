from services.deck import catalog
from services.deck.catalog import LAYOUTS, normalize_slide, is_slide_usable, downgrade_to_text_image


def test_every_layout_has_a_template_file():
    import os
    base = os.path.join(os.path.dirname(catalog.__file__), "templates", "layouts")
    for name in LAYOUTS:
        assert os.path.exists(os.path.join(base, f"{name}.j2")), name


def test_unknown_layout_falls_back_to_text_image():
    assert normalize_slide({"layout": "does-not-exist", "title": "x"})["layout"] == "text_image"


def test_legacy_layout_names_and_fields_are_mapped():
    s = normalize_slide({"layout_type": "statistics", "title": "T",
                         "stats_data": [{"value": "50%", "label": "A", "desc": "d"}, {"value": "2", "label": "B"}]})
    assert s["layout"] == "stats"
    assert s["stats"][0] == {"value": "50%", "label": "A", "text": "d"}
    s = normalize_slide({"layout_type": "conclusion", "bullet_points": ["a", "b", "c"]})
    assert s["layout"] == "summary"


def test_lists_are_clamped_to_their_maximum_and_text_trimmed():
    items = [{"title": "t" * 200, "text": "x"} for _ in range(10)]
    s = normalize_slide({"layout": "cards", "title": "T", "items": items})
    assert len(s["items"]) == LAYOUTS["cards"]["fields"]["items"]["max"]
    assert len(s["items"][0]["title"]) <= LAYOUTS["cards"]["fields"]["items"]["fields"]["title"]
    assert s["items"][0]["title"].endswith("…")


def test_chart_values_are_parsed_and_series_aligned():
    s = normalize_slide({"layout": "chart", "title": "C", "chart": {
        "type": "column", "labels": ["a", "b", "c"], "series": [{"name": "s", "values": ["1,5", "20%", "x", "9"]}]}})
    assert s["chart"]["series"][0]["values"] == [1.5, 20.0, 0.0]
    assert len(s["chart"]["labels"]) == 3
    assert is_slide_usable(s)


def test_empty_required_lists_make_a_slide_unusable_and_it_downgrades_to_text():
    s = normalize_slide({"layout": "process", "title": "P", "steps": []})
    assert not is_slide_usable(s)
    d = downgrade_to_text_image(normalize_slide({"layout": "timeline", "title": "T",
                                                 "events": [{"date": "1900", "title": "x", "text": "y"}]}))
    assert d["layout"] == "text_image" and d["bullets"]


def test_visual_string_becomes_a_photo_query():
    s = normalize_slide({"layout": "text_image", "title": "T", "visual": "green leaf"})
    assert s["visual"]["kind"] == "photo" and s["visual"]["query"] == "green leaf"


def test_catalog_prompt_lists_all_content_layouts():
    text = catalog.catalog_for_prompt()
    for name in catalog.CONTENT_LAYOUTS:
        assert f"- {name}:" in text
