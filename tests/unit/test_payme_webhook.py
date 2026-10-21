"""
Tests for services/payment/payme_webhook.py against Payme's documented Merchant
API JSON-RPC shapes (see module docstring for the protocol reference and the
caveat that this has not been exercised against Payme's real sandbox).
"""
import base64
import pytest
from services.payment import payme_webhook
from database import repository

PAYME_SECRET_KEY = "test-payme-secret"


@pytest.fixture(autouse=True)
def payme_secret(monkeypatch):
    monkeypatch.setattr("config.settings.PAYME_SECRET_KEY", PAYME_SECRET_KEY)


def _basic_auth(login="Paycom", key=PAYME_SECRET_KEY):
    token = base64.b64encode(f"{login}:{key}".encode()).decode()
    return f"Basic {token}"


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


def _rpc(method, params, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_verify_auth_header_accepts_correct_credentials():
    assert payme_webhook.verify_auth_header(_basic_auth()) is True


def test_verify_auth_header_rejects_wrong_key():
    assert payme_webhook.verify_auth_header(_basic_auth(key="wrong-key")) is False


def test_verify_auth_header_rejects_wrong_login():
    assert payme_webhook.verify_auth_header(_basic_auth(login="NotPaycom")) is False


def test_verify_auth_header_rejects_missing_header():
    assert payme_webhook.verify_auth_header(None) is False


def test_verify_auth_header_rejects_malformed_header():
    assert payme_webhook.verify_auth_header("Bearer sometoken") is False
    assert payme_webhook.verify_auth_header("Basic not-valid-base64!!!") is False


def test_verify_auth_header_fails_closed_when_secret_unconfigured(monkeypatch):
    monkeypatch.setattr("config.settings.PAYME_SECRET_KEY", "")
    assert payme_webhook.verify_auth_header(_basic_auth(key="")) is False


# ---------------------------------------------------------------------------
# dispatch() routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_unknown_method_returns_method_not_found():
    resp = await payme_webhook.dispatch(_rpc("NotAMethod", {}))
    assert resp["error"]["code"] == payme_webhook.ERR_METHOD_NOT_FOUND
    assert resp["id"] == 1


# ---------------------------------------------------------------------------
# CheckPerformTransaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_perform_transaction_allows_valid_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await payme_webhook.dispatch(_rpc("CheckPerformTransaction", {
        "amount": 175000, "account": {"order_id": order_id}
    }))
    assert resp["result"]["allow"] is True


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_wrong_amount(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await payme_webhook.dispatch(_rpc("CheckPerformTransaction", {
        "amount": 1, "account": {"order_id": order_id}
    }))
    assert resp["error"]["code"] == payme_webhook.ERR_INVALID_AMOUNT


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_unknown_account(patched_handlers_db):
    resp = await payme_webhook.dispatch(_rpc("CheckPerformTransaction", {
        "amount": 175000, "account": {"order_id": "does-not-exist"}
    }))
    assert resp["error"]["code"] == payme_webhook.ERR_ACCOUNT_NOT_FOUND
    assert resp["error"]["data"] == "order_id"


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_missing_account_field(patched_handlers_db):
    resp = await payme_webhook.dispatch(_rpc("CheckPerformTransaction", {"amount": 175000, "account": {}}))
    assert resp["error"]["code"] == payme_webhook.ERR_ACCOUNT_NOT_FOUND


@pytest.mark.asyncio
async def test_check_perform_transaction_rejects_already_paid_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750, status="PAID")
    resp = await payme_webhook.dispatch(_rpc("CheckPerformTransaction", {
        "amount": 175000, "account": {"order_id": order_id}
    }))
    assert resp["error"]["code"] == payme_webhook.ERR_CANT_PERFORM


# ---------------------------------------------------------------------------
# CreateTransaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transaction_succeeds_and_stores_state_created(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-1", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))
    assert resp["result"]["state"] == payme_webhook.STATE_CREATED
    assert isinstance(resp["result"]["create_time"], int)


@pytest.mark.asyncio
async def test_create_transaction_is_idempotent_for_the_same_payme_id(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    params = {"id": "payme-tx-2", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}}

    resp1 = await payme_webhook.dispatch(_rpc("CreateTransaction", params))
    resp2 = await payme_webhook.dispatch(_rpc("CreateTransaction", params))

    assert resp1["result"] == resp2["result"]


