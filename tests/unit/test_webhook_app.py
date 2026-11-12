"""
HTTP-level tests for bot/webhook_app.py using aiohttp's own test client (no real
network socket)."""
import pytest
from aiohttp.test_utils import TestClient, TestServer
from bot.webhook_app import create_webhook_app


@pytest.fixture
async def client():
    app = create_webhook_app()
    async with TestClient(TestServer(app)) as c:
        yield c




@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status == 200
    assert (await resp.json())["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/payments/click/prepare", "/payments/click/complete", "/payments/payme"])
async def test_old_click_and_payme_endpoints_are_gone(client, path):
    """TezCheck is the only payment system: nothing else may mark an order paid."""
    resp = await client.post(path, data={"amount": "1"})
    assert resp.status in (404, 405)


@pytest.mark.asyncio
async def test_tezcheck_webhook_without_a_secret_is_rejected(client):
    resp = await client.post("/payments/tezcheck/webhook", data=b"{}",
                             headers={"X-Checkout-Timestamp": "1", "X-Checkout-Signature": "v1=x"})
    assert resp.status == 401


# ---------------------------------------------------------------------------
import time as _time

from services.webapp_auth import sign_init_data, validate_init_data

_TOKEN = "123456:TEST-token"


def _init(user_id=777, **extra):
    fields = {"auth_date": str(int(_time.time())), "query_id": "Q", "user": '{"id":%d,"first_name":"T"}' % user_id}
    fields.update(extra)
    return sign_init_data(fields, _TOKEN)


def test_init_data_signature_roundtrip_and_tamper_detection():
    raw = _init(42)
    data = validate_init_data(raw, _TOKEN)
    assert data and data["user"]["id"] == 42
    assert validate_init_data(raw.replace("42", "43"), _TOKEN) is None
    assert validate_init_data(raw, "999:other") is None
    assert validate_init_data(_init(1, auth_date="1000"), _TOKEN) is None


async def test_webapp_index_and_catalog_are_served():
    async with TestClient(TestServer(create_webhook_app())) as client:
        r = await client.get("/webapp/")
        assert r.status == 200 and "Dizayn laboratoriyasi" in await r.text()
        r = await client.get("/webapp/catalog.json")
        assert r.status == 200
        assert len((await r.json())["themes"]) == 400


async def test_webapp_select_rejects_unsigned_requests():
    async with TestClient(TestServer(create_webhook_app())) as client:
        r = await client.post("/webapp/api/select", json={"init_data": "user=%7B%22id%22%3A1%7D&hash=bad", "theme": "05"})
        assert r.status == 403


async def test_webapp_select_sets_the_users_theme(monkeypatch, patched_handlers_db):
    from aiogram import Dispatcher
    from config import settings
    from tests.fixtures.telegram_fakes import FakeBot

    monkeypatch.setattr(settings, "BOT_TOKEN", _TOKEN)
    bot, dp = FakeBot(), Dispatcher()
    bot.id = 123456
    async with TestClient(TestServer(create_webhook_app(bot, dp))) as client:
        r = await client.post("/webapp/api/select", json={"init_data": _init(777), "theme": "150_apollo~emerald"})
        assert r.status == 200 and (await r.json())["ok"]
    state = dp.fsm.get_context(bot=bot, chat_id=777, user_id=777)
    assert (await state.get_data())["template_id"] == "150_apollo~emerald"
    assert await state.get_state() == "PresentationForm:topic"
    assert bot.sent_messages[0]["chat_id"] == 777


async def test_webapp_preview_route_serves_default_and_rejects_bad_keys():
    import os
    from services import gallery
    async with TestClient(TestServer(create_webhook_app())) as client:
        r = await client.get("/webapp/preview/..%2F..%2Fconfig/0.webp")
        assert r.status == 404
        r = await client.get("/webapp/preview/999_nope/0.webp")
        assert r.status == 404
        if os.path.exists(os.path.join(gallery.THUMBS_DIR, "05_nature_organic", "0.webp")):
            r = await client.get("/webapp/preview/05_nature_organic/0.webp")
            assert r.status == 200 and r.headers["Content-Type"] == "image/webp"


async def test_webapp_select_with_fonts_and_text_colour(monkeypatch, patched_handlers_db):
    from aiogram import Dispatcher
    from config import settings
    from tests.fixtures.telegram_fakes import FakeBot

    async def no_preview(data):
        return None
    from bot.handlers import style
    monkeypatch.setattr(style, "preview_path", no_preview)
    monkeypatch.setattr(settings, "BOT_TOKEN", _TOKEN)
    bot, dp = FakeBot(), Dispatcher()
    bot.id = 123456
    async with TestClient(TestServer(create_webhook_app(bot, dp))) as client:
        r = await client.post("/webapp/api/select", json={
            "init_data": _init(778), "theme": "02_clean_academic", "font_title": "g:lobster",
            "font_body": "g:nope", "text_color": "#FFFFFF"})  # unknown font and unreadable colour are dropped
        assert r.status == 200 and (await r.json())["ok"]
        r2 = await client.post("/webapp/api/select", json={
            "init_data": _init(779), "theme": "02_clean_academic", "text_color": "#1E3A8A"})
        assert r2.status == 200
    data = await dp.fsm.get_context(bot=bot, chat_id=778, user_id=778).get_data()
    assert data["font_title"] == "g:lobster" and not data.get("font_body") and not data.get("text_color")
    assert (await dp.fsm.get_context(bot=bot, chat_id=779, user_id=779).get_data())["text_color"] == "#1E3A8A"


