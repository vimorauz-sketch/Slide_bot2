"""
Tests for services/payment/click_webhook.py against Click's documented Shop API
request/response shapes (see module docstring for the protocol reference and the
caveat that this has not been exercised against Click's real sandbox).
"""
import hashlib
import pytest
from services.payment import click_webhook
from database import repository

CLICK_SECRET_KEY = "test-click-secret"


@pytest.fixture(autouse=True)
def click_secret(monkeypatch):
    monkeypatch.setattr("config.settings.CLICK_SECRET_KEY", CLICK_SECRET_KEY)


async def _make_order(db, user_id=111, total_price=1750, status=None):
    async with db() as session:
        await repository.get_or_create_user(session, user_id, "Tester", "tester")
        order = await repository.create_presentation_order(
            session=session, user_id=user_id, topic="T", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=total_price
        )
        if status:
            await repository.update_order_status(session, order.id, status)
        return order.id


def _sign(params, action, secret=CLICK_SECRET_KEY):
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


def _prepare_params(order_id, amount, click_trans_id="1001", sign_time="2026-01-01 00:00:00"):
    p = {
        "click_trans_id": click_trans_id, "service_id": "20000", "merchant_trans_id": order_id,
        "amount": str(amount), "action": "0", "sign_time": sign_time,
    }
    p["sign_string"] = _sign(p, 0)
    return p


def _complete_params(order_id, amount, merchant_prepare_id, click_trans_id="1001",
                      sign_time="2026-01-01 00:00:01", error="0"):
    p = {
        "click_trans_id": click_trans_id, "service_id": "20000", "merchant_trans_id": order_id,
        "merchant_prepare_id": merchant_prepare_id, "amount": str(amount), "action": "1",
        "sign_time": sign_time, "error": error, "error_note": "",
    }
    p["sign_string"] = _sign(p, 1)
    return p


# ---------------------------------------------------------------------------
# Prepare
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_succeeds_with_valid_signature_and_amount(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750))

    assert resp["error"] == 0
    assert resp["click_trans_id"] == "1001"
    assert resp["merchant_trans_id"] == order_id
    assert "merchant_prepare_id" in resp


@pytest.mark.asyncio
async def test_prepare_rejects_bad_signature(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = _prepare_params(order_id, 1750)
    params["sign_string"] = "deliberately-wrong"

    resp = await click_webhook.handle_prepare(params)

    assert resp["error"] == click_webhook.ERROR_SIGN_FAILED


@pytest.mark.asyncio
async def test_prepare_rejects_when_secret_key_unconfigured(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.CLICK_SECRET_KEY", "")
    order_id = await _make_order(patched_handlers_db, total_price=1750)

    resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750))

    assert resp["error"] == click_webhook.ERROR_SIGN_FAILED


@pytest.mark.asyncio
async def test_prepare_rejects_unknown_order(patched_handlers_db):
    resp = await click_webhook.handle_prepare(_prepare_params("does-not-exist", 1750))
    assert resp["error"] == click_webhook.ERROR_ORDER_NOT_FOUND


@pytest.mark.asyncio
async def test_prepare_rejects_amount_mismatch(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await click_webhook.handle_prepare(_prepare_params(order_id, 9999))
    assert resp["error"] == click_webhook.ERROR_AMOUNT


@pytest.mark.asyncio
async def test_prepare_rejects_already_paid_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750, status="PAID")
    resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750))
    assert resp["error"] == click_webhook.ERROR_ALREADY_PAID


@pytest.mark.asyncio
async def test_prepare_rejects_wrong_action(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = _prepare_params(order_id, 1750)
    params["action"] = "1"  # Complete action sent to the Prepare handler
    resp = await click_webhook.handle_prepare(params)
    assert resp["error"] == click_webhook.ERROR_ACTION


@pytest.mark.asyncio
async def test_repeated_prepare_with_same_click_trans_id_is_idempotent(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = _prepare_params(order_id, 1750, click_trans_id="5555")

    resp1 = await click_webhook.handle_prepare(params)
    resp2 = await click_webhook.handle_prepare(params)

    assert resp1["merchant_prepare_id"] == resp2["merchant_prepare_id"]


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_marks_order_paid(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prepare_resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750, click_trans_id="2002"))

    complete_resp = await click_webhook.handle_complete(
        _complete_params(order_id, 1750, prepare_resp["merchant_prepare_id"], click_trans_id="2002")
    )

    assert complete_resp["error"] == 0
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status == "PAID"


@pytest.mark.asyncio
async def test_complete_rejects_bad_signature(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prepare_resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750, click_trans_id="2003"))

    params = _complete_params(order_id, 1750, prepare_resp["merchant_prepare_id"], click_trans_id="2003")
    params["sign_string"] = "tampered"

    resp = await click_webhook.handle_complete(params)
    assert resp["error"] == click_webhook.ERROR_SIGN_FAILED

    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status != "PAID"


@pytest.mark.asyncio
async def test_complete_with_unknown_merchant_prepare_id_is_rejected(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await click_webhook.handle_complete(_complete_params(order_id, 1750, "does-not-exist"))
    assert resp["error"] == click_webhook.ERROR_TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_complete_rejects_amount_mismatch(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prepare_resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750, click_trans_id="2004"))

    resp = await click_webhook.handle_complete(
        _complete_params(order_id, 9999, prepare_resp["merchant_prepare_id"], click_trans_id="2004")
    )
    assert resp["error"] == click_webhook.ERROR_AMOUNT

    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status != "PAID"


@pytest.mark.asyncio
async def test_complete_with_negative_click_error_cancels_without_marking_paid(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prepare_resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750, click_trans_id="2005"))

    resp = await click_webhook.handle_complete(
        _complete_params(order_id, 1750, prepare_resp["merchant_prepare_id"], click_trans_id="2005", error="-5017")
    )

    assert resp["error"] == 0  # we must still ack Click's own cancellation report
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status != "PAID"


@pytest.mark.asyncio
async def test_repeated_complete_is_idempotent(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    prepare_resp = await click_webhook.handle_prepare(_prepare_params(order_id, 1750, click_trans_id="2006"))
    complete_params = _complete_params(order_id, 1750, prepare_resp["merchant_prepare_id"], click_trans_id="2006")

    resp1 = await click_webhook.handle_complete(complete_params)
    resp2 = await click_webhook.handle_complete(complete_params)

    assert resp1["error"] == 0
    assert resp2["error"] == 0  # second call re-acks rather than erroring or double-processing


@pytest.mark.asyncio
async def test_a_different_users_order_amount_cannot_be_spoofed_via_webhook(patched_handlers_db):
    # Sanity check: the webhook trusts merchant_trans_id (our own order id) and the
    # signed amount, not any client-supplied user identity -- there is no "wrong
    # user" concept here the way there is for the Telegram-side handlers, but the
    # order's *stored* total_price must be the source of truth, not the request.
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    cheap_params = _prepare_params(order_id, 1)  # attacker tries to "pay" 1 so'm
    resp = await click_webhook.handle_prepare(cheap_params)
    assert resp["error"] == click_webhook.ERROR_AMOUNT
