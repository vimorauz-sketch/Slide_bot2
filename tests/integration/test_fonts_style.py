"""Fonts and text colour chosen by the user after the template."""
import json
import os
import zipfile

import pytest

from bot.handlers import style
from bot.states.forms import PresentationForm
from services.deck import fonts, themes
from services.presentation import theme_key_from_data
from tests.fixtures.telegram_fakes import FakeCallbackQuery, FakeFSMContext, FakeUser


def _key(name):
    return next(e for e in fonts.library_fonts() if e["id"] == name)["key"]


def test_library_is_big_and_every_font_writes_uzbek():
    lib = fonts.library_fonts()
    assert len(lib) >= 150
    assert {e["category"] for e in lib} == set(fonts.library_categories())
    for e in lib:
        assert all(os.path.exists(p) for p in fonts.font_paths(e["key"]))
    assert sum(e["cyrillic"] for e in lib) >= 60


def test_style_changes_fonts_pptx_names_and_text_colour():
    t = themes.get_theme({"base": "05_nature_organic",
                          "fonts": {"title": _key("lobster"), "body": _key("ptserif")}, "text_color": "#7C2D12"})
    assert t["fonts"]["title"] == "g:lobster" and t["pptx_fonts"] == {"title": "Lobster", "body": "PT Serif"}
    assert t["palette"]["text"] == "#7C2D12" and "--title-color:#7C2D12 !important" in t["css"]
    css = fonts.font_face_css([t["fonts"]["title"], t["fonts"]["body"]])
    assert '"Lobster"' in css and 'format("truetype")' in css
    # unknown fonts and bad colours are ignored
    t2 = themes.get_theme({"base": "05_nature_organic", "fonts": {"title": "g:nope"}, "text_color": "red;}"})
    assert t2["fonts"]["title"] == themes.get_theme("05_nature_organic")["fonts"]["title"]
    assert "red;}" not in t2["css"]


def test_theme_key_keeps_plain_templates_and_swaps_latin_only_fonts_for_russian():
    assert theme_key_from_data({"template_id": "05_nature_organic"}) == "05_nature_organic"
    latin_only = next(e for e in fonts.library_fonts() if not e["cyrillic"])
    key = theme_key_from_data({"template_id": "05_nature_organic", "font_title": latin_only["key"], "language": "ru"})
    assert key["base"] == "05_nature_organic"
    assert fonts.library_font(key["fonts"]["title"])["cyrillic"]
    key_uz = theme_key_from_data({"template_id": "05_nature_organic", "font_title": latin_only["key"], "language": "uz"})
    assert key_uz["fonts"]["title"] == latin_only["key"]


def test_only_readable_colours_are_offered():
    light = [c[3] for c in style.allowed_colors({"template_id": "02_clean_academic"})]
    dark = [c[3] for c in style.allowed_colors({"template_id": "01_midnight_tech"})]
    assert "#FFFFFF" not in light and "#111827" in light
    assert "#FFFFFF" in dark and "#111827" not in dark


@pytest.mark.asyncio
async def test_picking_fonts_and_colour_then_continuing(monkeypatch):
    async def no_preview(data):
        return None
    monkeypatch.setattr(style, "preview_path", no_preview)
    state = FakeFSMContext()
    await state.set_state(PresentationForm.style)
    await state.update_data(template_id="05_nature_organic")
    user = FakeUser(id=5)

    cb = FakeCallbackQuery(data="st_f:t", from_user=user)
    await style.font_categories(cb, state)
    cb = FakeCallbackQuery(data="st_c:t:hand:0", from_user=user)
    await style.font_list(cb, state)
    sent = cb.message.calls_for("edit_text") or cb.bot.sent_messages or cb.message.calls_for("answer_photo")
    assert sent
    idx = next(i for i, e in enumerate(fonts.library_fonts()) if e["id"] == "caveat")
    await style.font_selected(FakeCallbackQuery(data=f"st_s:t:{idx}", from_user=user), state)
    body_idx = next(i for i, e in enumerate(fonts.library_fonts()) if e["id"] == "lora")
    await style.font_selected(FakeCallbackQuery(data=f"st_s:b:{body_idx}", from_user=user), state)
    i = next(i for i, c in enumerate(style.COLORS) if c[2] == "#1E3A8A")
    await style.color_selected(FakeCallbackQuery(data=f"st_k:{i}", from_user=user), state)
    data = await state.get_data()
    assert (data["font_title"], data["font_body"], data["text_color"]) == ("g:caveat", "g:lora", "#1E3A8A")
    assert "Caveat" in style.menu_caption(data) and "Lora" in style.menu_caption(data)

    go = FakeCallbackQuery(data="st_go", from_user=user)
    await style.style_continue(go, state)
    assert await state.get_state() == PresentationForm.subject

    await style.style_reset(FakeCallbackQuery(data="st_reset", from_user=user), state)
    assert not (await state.get_data()).get("font_title")


@pytest.mark.asyncio
async def test_old_style_buttons_do_nothing_outside_the_wizard():
    state = FakeFSMContext()
    cb = FakeCallbackQuery(data="st_k:0", from_user=FakeUser(id=6))
    await style.color_selected(cb, state)
    assert not (await state.get_data()).get("text_color")


@pytest.mark.asyncio
async def test_customer_gets_installable_fonts_with_the_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bot import delivery
    monkeypatch.setattr(delivery, "FONT_CACHE", str(tmp_path / "cache"))
    theme = {"base": "05_nature_organic", "fonts": {"title": _key("ptserif"), "body": _key("ptserif")}}
    order = SimpleNamespace(id="o1", content_json=json.dumps({"content": {}, "theme": theme}),
                            pptx_path=str(tmp_path / "o1" / "presentation.pptx"), pdf_path=None)
    pack = await delivery.font_pack(order)
    assert pack.endswith(".zip") and os.path.exists(pack)
    names = zipfile.ZipFile(pack).namelist()
    assert "PTSerif-Regular.ttf" in names and "PTSerif-Bold.ttf" in names and "O'RNATISH.txt" in names
    plain = SimpleNamespace(id="o2", content_json=json.dumps({"content": {}, "theme": "05_nature_organic"}),
                            pptx_path=None, pdf_path=None)
    assert await delivery.font_pack(plain) == ""