async def test_webapp_font_list_colours_font_files_and_styled_cover():
    async with TestClient(TestServer(create_webhook_app(None, None))) as client:
        d = await (await client.get("/webapp/api/fonts")).json()
        assert len(d["fonts"]) >= 150 and len(d["colors"]) == 20 and "hand" in d["categories"]
        f = next(x for x in d["fonts"] if x["key"] == "g:lora")
        r = await client.get("/webapp/" + f["file"])
        assert r.status == 200 and len(await r.read()) > 10000
        c = await (await client.get("/webapp/api/colors/02_clean_academic")).json()
        assert "#111827" in c["colors"] and "#FFFFFF" not in c["colors"]
        assert (await client.get("/webapp/api/colors/nope")).status == 404
        r = await client.get("/webapp/styled/05_nature_organic.jpg?ft=g:caveat&c=%231E3A8A")
        assert r.status == 200 and r.headers["Content-Type"] == "image/jpeg"
        assert (await client.get("/webapp/styled/05_nature_organic.jpg?ft=g:nope")).status == 404
        assert (await client.get("/webapp/fonts/../../config.py")).status in (403, 404)


async def test_mini_app_home_lists_products_and_starts_a_wizard(monkeypatch, patched_handlers_db):
    from aiogram import Dispatcher
    from config import settings
    from tests.fixtures.telegram_fakes import FakeBot

    monkeypatch.setattr(settings, "BOT_TOKEN", _TOKEN)
    bot, dp = FakeBot(), Dispatcher()
    bot.id = 123456
    async with TestClient(TestServer(create_webhook_app(bot, dp))) as client:
        r = await client.get("/webapp/home/")
        assert r.status == 200 and "Nima tayyorlaymiz?" in await r.text()
        r = await client.post("/webapp/api/home", json={"init_data": _init(777)})
        data = await r.json()
        by_key = {p["key"]: p for p in data["products"]}
        assert by_key["pres"]["active"] and by_key["pres"]["price"] == "1 750 so‘mdan"   # 5 slides × 350
        assert by_key["referat"]["active"] and not by_key["esse"]["active"]
        assert by_key["krossvord"]["price"] == "Tez orada"

        r = await client.post("/webapp/api/start", json={"init_data": _init(777), "product": "esse"})
        assert r.status == 404                                     # not ready yet
        r = await client.post("/webapp/api/start", json={"init_data": "hash=bad", "product": "pres"})
        assert r.status == 403
        r = await client.post("/webapp/api/start", json={"init_data": _init(777), "product": "pres"})
        assert r.status == 200 and (await r.json())["ok"]
    state = dp.fsm.get_context(bot=bot, chat_id=777, user_id=777)
    assert await state.get_state() == "PresentationForm:topic"     # the wizard asks the topic in the chat
    assert "mavzusini" in bot.sent_messages[-1]["text"] and bot.sent_messages[-1]["chat_id"] == 777


async def test_mini_app_home_from_the_keyboard_button(patched_handlers_db):
    import json
    from types import SimpleNamespace
    from bot.handlers import create_pres
    from bot.states.forms import PresentationForm
    from tests.fixtures.telegram_fakes import FakeFSMContext, FakeMessage, FakeUser
    state = FakeFSMContext()
    msg = FakeMessage(text="", from_user=FakeUser(id=5))
    msg.web_app_data = SimpleNamespace(data=json.dumps({"action": "start", "product": "pres"}))
    await create_pres.process_webapp_choice(msg, state)
    assert await state.get_state() == PresentationForm.topic
    msg = FakeMessage(text="", from_user=FakeUser(id=5))
    msg.web_app_data = SimpleNamespace(data=json.dumps({"action": "start", "product": "esse"}))
    await create_pres.process_webapp_choice(msg, FakeFSMContext())
    assert any("tez orada" in t for t in [c.get("text", "") for c in msg.bot.sent_messages] +
               [c["text"] for c in msg.calls_for("answer")])


def test_main_menu_has_the_mini_app_on_top(monkeypatch):
    from bot.handlers import create_pres
    from bot.keyboards.reply import get_main_menu_keyboard
    monkeypatch.setattr(create_pres.settings, "WEBAPP_URL", "https://bot.slidelab.uz/webapp/")
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
    kb = get_main_menu_keyboard("uz")
    top = kb.keyboard[0][0]
    assert top.text == "🚀 Nima tayyorlaymiz?" and top.web_app.url == "https://bot.slidelab.uz/webapp/home/"
    monkeypatch.setattr(create_pres.settings, "WEBAPP_URL", "")
    assert get_main_menu_keyboard("uz").keyboard[0][0].text == "🎨 Presentation yaratish"
