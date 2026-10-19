"""
HTTP-level tests for bot/webhook_app.py using aiohttp's own test client (no real
network socket, no external dependency beyond aiohttp which the project already
requires for aiogram).
"""
import base64
import hashlib
import pytest
from aiohttp.test_utils import TestClient, TestServer
from bot.webhook_app import create_webhook_app
from database import repository

CLICK_SECRET_KEY = "test-click-secret"
PAYME_SECRET_KEY = "test-payme-secret"


@pytest.fixture(autouse=True)
def provider_secrets(monkeypatch):
    monkeypatch.setattr("config.settings.CLICK_SECRET_KEY", CLICK_SECRET_KEY)
    monkeypatch.setattr("config.settings.PAYME_SECRET_KEY", PAYME_SECRET_KEY)


@pytest.fixture
async def client():
    app = create_webhook_app()
    async with TestClient(TestServer(app)) as c:
        yield c


async def _make_order(db, user_id=111, total_price=1750):
    async with db() as session:
        await repository.get_or_create_user(session, user_id, "Tester", "tester")
        order = await repository.create_presentation_order(
            session=session, user_id=user_id, topic="T", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=total_price
        )
        return order.id


def _click_sign(params, action, secret=CLICK_SECRET_KEY):
    if action == 0:
        raw = (
            str(params["click_trans_id"]) + str(params["service_id"]) + secret
            + str(params["merchant_trans_id"]) + str(params["amount"]) + str(action) + str(params["sign_time"])
        )
    else:
        raw = (
            str(params["click_trans_id"]) + str(params["service_id"]) + secret
            + str(params["merchant_trans_id"]) + str(params["merchant_prepare_id"])
            + str(params["amount"]) + str(action) + str(params["sign_time"])
        )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _payme_basic_auth():
    token = base64.b64encode(f"Paycom:{PAYME_SECRET_KEY}".encode()).decode()
    return f"Basic {token}"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_click_prepare_endpoint_end_to_end(client, patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = {
        "click_trans_id": "9001", "service_id": "20000", "merchant_trans_id": order_id,
        "amount": "1750", "action": "0", "sign_time": "2026-01-01 00:00:00",
    }
    params["sign_string"] = _click_sign(params, 0)

    resp = await client.post("/payments/click/prepare", data=params)

    assert resp.status == 200
    body = await resp.json()
    assert body["error"] == 0
    assert "merchant_prepare_id" in body


@pytest.mark.asyncio
async def test_click_complete_endpoint_marks_order_paid(client, patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prep = {
        "click_trans_id": "9002", "service_id": "20000", "merchant_trans_id": order_id,
        "amount": "1750", "action": "0", "sign_time": "2026-01-01 00:00:00",
    }
    prep["sign_string"] = _click_sign(prep, 0)
    prep_resp = await (await client.post("/payments/click/prepare", data=prep)).json()

    comp = {
        "click_trans_id": "9002", "service_id": "20000", "merchant_trans_id": order_id,
        "merchant_prepare_id": prep_resp["merchant_prepare_id"], "amount": "1750", "action": "1",
        "sign_time": "2026-01-01 00:00:01", "error": "0", "error_note": "",
    }
    comp["sign_string"] = _click_sign(comp, 1)

    resp = await client.post("/payments/click/complete", data=comp)
    body = await resp.json()

    assert body["error"] == 0
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status == "PAID"


@pytest.mark.asyncio
async def test_payme_endpoint_rejects_request_without_auth(client):
    resp = await client.post("/payments/payme", json={"jsonrpc": "2.0", "id": 1, "method": "CheckTransaction", "params": {"id": "x"}})

    assert resp.status == 200  # Payme expects HTTP 200 even for RPC-level auth errors
    body = await resp.json()
    assert body["error"]["code"] == -32504


@pytest.mark.asyncio
async def test_payme_endpoint_accepts_authorized_request_and_dispatches(client, patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)

    resp = await client.post(
        "/payments/payme",
        json={"jsonrpc": "2.0", "id": 1, "method": "CheckPerformTransaction",
              "params": {"amount": 175000, "account": {"order_id": order_id}}},
        headers={"Authorization": _payme_basic_auth()},
    )

    assert resp.status == 200
    body = await resp.json()
    assert body["result"]["allow"] is True


@pytest.mark.asyncio
async def test_payme_endpoint_rejects_malformed_json_body(client):
    resp = await client.post(
        "/payments/payme",
        data="not-json{{{",
        headers={"Authorization": _payme_basic_auth(), "Content-Type": "application/json"},
    )

    body = await resp.json()
    assert body["error"]["code"] == -32700


@pytest.mark.asyncio
async def test_full_click_flow_rejects_a_tampered_amount_over_http(client, patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = {
        "click_trans_id": "9003", "service_id": "20000", "merchant_trans_id": order_id,
        "amount": "1750", "action": "0", "sign_time": "2026-01-01 00:00:00",
    }
    params["sign_string"] = _click_sign(params, 0)
    params["amount"] = "1"  # tamper with amount AFTER signing, like a MITM would

    resp = await client.post("/payments/click/prepare", data=params)
    body = await resp.json()

    assert body["error"] == -1  # signature no longer matches the tampered amount



# ---------------------------------------------------------------------------
# Template gallery Mini App
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


async def test_webapp_select_sets_the_users_theme(monkeypatch):
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
    assert await state.get_state() == "PresentationForm:subject"
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