@pytest.mark.asyncio
async def test_create_transaction_rejects_wrong_amount(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    resp = await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-3", "time": 1700000000000, "amount": 1, "account": {"order_id": order_id}
    }))
    assert resp["error"]["code"] == payme_webhook.ERR_INVALID_AMOUNT


@pytest.mark.asyncio
async def test_create_transaction_rejects_already_paid_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750, status="PAID")
    resp = await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-4", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))
    assert resp["error"]["code"] == payme_webhook.ERR_CANT_PERFORM


# ---------------------------------------------------------------------------
# PerformTransaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_perform_transaction_marks_order_paid(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-5", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp = await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-5"}))

    assert resp["result"]["state"] == payme_webhook.STATE_PERFORMED
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status == "PAID"


@pytest.mark.asyncio
async def test_perform_transaction_is_idempotent(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-6", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp1 = await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-6"}))
    resp2 = await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-6"}))

    assert resp1["result"] == resp2["result"]


@pytest.mark.asyncio
async def test_perform_transaction_rejects_unknown_id(patched_handlers_db):
    resp = await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "does-not-exist"}))
    assert resp["error"]["code"] == payme_webhook.ERR_TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_perform_transaction_rejects_a_cancelled_transaction(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-7", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))
    await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "payme-tx-7", "reason": 3}))

    resp = await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-7"}))
    assert resp["error"]["code"] == payme_webhook.ERR_CANT_PERFORM


# ---------------------------------------------------------------------------
# CancelTransaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_before_perform_sets_state_minus_one_and_cancels_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-8", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp = await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "payme-tx-8", "reason": 3}))

    assert resp["result"]["state"] == payme_webhook.STATE_CANCELLED_UNPERFORMED
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    assert order.status == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_after_perform_sets_state_minus_two_and_leaves_order_paid(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-9", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))
    await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-9"}))

    resp = await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "payme-tx-9", "reason": 5}))

    assert resp["result"]["state"] == payme_webhook.STATE_CANCELLED_PERFORMED
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
    # A post-payment cancel (refund) is a business decision, not auto-revoked --
    # files were already delivered. Order intentionally stays PAID for manual review.
    assert order.status == "PAID"


@pytest.mark.asyncio
async def test_cancel_transaction_is_idempotent(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-10", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp1 = await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "payme-tx-10", "reason": 3}))
    resp2 = await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "payme-tx-10", "reason": 1}))

    assert resp1["result"] == resp2["result"]  # second cancel does not change the recorded reason/time


@pytest.mark.asyncio
async def test_cancel_transaction_rejects_unknown_id(patched_handlers_db):
    resp = await payme_webhook.dispatch(_rpc("CancelTransaction", {"id": "does-not-exist", "reason": 1}))
    assert resp["error"]["code"] == payme_webhook.ERR_TRANSACTION_NOT_FOUND


# ---------------------------------------------------------------------------
# CheckTransaction / GetStatement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_transaction_reports_full_lifecycle(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-11", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))
    await payme_webhook.dispatch(_rpc("PerformTransaction", {"id": "payme-tx-11"}))

    resp = await payme_webhook.dispatch(_rpc("CheckTransaction", {"id": "payme-tx-11"}))

    assert resp["result"]["state"] == payme_webhook.STATE_PERFORMED
    assert resp["result"]["perform_time"] > 0
    assert resp["result"]["cancel_time"] == 0


@pytest.mark.asyncio
async def test_check_transaction_rejects_unknown_id(patched_handlers_db):
    resp = await payme_webhook.dispatch(_rpc("CheckTransaction", {"id": "does-not-exist"}))
    assert resp["error"]["code"] == payme_webhook.ERR_TRANSACTION_NOT_FOUND


@pytest.mark.asyncio
async def test_get_statement_returns_transactions_within_range(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-12", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp = await payme_webhook.dispatch(_rpc("GetStatement", {"from": 0, "to": 99999999999999}))

    ids = [t["id"] for t in resp["result"]["transactions"]]
    assert "payme-tx-12" in ids


@pytest.mark.asyncio
async def test_get_statement_excludes_transactions_outside_range(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, total_price=1750)
    await payme_webhook.dispatch(_rpc("CreateTransaction", {
        "id": "payme-tx-13", "time": 1700000000000, "amount": 175000, "account": {"order_id": order_id}
    }))

    resp = await payme_webhook.dispatch(_rpc("GetStatement", {"from": 1, "to": 2}))

    ids = [t["id"] for t in resp["result"]["transactions"]]
    assert "payme-tx-13" not in ids
