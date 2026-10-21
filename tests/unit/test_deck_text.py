import pytest
from services.deck.text import fix_uzbek, clean_value, smart_quotes


@pytest.mark.parametrize("raw,expected", [
    ("o'simlik", "o‘simlik"), ("O'zbekiston", "O‘zbekiston"), ("g`alla", "g‘alla"), ("Oʻzbek", "O‘zbek"),
    ("Ta'lim", "Ta’lim"), ("sun'iy", "sun’iy"), ("maʼruza", "ma’ruza"), ("Yorug'lik", "Yorug‘lik"),
])
def test_uzbek_apostrophes_are_normalized(raw, expected):
    assert fix_uzbek(raw) == expected


def test_quotes_follow_the_language():
    assert smart_quotes('"buzilgan" havo', "uz") == "“buzilgan” havo"
    assert smart_quotes('"Война и мир"', "ru") == "«Война и мир»"


def test_clean_value_leaves_identifiers_untouched():
    v = clean_value({"layout": "text_image", "title": "o'quv", "visual": {"query": "don't", "icon": "leaf"}}, "uz")
    assert v["title"] == "o‘quv"
    assert v["visual"]["query"] == "don't"
    assert v["layout"] == "text_image"


def test_russian_text_is_not_uzbek_normalized():
    assert clean_value("don't", "ru") == "don't"
