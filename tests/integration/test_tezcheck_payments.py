"""TezCheck payments end to end against an in-process imitation of the API:
bill creation, the check button, the signed webhook, duplicates, test money, reconciliation."""
import asyncio
import os
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from bot.handlers import payment as payment_handlers
from database import repository
from services.payment import orders, tezcheck
from tests.fixtures.fake_tezcheck import (API_KEY, DESK, WEBHOOK_SECRET, FakeTezCheck, paid_event,
                                          signed_webhook)
from tests.fixtures.telegram_fakes import FakeBot, FakeCallbackQuery, FakeUser


@pytest.fixture
async def tc(monkeypatch):
    fake = FakeTezCheck()
    server = TestServer(fake.app())
    await server.start_server()
    monkeypatch.setattr("config.settings.TEZCHECK_API_URL", str(server.make_url("/api/merchant/v1")))
    monkeypatch.setattr("config.settings.TEZCHECK_API_KEY", API_KEY)
    monkeypatch.setattr("config.settings.TEZCHECK_CASH_DESK_CODE", DESK)
    monkeypatch.setattr("config.settings.TEZCHECK_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr("config.settings.TEZCHECK_ACCEPT_TEST", False)
    yield fake
    await server.close()


async def _order(db, tmp_path, user_id=111, price=3500):
    async with db() as s:
        await repository.get_or_create_user(s, user_id, "Ali Valiyev", "ali")
        d = tmp_path / "storage" / f"o{user_id}"
        d.mkdir(parents=True)
        for name in ("presentation.pdf", "presentation.pptx"):
            (d / name).write_bytes(b"x")
        o = await repository.create_presentation_order(s, user_id, "Biosfera", "Biologiya", 10, "05_nature_organic",
                                                       price, pptx_path=str(d / "presentation.pptx"),
                                                       pdf_path=str(d / "presentation.pdf"))
        return o.id


class DeliveryBot(FakeBot):
    async def me(self):
        return type("Me", (), {"username": "SlideLabBot"})()


async def _status(db, oid):
    async with db() as s:
        return await repository.get_presentation_order(s, oid)


# ---------------------------------------------------------------------- client
async def test_bill_request_has_key_desk_tiyin_and_idempotency(tc, patched_handlers_db, tmp_path):
    data = await tezcheck.TezCheckClient().create_bill(3500, "SlideLab: Biosfera", "ORD-1", return_url="https://t.me/x")
    req = tc.requests[-1]
    assert req["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert req["headers"]["X-Cash-Desk-Code"] == DESK
    assert req["headers"]["Idempotency-Key"] == "order-ORD-1"
    assert b'"amount_minor": 350000' in req["body"]  # 3 500 so'm = 350 000 tiyin
    assert data["payment_url"].startswith("https://pay.tezcheck.uz/")


async def test_signed_requests_are_accepted(tc, monkeypatch):
    tc.require_signature = True
    monkeypatch.setattr("config.settings.TEZCHECK_SIGN_REQUESTS", True)
    me = await tezcheck.TezCheckClient().me()
    assert me["cash_desk"]["code"] == DESK
    assert tc.requests[-1]["headers"]["X-TezCheck-Signature"].startswith("v1=")


async def test_api_errors_carry_the_code(tc):
    with pytest.raises(tezcheck.TezCheckError) as e:
        await tezcheck.TezCheckClient().create_bill(5, "x" * 3, "ORD-2")   # below 1 000 so'm
    assert e.value.code == "payment_link.amount_out_of_range" and e.value.status == 422


# ---------------------------------------------------------------------- webhook signature
def test_webhook_signature_rules():
    raw, h = signed_webhook({"id": "oev_1"})
    args = (raw, h["X-Checkout-Timestamp"], h["X-Checkout-Delivery"])
    assert tezcheck.verify_webhook(*args, h["X-Checkout-Signature"], secret=WEBHOOK_SECRET)
    assert not tezcheck.verify_webhook(*args, h["X-Checkout-Signature"], secret="wbs_OTHER")
    assert not tezcheck.verify_webhook(raw + b" ", *args[1:], h["X-Checkout-Signature"], secret=WEBHOOK_SECRET)
    # during a secret rotation the header has two signatures: either may match
    assert tezcheck.verify_webhook(*args, "v1=deadbeef," + h["X-Checkout-Signature"], secret=WEBHOOK_SECRET)
    # a future "v2=" is not silently accepted, and an old request cannot be replayed
    assert not tezcheck.verify_webhook(*args, h["X-Checkout-Signature"].replace("v1=", "v2="), secret=WEBHOOK_SECRET)
    raw2, h2 = signed_webhook({"id": "oev_1"}, ts=int(time.time()) - 600)
    assert not tezcheck.verify_webhook(raw2, h2["X-Checkout-Timestamp"], h2["X-Checkout-Delivery"],
                                       h2["X-Checkout-Signature"], secret=WEBHOOK_SECRET)


# ---------------------------------------------------------------------- bot flow
async def test_pay_button_creates_one_bill_and_check_delivers_the_files(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    bot = DeliveryBot()
    cb = FakeCallbackQuery(data=f"tc_pay_{oid}", from_user=FakeUser(id=111))
    cb.bot = cb.message.bot = bot
    await payment_handlers.tezcheck_pay(cb)
    o = await _status(patched_handlers_db, oid)
    assert o.status == "WAITING_PAYMENT" and o.bill_id and o.payment_url
    markup = cb.message.calls_for("edit_reply_markup")[0]["reply_markup"]
    assert markup.inline_keyboard[0][0].url == o.payment_url
    assert b"start=paid_" in tc.requests[-1]["body"]  # the customer comes back to the bot after paying

    await payment_handlers.tezcheck_pay(cb)  # pressed again: the same bill
    assert len(tc.bills) == 1

    chk = FakeCallbackQuery(data=f"tc_chk_{oid}", from_user=FakeUser(id=111))
    chk.bot = chk.message.bot = bot
    await payment_handlers.tezcheck_check(chk)
    assert "hali kelmadi" in chk.message.calls_for("answer")[-1]["text"]

    tc.pay(o.bill_id)
    await payment_handlers.tezcheck_check(chk)
    o = await _status(patched_handlers_db, oid)
    assert o.status == "PAID" and o.paid_by == "TEZCHECK" and o.paid_amount == 3500 and o.fee_amount == 35
    docs = [m for m in bot.sent_messages if "document" in m]
    assert len(docs) == 2 and o.delivered_at is not None


async def test_someone_else_cannot_pay_or_check_an_order(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    cb = FakeCallbackQuery(data=f"tc_pay_{oid}", from_user=FakeUser(id=999))
    await payment_handlers.tezcheck_pay(cb)
    assert "sizniki emas" in cb.message.calls_for("answer")[-1]["text"]
    assert tc.bills == {}


async def test_test_money_is_not_accepted_unless_allowed(tc, patched_handlers_db, tmp_path, monkeypatch):
    oid = await _order(patched_handlers_db, tmp_path)
    url, _ = await orders.get_payment_link(oid, 111)
    bill = (await _status(patched_handlers_db, oid)).bill_id
    tc.pay(bill, environment="test")
    result, _ = await orders.check_bill(oid)
    assert result == "waiting" and (await _status(patched_handlers_db, oid)).status != "PAID"
    monkeypatch.setattr("config.settings.TEZCHECK_ACCEPT_TEST", True)
    result, _ = await orders.check_bill(oid)
    assert result == "paid"


async def test_unknown_outcome_is_never_treated_as_failure(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    tc.pay((await _status(patched_handlers_db, oid)).bill_id, state="processing", unknown=True)
    result, st = await orders.check_bill(oid)
    assert result == "unknown" and st.unknown


async def test_mark_paid_happens_once_under_concurrency(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    results = await asyncio.gather(*(orders.mark_paid(oid, by="TEZCHECK") for _ in range(5)))
    assert results.count(True) == 1


# ---------------------------------------------------------------------- webhook endpoint
async def test_webhook_marks_paid_delivers_and_ignores_duplicates(tc, patched_handlers_db, tmp_path):
    from bot.webhook_app import create_webhook_app
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    bill = (await _status(patched_handlers_db, oid)).bill_id
    bot = DeliveryBot()
    async with TestClient(TestServer(create_webhook_app(bot))) as client:
        raw, h = signed_webhook(paid_event(oid, bill, 3500))
        r = await client.post("/payments/tezcheck/webhook", data=raw, headers=h)
        assert r.status == 200 and (await r.json())["result"] == "paid"
        for _ in range(50):
            if any("document" in m for m in bot.sent_messages):
                break
            await asyncio.sleep(0.05)
        assert sum(1 for m in bot.sent_messages if "document" in m) == 2
        # the same event again (TezCheck retries when our 200 was lost): nothing happens twice
        r = await client.post("/payments/tezcheck/webhook", data=raw, headers=h)
        assert (await r.json())["result"] == "duplicate"
        # bad signature
        r = await client.post("/payments/tezcheck/webhook", data=raw + b" ", headers=h)
        assert r.status == 401
    o = await _status(patched_handlers_db, oid)
    assert o.status == "PAID" and o.payment_provider == "click"


async def test_webhook_with_too_little_money_or_test_money_does_not_pay(tc, patched_handlers_db, tmp_path):
    from bot.webhook_app import create_webhook_app
    oid = await _order(patched_handlers_db, tmp_path)
    async with TestClient(TestServer(create_webhook_app(DeliveryBot()))) as client:
        raw, h = signed_webhook(paid_event(oid, "link_X", 1000, event_id="oev_A"))
        assert (await (await client.post("/payments/tezcheck/webhook", data=raw, headers=h)).json())["result"] == "ignored"
        raw, h = signed_webhook(paid_event(oid, "link_X", 3500, environment="test", event_id="oev_B"))
        assert (await (await client.post("/payments/tezcheck/webhook", data=raw, headers=h)).json())["result"] == "ignored"
    assert (await _status(patched_handlers_db, oid)).status != "PAID"


async def test_reconciliation_finds_payments_without_a_webhook(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    tc.pay((await _status(patched_handlers_db, oid)).bill_id)
    delivered = []

    async def deliver(o):
        delivered.append(o)
    assert await orders.reconcile_once(deliver) == 1
    assert delivered == [oid]
    assert await orders.reconcile_once(deliver) == 0


async def _until(cond, tries=200):
    for _ in range(tries):
        if cond():
            return True
        await asyncio.sleep(0.02)
    return False


@pytest.fixture
def fast_watch(monkeypatch):
    monkeypatch.setattr(orders, "WATCH_FAST", 0.01)
    monkeypatch.setattr(orders, "WATCH_SLOW", 0.01)
    monkeypatch.setattr("config.settings.TEZCHECK_WEBHOOK_SECRET", "")  # no webhook at all
    yield
    for t in list(orders._watching.values()):
        t.cancel()


async def test_without_a_webhook_the_pay_button_watches_the_bill_and_delivers(tc, patched_handlers_db, tmp_path,
                                                                              fast_watch):
    assert not orders.webhook_enabled()
    oid = await _order(patched_handlers_db, tmp_path)
    bot = DeliveryBot()
    cb = FakeCallbackQuery(data=f"tc_pay_{oid}", from_user=FakeUser(id=111))
    cb.bot = cb.message.bot = bot
    await payment_handlers.tezcheck_pay(cb)
    assert oid in orders._watching
    await payment_handlers.tezcheck_pay(cb)  # pressed again: still one watcher
    assert len(orders._watching) == 1

    tc.pay((await _status(patched_handlers_db, oid)).bill_id)
    assert await _until(lambda: sum(1 for m in bot.sent_messages if "document" in m) == 2)
    assert await _until(lambda: oid not in orders._watching)
    o = await _status(patched_handlers_db, oid)
    assert o.status == "PAID" and o.paid_by == "TEZCHECK"


async def test_watcher_tells_about_a_failed_payment_once_and_keeps_watching(tc, patched_handlers_db, tmp_path,
                                                                            fast_watch):
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    bill = (await _status(patched_handlers_db, oid)).bill_id
    told, delivered = [], []

    async def deliver(o):
        delivered.append(o)

    async def notify(text):
        told.append(text)
    tc.pay(bill, state="failed")
    assert orders.watch_bill(oid, deliver, notify)
    assert await _until(lambda: told)
    await asyncio.sleep(0.1)
    assert len(told) == 1 and "o‘tmadi" in told[0]
    tc.pay(bill)  # second try on the same page succeeds
    assert await _until(lambda: delivered == [oid])


async def test_watcher_stops_after_its_time(tc, patched_handlers_db, tmp_path, fast_watch, monkeypatch):
    monkeypatch.setattr(orders, "WATCH_FOR", 0.05)
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    assert orders.watch_bill(oid, lambda o: asyncio.sleep(0))
    assert await _until(lambda: oid not in orders._watching)


async def test_files_are_rebuilt_from_the_database_after_a_redeploy(patched_handlers_db, tmp_path, monkeypatch):
    """storage/ is wiped on every redeploy: the deck saved in the order is enough to make the files again."""
    from services import ai_service
    from services.payment.orders import content_for_db, order_files
    content = ai_service.generate_mock_presentation({"topic": "Suv aylanishi", "slide_count": 5})
    async with patched_handlers_db() as s:
        await repository.get_or_create_user(s, 5, "A", "a")
        o = await repository.create_presentation_order(
            s, 5, "Suv aylanishi", "Geografiya", 5, "05_nature_organic", 1750,
            pptx_path=str(tmp_path / "gone" / "presentation.pptx"), pdf_path=str(tmp_path / "gone" / "presentation.pdf"),
            content_json=content_for_db(content, "05_nature_organic"))
    pdf, pptx = await order_files(o)
    assert pdf and pptx and os.path.getsize(pdf) > 1000 and os.path.getsize(pptx) > 1000


# ---------------------------------------------------------------------- protection against mistakes
async def _set(db, oid, **values):
    from sqlalchemy import update
    from database.models import PresentationOrder
    async with db() as s:
        await s.execute(update(PresentationOrder).where(PresentationOrder.id == oid).values(**values))
        await s.commit()


async def test_two_quick_presses_make_one_bill(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    urls = await asyncio.gather(*(orders.get_payment_link(oid, 111) for _ in range(5)))
    assert len({u for u, _ in urls}) == 1 and len(tc.bills) == 1


async def test_an_expired_bill_paid_in_time_is_not_billed_again(tc, patched_handlers_db, tmp_path):
    from datetime import datetime, timedelta
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    tc.pay((await _status(patched_handlers_db, oid)).bill_id)
    await _set(patched_handlers_db, oid, bill_expires_at=datetime.utcnow() - timedelta(minutes=1))
    url, reason = await orders.get_payment_link(oid, 111)
    assert url is None and reason == "paid" and len(tc.bills) == 1
    assert (await _status(patched_handlers_db, oid)).status == "PAID"


async def test_an_expired_unpaid_bill_gets_a_new_one(tc, patched_handlers_db, tmp_path):
    from datetime import datetime, timedelta
    oid = await _order(patched_handlers_db, tmp_path)
    first, _ = await orders.get_payment_link(oid, 111)
    await _set(patched_handlers_db, oid, bill_expires_at=datetime.utcnow() - timedelta(minutes=1))
    second, reason = await orders.get_payment_link(oid, 111)
    assert reason == "" and second != first and len(tc.bills) == 2


async def test_cancelled_orders_and_tiny_prices_are_never_billed(tc, patched_handlers_db, tmp_path):
    oid = await _order(patched_handlers_db, tmp_path)
    await _set(patched_handlers_db, oid, status="CANCELLED")
    assert await orders.get_payment_link(oid, 111) == (None, "closed")
    cheap = await _order(patched_handlers_db, tmp_path, user_id=112, price=500)
    assert await orders.get_payment_link(cheap, 112) == (None, "amount")
    assert tc.bills == {}


async def test_tezcheck_down_gives_a_friendly_answer(tc, patched_handlers_db, tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.TEZCHECK_API_URL", "http://127.0.0.1:9/api")  # nothing listens
    oid = await _order(patched_handlers_db, tmp_path)
    cb = FakeCallbackQuery(data=f"tc_pay_{oid}", from_user=FakeUser(id=111))
    cb.bot = cb.message.bot = DeliveryBot()
    await payment_handlers.tezcheck_pay(cb)
    assert "ulanib bo‘lmadi" in cb.message.calls_for("answer")[-1]["text"]
    assert await orders.check_bill(oid) == ("no_bill", None)


async def test_paid_but_undelivered_orders_are_sent_again_a_few_times(tc, patched_handlers_db, tmp_path):
    from datetime import datetime, timedelta
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.mark_paid(oid, by="TEZCHECK", amount=3500)
    await _set(patched_handlers_db, oid, paid_at=datetime.utcnow() - timedelta(minutes=5))
    orders._redelivered.clear()
    tries = []

    async def deliver(o):
        tries.append(o)
    for _ in range(5):
        await orders.reconcile_once(deliver)
    assert tries == [oid] * orders.REDELIVER_TRIES


async def test_reconciliation_skips_bills_that_expired_long_ago(tc, patched_handlers_db, tmp_path):
    from datetime import datetime, timedelta
    oid = await _order(patched_handlers_db, tmp_path)
    await orders.get_payment_link(oid, 111)
    await _set(patched_handlers_db, oid, bill_expires_at=datetime.utcnow() - timedelta(hours=1))
    before = len(tc.requests)
    await orders.reconcile_once(lambda o: asyncio.sleep(0))
    assert len(tc.requests) == before
