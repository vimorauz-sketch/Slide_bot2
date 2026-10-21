"""
Click Shop API webhook handlers (Prepare / Complete).

Protocol reference: https://docs.click.uz (Shop API -> Prepare/Complete requests).
Click calls these two endpoints (as application/x-www-form-urlencoded POST) when a
user pays via a Click checkout link built by services/payment/providers.py
(ClickPaymentProvider.create_checkout, whose `transaction_param` is our
PresentationOrder.id -- Click echoes it back as `merchant_trans_id`).

Signature (MD5, lowercase hex, compared against the `sign_string` field):
  Prepare:  click_trans_id + service_id + secret_key + merchant_trans_id + amount + action + sign_time
  Complete: click_trans_id + service_id + secret_key + merchant_trans_id + merchant_prepare_id + amount + action + sign_time

NOTE: this has NOT been exercised against Click's live/sandbox endpoints (no merchant
credentials were available while writing it) -- it is implemented strictly to the
published protocol and covered by tests that simulate Click's documented request/response
shapes. Test against Click's real test environment before flipping PAYMENT_ENV=PRODUCTION.
"""
import hashlib
import logging
import time
from typing import Any, Dict

from config import settings
from database.connection import AsyncSessionLocal
from database import repository

logger = logging.getLogger(__name__)

ACTION_PREPARE = 0
ACTION_COMPLETE = 1

ERROR_SIGN_FAILED = -1
ERROR_AMOUNT = -2
ERROR_ACTION = -3
ERROR_ALREADY_PAID = -4
ERROR_ORDER_NOT_FOUND = -5
ERROR_TRANSACTION_NOT_FOUND = -6
ERROR_REQUEST_FAILED = -8
ERROR_TRANSACTION_CANCELLED = -9

AMOUNT_TOLERANCE = 0.01  # Click sends amount as a decimal string; allow for float rounding.


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_signature(params: Dict[str, Any], action: int) -> str:
    click_trans_id = str(params.get("click_trans_id", ""))
    service_id = str(params.get("service_id", ""))
    merchant_trans_id = str(params.get("merchant_trans_id", ""))
    amount = str(params.get("amount", ""))
    sign_time = str(params.get("sign_time", ""))

    if action == ACTION_PREPARE:
        raw = click_trans_id + service_id + settings.CLICK_SECRET_KEY + merchant_trans_id + amount + str(action) + sign_time
    else:
        merchant_prepare_id = str(params.get("merchant_prepare_id", ""))
        raw = (
            click_trans_id + service_id + settings.CLICK_SECRET_KEY + merchant_trans_id
            + merchant_prepare_id + amount + str(action) + sign_time
        )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _verify_signature(params: Dict[str, Any], action: int) -> bool:
    expected = _compute_signature(params, action)
    return expected == str(params.get("sign_string", ""))


def _amounts_match(sent_amount: Any, expected_uzs: int) -> bool:
    try:
        return abs(float(sent_amount) - float(expected_uzs)) <= AMOUNT_TOLERANCE
    except (TypeError, ValueError):
        return False


async def handle_prepare(params: Dict[str, Any]) -> Dict[str, Any]:
    click_trans_id = str(params.get("click_trans_id", ""))
    merchant_trans_id = str(params.get("merchant_trans_id", ""))  # our PresentationOrder.id
    base = {"click_trans_id": click_trans_id, "merchant_trans_id": merchant_trans_id}

    try:
        action = int(params.get("action"))
    except (TypeError, ValueError):
        return {**base, "error": ERROR_ACTION, "error_note": "Action not found"}
    if action != ACTION_PREPARE:
        return {**base, "error": ERROR_ACTION, "error_note": "Action not found"}

    if not settings.CLICK_SECRET_KEY or not _verify_signature(params, ACTION_PREPARE):
        return {**base, "error": ERROR_SIGN_FAILED, "error_note": "SIGN CHECK FAILED!"}

    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, merchant_trans_id)
        if not order:
            return {**base, "error": ERROR_ORDER_NOT_FOUND, "error_note": "Order not found"}

        if not _amounts_match(params.get("amount"), order.total_price):
            return {**base, "error": ERROR_AMOUNT, "error_note": "Incorrect parameter amount"}

        if order.status == "PAID":
            return {**base, "error": ERROR_ALREADY_PAID, "error_note": "Order already paid"}

        existing = await repository.get_payment_transaction_by_provider_id(session, "CLICK", click_trans_id)
        if existing:
            tx = existing
        else:
            tx = await repository.create_provider_transaction(
                session, order_id=order.id, user_id=order.user_id, amount=order.total_price,
                provider="CLICK", provider_trans_id=click_trans_id, state=1, create_time=_now_ms()
            )

    return {**base, "merchant_prepare_id": tx.id, "error": 0, "error_note": "Success"}


async def handle_complete(params: Dict[str, Any]) -> Dict[str, Any]:
    click_trans_id = str(params.get("click_trans_id", ""))
    merchant_trans_id = str(params.get("merchant_trans_id", ""))
    merchant_prepare_id = str(params.get("merchant_prepare_id", ""))
    base = {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": merchant_prepare_id,
    }

    try:
        action = int(params.get("action"))
    except (TypeError, ValueError):
        return {**base, "error": ERROR_ACTION, "error_note": "Action not found"}
    if action != ACTION_COMPLETE:
        return {**base, "error": ERROR_ACTION, "error_note": "Action not found"}

    if not settings.CLICK_SECRET_KEY or not _verify_signature(params, ACTION_COMPLETE):
        return {**base, "error": ERROR_SIGN_FAILED, "error_note": "SIGN CHECK FAILED!"}

    async with AsyncSessionLocal() as session:
        tx = await repository.get_payment_transaction(session, merchant_prepare_id)
        if not tx or tx.provider != "CLICK" or tx.provider_trans_id != click_trans_id:
            return {**base, "error": ERROR_TRANSACTION_NOT_FOUND, "error_note": "Transaction not found"}

        order = await repository.get_presentation_order(session, tx.order_id)
        if not order:
            return {**base, "error": ERROR_ORDER_NOT_FOUND, "error_note": "Order not found"}

        if tx.state == 2:
            return {**base, "error": 0, "error_note": "Success"}  # idempotent re-ack
        if tx.state in (-1, -2):
            return {**base, "error": ERROR_TRANSACTION_CANCELLED, "error_note": "Transaction cancelled"}

        try:
            click_reported_error = int(params.get("error", 0))
        except (TypeError, ValueError):
            click_reported_error = 0
        if click_reported_error < 0:
            # Click itself reports the payment failed/was cancelled on its side.
            await repository.mark_transaction_cancelled(session, tx, _now_ms(), click_reported_error, new_state=-1)
            return {**base, "error": 0, "error_note": "Success"}

        if not _amounts_match(params.get("amount"), order.total_price):
            return {**base, "error": ERROR_AMOUNT, "error_note": "Incorrect parameter amount"}

        await repository.mark_transaction_performed(session, tx, _now_ms())
        await repository.update_order_status(session, order.id, "PAID")

    return {**base, "error": 0, "error_note": "Success"}
