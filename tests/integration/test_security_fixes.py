"""Regression tests for the security review: spoofed addresses, payments without an amount, closed
orders, limits when the database fails, wizard state across restarts, disk cleanup, free presentation
cap, bot price commands, /diag, the session key and initData age."""
import asyncio
import hashlib
import hmac
import json
import os
import time
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import update

from bot.admin_web import auth
from database import repository
from database.models import PresentationOrder
from services import netutil
from services.payment import orders
from tests.fixtures.fake_tezcheck import paid_event, signed_webhook
from tests.fixtures.telegram_fakes import FakeMessage, FakeUser
from tests.integration.test_tezcheck_payments import DeliveryBot, _order, _status, tc  # noqa: F401 (fixture)


def _req(xff="", remote="10.0.0.1"):
    return SimpleNamespace(headers={"X-Forwarded-For": xff} if xff else {}, remote=remote)


# ---------------------------------------------------------------------- 1. addresses and login
def test_client_ip_is_the_address_the_proxy_saw(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    # the visitor writes the first values himself; the proxy appends the real one at the end
    assert netutil.client_ip(_req("6.6.6.6, 1.2.3.4")) == "1.2.3.4"
    assert netutil.client_ip(_req("1.2.3.4")) == "1.2.3.4"
    assert netutil.client_ip(_req()) == "10.0.0.1"
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    assert netutil.client_ip(_req("6.6.6.6, 1.2.3.4")) == "10.0.0.1"


@pytest.fixture
def fresh_login(monkeypatch):
    monkeypatch.setattr("config.settings.ADMIN_PASSWORD", "right-password")
    monkeypatch.setattr("config.settings.ADMIN_LOGIN", "admin")
    auth._fails.clear()
    auth._recent_fails.clear()
    monkeypatch.setattr(auth, "_global_lock_until", 0.0)
    yield
    auth._fails.clear()
    auth._recent_fails.clear()


def test_guessing_from_many_addresses_pauses_password_sign_in(fresh_login):
    for i in range(auth.GLOBAL_MAX_FAILS + 1):
        assert not auth.check_password(f"10.1.{i // 250}.{i % 250}", "admin", "wrong")
    # every address is now refused, even with the right password, for a while
    assert auth.locked_for("192.168.9.9") > 0
    assert not auth.check_password("192.168.9.9", "admin", "right-password")


def test_flooding_the_table_does_not_unlock_a_locked_address(fresh_login, monkeypatch):
    monkeypatch.setattr(auth, "GLOBAL_MAX_FAILS", 10 ** 9)
    monkeypatch.setattr(auth, "MAX_TRACKED", 50)
    for _ in range(auth.MAX_FAILS):
        auth.check_password("1.1.1.1", "admin", "wrong")
    assert auth.locked_for("1.1.1.1") > 0
    for i in range(200):
        auth.check_password(f"2.2.{i // 250}.{i % 250}", "admin", "wrong")
    assert auth.locked_for("1.1.1.1") > 0 and len(auth._fails) <= 60


# ---------------------------------------------------------------------- 2-3. payments
async def test_a_paid_bill_without_an_amount_is_held(tc, patched_handlers_db, tmp_path):  # noqa: F811
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    bill = (await _status(patched_handlers_db, oid)).bill_id
    tc.pay(bill)
    tc.bills[bill]["payment"].pop("amount_minor")
    result, _ = await orders.check_bill(oid)
    assert result == "unknown" and (await _status(patched_handlers_db, oid)).status != "PAID"


async def test_a_webhook_without_an_amount_does_not_pay(tc, patched_handlers_db, tmp_path):  # noqa: F811
    from bot.webhook_app import create_webhook_app
    oid = await _order(patched_handlers_db, tmp_path)
    event = paid_event(oid, "link_X", 3500)
    event["data"].pop("amount_minor")
    async with TestClient(TestServer(create_webhook_app(DeliveryBot()))) as client:
        raw, h = signed_webhook(event)
        r = await client.post("/payments/tezcheck/webhook", data=raw, headers=h)
        assert (await r.json())["result"] == "ignored"
    assert (await _status(patched_handlers_db, oid)).status != "PAID"


@pytest.mark.parametrize("closed", ["CANCELLED", "REFUNDED"])
async def test_closed_orders_are_not_reopened_by_a_payment(closed, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    async with patched_handlers_db() as s:
        await s.execute(update(PresentationOrder).where(PresentationOrder.id == oid).values(status=closed))
        await s.commit()
    assert not await orders.mark_paid(oid, by="TEZCHECK", amount=3500)
    assert (await _status(patched_handlers_db, oid)).status == closed
    # the admin's explicit «mark paid» still can
    assert await orders.mark_paid(oid, by="ADMIN", amount=3500, reopen=True)
    assert (await _status(patched_handlers_db, oid)).status == "PAID"


async def test_bill_locks_do_not_pile_up(tc, patched_handlers_db, tmp_path):  # noqa: F811
    oid = await _order(patched_handlers_db, tmp_path)
    await asyncio.gather(*(orders.get_payment_link(oid, 111) for _ in range(5)))
    assert len(tc.bills) == 1 and oid not in orders._bill_locks


# ---------------------------------------------------------------------- 4. limits fail closed
async def test_limits_refuse_when_the_database_fails(patched_handlers_db, monkeypatch):
    from services import guard, credits

    async def no_free(*a, **k):
        return False

    class Broken:
        async def __aenter__(self):
            raise RuntimeError("database is down")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(credits, "usable", no_free)
    monkeypatch.setattr(guard, "creation_open", lambda: True)
    monkeypatch.setattr(guard, "AsyncSessionLocal", lambda: Broken())
    block = await guard.check(424242)
    assert block is not None and block.reason == "error"


# ---------------------------------------------------------------------- 5. wizard state survives a restart
async def test_wizard_state_survives_a_restart(patched_handlers_db, monkeypatch):
    from bot import fsm_storage
    monkeypatch.setattr(fsm_storage, "AsyncSessionLocal", patched_handlers_db)
    key = StorageKey(bot_id=1, chat_id=5, user_id=5)
    first = fsm_storage.DbStorage()
    await first.set_state(key, "PresentationForm:topic")
    await first.update_data(key, {"subject": "Tarix", "outline": {"slides": [{"title": "Kirish"}]}})

    after_restart = fsm_storage.DbStorage()          # a new process: empty memory
    assert await after_restart.get_state(key) == "PresentationForm:topic"
    assert (await after_restart.get_data(key))["outline"]["slides"][0]["title"] == "Kirish"
    await after_restart.set_state(key, None)
    await after_restart.set_data(key, {})
    assert await fsm_storage.DbStorage().get_state(key) is None


# ---------------------------------------------------------------------- 6. disk cleanup
async def test_old_order_folders_are_deleted_only_when_rebuildable(patched_handlers_db, monkeypatch, tmp_path):
    from services import storage_cleanup
    monkeypatch.setattr(storage_cleanup, "AsyncSessionLocal", patched_handlers_db)
    root = tmp_path / "storage"
    old_ok, old_keep, fresh = (root / n for n in ("11111111-1111-1111-1111-111111111111",
                                                  "22222222-2222-2222-2222-222222222222",
                                                  "33333333-3333-3333-3333-333333333333"))
    for d in (old_ok, old_keep, fresh):
        d.mkdir(parents=True)
        (d / "presentation.pdf").write_bytes(b"x")
    (root / "gallery_cache").mkdir()
    async with patched_handlers_db() as s:
        await repository.get_or_create_user(s, 7, "A", "a")
        await repository.create_presentation_order(s, 7, "T", "S", 10, "05_nature_organic", 3500,
                                                   pdf_path=str(old_ok / "presentation.pdf"), content_json="{}")
        await repository.create_presentation_order(s, 7, "T", "S", 10, "05_nature_organic", 3500,
                                                   pdf_path=str(old_keep / "presentation.pdf"))
    week_ago = time.time() - 7 * 86400
    for d in (old_ok, old_keep, root / "gallery_cache"):
        os.utime(d, (week_ago, week_ago))
    assert await storage_cleanup.run_once(str(root)) == 1
    assert not old_ok.exists()                    # rebuildable from the database
    assert old_keep.exists()                      # no saved content: its files are still needed
    assert fresh.exists() and (root / "gallery_cache").exists()


# ---------------------------------------------------------------------- 8. free presentations per day
async def test_free_presentations_stop_at_the_daily_cap(patched_handlers_db, monkeypatch):
    from services import credits, runtime
    monkeypatch.setattr(credits, "_free_today_cache", [0.0, 0])
    monkeypatch.setitem(runtime._values, "free_trial", "1")
    monkeypatch.setitem(runtime._values, "free_daily_cap", "0")
    assert await credits.usable(9999, 5)           # a brand-new account gets the trial
    monkeypatch.setitem(runtime._values, "free_daily_cap", "2")
    async with patched_handlers_db() as s:
        await repository.get_or_create_user(s, 8, "B", "b")
        for _ in range(2):
            o = await repository.create_presentation_order(s, 8, "T", "S", 5, "05_nature_organic", 0)
            await s.execute(update(PresentationOrder).where(PresentationOrder.id == o.id).values(paid_by=credits.TRIAL))
        await s.commit()
    monkeypatch.setattr(credits, "_free_today_cache", [0.0, 0])
    assert not await credits.usable(9999, 5)       # two made today: the trial waits for tomorrow


# ---------------------------------------------------------------------- 9. bot price commands
@pytest.mark.parametrize("text,ok", [("/setprice 0", False), ("/setprice 50", False), ("/setprice 350", True),
                                     ("/setminslides 70", False), ("/setmaxslides 2", False)])
async def test_price_commands_are_checked(text, ok, monkeypatch, patched_handlers_db):
    from bot.handlers import admin as admin_module
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text=text, from_user=FakeUser(id=8371155553))
    cmd = {"/setprice": admin_module.cmd_set_price, "/setminslides": admin_module.cmd_set_min_slides,
           "/setmaxslides": admin_module.cmd_set_max_slides}[text.split()[0]]
    await cmd(message)
    answer = message.calls_for("answer")[-1]["text"]
    assert answer.startswith("✅") == ok, answer


async def test_min_slides_cannot_pass_max(monkeypatch, patched_handlers_db):
    from bot.handlers import admin as admin_module
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    await admin_module.cmd_set_max_slides(FakeMessage(text="/setmaxslides 10", from_user=FakeUser(id=8371155553)))
    m = FakeMessage(text="/setminslides 12", from_user=FakeUser(id=8371155553))
    await admin_module.cmd_set_min_slides(m)
    assert "katta" in m.calls_for("answer")[-1]["text"]


# ---------------------------------------------------------------------- 10-12
async def test_diag_is_for_admins_only(patched_handlers_db):
    from bot.webhook_app import create_webhook_app
    async with TestClient(TestServer(create_webhook_app())) as client:
        r = await client.get("/diag", allow_redirects=False)
        assert r.status == 302 and r.headers["Location"] == "/admin/diag"
        r = await client.get("/admin/diag", allow_redirects=False)
        assert r.status == 302 and r.headers["Location"] == "/admin/login"


async def test_session_key_is_random_and_not_the_bot_token(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.ADMIN_SECRET", "")
    monkeypatch.setattr(auth, "_generated_secret", b"")
    monkeypatch.setattr("database.connection.AsyncSessionLocal", patched_handlers_db)
    await auth.init_secret()
    key = auth._secret()
    from config import settings
    assert len(key) >= 64 and settings.BOT_TOKEN.encode() not in key
    assert key != hashlib.sha256(("slidelab-admin:" + (settings.BOT_TOKEN or "")).encode()).digest()
    monkeypatch.setattr(auth, "_generated_secret", b"")
    await auth.init_secret()                       # the same key after a restart: sessions survive it
    assert auth._secret() == key


def _init_data(token: str, age: int) -> str:
    pairs = {"auth_date": str(int(time.time()) - age), "user": json.dumps({"id": 5})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_mini_app_data_expires_after_two_hours():
    from services.webapp_auth import validate_init_data
    assert validate_init_data(_init_data("123:abc", 3600), "123:abc")
    assert validate_init_data(_init_data("123:abc", 3 * 3600), "123:abc") is None
