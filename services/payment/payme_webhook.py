"""
Payme Merchant API webhook handler (JSON-RPC 2.0 over a single HTTPS POST endpoint).

Protocol reference: https://developer.help.paycom.uz (Merchant API).
Payme calls our endpoint for a checkout built by services/payment/providers.py
(PaymePaymentProvider.create_checkout, whose `ac.order_id` is our PresentationOrder.id).

Auth: HTTP Basic, login is the constant string "Paycom", password is PAYME_SECRET_KEY
(the merchant's secret key from the Payme Business cabinet).

NOTE: this has NOT been exercised against Payme's live/sandbox endpoints (no merchant
credentials were available while writing it) -- it is implemented strictly to the
published protocol and covered by tests that simulate Payme's documented request/response
shapes. Test against Payme's real test environment before flipping PAYMENT_ENV=PRODUCTION.
"""
import base64
import logging
import time
from typing import Any, Dict, Optional

from config import settings
from database.connection import AsyncSessionLocal
from database import repository

logger = logging.getLogger(__name__)

STATE_CREATED = 1
STATE_PERFORMED = 2
STATE_CANCELLED_UNPERFORMED = -1
STATE_CANCELLED_PERFORMED = -2

ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_CANT_CANCEL = -31007
ERR_CANT_PERFORM = -31008
ERR_ACCOUNT_NOT_FOUND = -31050
ERR_PARSE_ERROR = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_ACCESS_DENIED = -32504


class PaymeError(Exception):
    def __init__(self, code: int, message: str, data: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _now_ms() -> int:
    return int(time.time() * 1000)


def verify_auth_header(auth_header: Optional[str]) -> bool:
    if not settings.PAYME_SECRET_KEY or not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[len("Basic "):]).decode("utf-8")
        login, _, key = decoded.partition(":")
    except Exception:
        return False
    return login == "Paycom" and key == settings.PAYME_SECRET_KEY


def _rpc_error(request_id: Any, code: int, message: str, data: Optional[str] = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": {"ru": message, "uz": message, "en": message}}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _rpc_result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _get_order_for_account(session, account: Dict[str, Any]):
    order_id = (account or {}).get("order_id")
    if not order_id:
        raise PaymeError(ERR_ACCOUNT_NOT_FOUND, "order_id is required", data="order_id")
    order = await repository.get_presentation_order(session, order_id)
    if not order:
        raise PaymeError(ERR_ACCOUNT_NOT_FOUND, "Order not found", data="order_id")
    return order


async def _check_perform_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    amount = params.get("amount")
    account = params.get("account", {})
    async with AsyncSessionLocal() as session:
        order = await _get_order_for_account(session, account)
        if amount != order.total_price * 100:
            raise PaymeError(ERR_INVALID_AMOUNT, "Incorrect amount")
        if order.status == "PAID":
            raise PaymeError(ERR_CANT_PERFORM, "Order already paid")
    return {"allow": True}


async def _create_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = params.get("id")
    amount = params.get("amount")
    account = params.get("account", {})

    async with AsyncSessionLocal() as session:
        existing = await repository.get_payment_transaction_by_provider_id(session, "PAYME", payme_id)
        if existing:
            # Idempotent re-request with the same Payme transaction id: must return
            # the same result, not create a duplicate or error.
            if existing.state == STATE_CANCELLED_UNPERFORMED or existing.state == STATE_CANCELLED_PERFORMED:
                raise PaymeError(ERR_CANT_PERFORM, "Transaction was cancelled")
            return {
                "create_time": existing.provider_create_time,
                "transaction": existing.id,
                "state": existing.state,
            }

        order = await _get_order_for_account(session, account)
        if amount != order.total_price * 100:
            raise PaymeError(ERR_INVALID_AMOUNT, "Incorrect amount")
        if order.status == "PAID":
            raise PaymeError(ERR_CANT_PERFORM, "Order already paid")

        tx = await repository.create_provider_transaction(
            session, order_id=order.id, user_id=order.user_id, amount=order.total_price,
            provider="PAYME", provider_trans_id=payme_id, state=STATE_CREATED, create_time=_now_ms()
        )
    return {"create_time": tx.provider_create_time, "transaction": tx.id, "state": tx.state}


async def _perform_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = params.get("id")
    async with AsyncSessionLocal() as session:
        tx = await repository.get_payment_transaction_by_provider_id(session, "PAYME", payme_id)
        if not tx:
            raise PaymeError(ERR_TRANSACTION_NOT_FOUND, "Transaction not found")

        if tx.state == STATE_PERFORMED:
            return {"transaction": tx.id, "perform_time": tx.provider_perform_time, "state": STATE_PERFORMED}
        if tx.state != STATE_CREATED:
            raise PaymeError(ERR_CANT_PERFORM, "Transaction cannot be performed")

        perform_time = _now_ms()
        await repository.mark_transaction_performed(session, tx, perform_time)
        await repository.update_order_status(session, tx.order_id, "PAID")
    return {"transaction": tx.id, "perform_time": perform_time, "state": STATE_PERFORMED}


async def _cancel_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = params.get("id")
    reason = params.get("reason")
    async with AsyncSessionLocal() as session:
        tx = await repository.get_payment_transaction_by_provider_id(session, "PAYME", payme_id)
        if not tx:
            raise PaymeError(ERR_TRANSACTION_NOT_FOUND, "Transaction not found")

        if tx.state in (STATE_CANCELLED_UNPERFORMED, STATE_CANCELLED_PERFORMED):
            return {"transaction": tx.id, "cancel_time": tx.provider_cancel_time, "state": tx.state}

        new_state = STATE_CANCELLED_PERFORMED if tx.state == STATE_PERFORMED else STATE_CANCELLED_UNPERFORMED
        cancel_time = _now_ms()
        await repository.mark_transaction_cancelled(session, tx, cancel_time, reason, new_state)
        if new_state == STATE_CANCELLED_UNPERFORMED:
            await repository.update_order_status(session, tx.order_id, "CANCELLED")
        # new_state == STATE_CANCELLED_PERFORMED means a refund of an already-paid order --
        # left for manual review; order.status intentionally stays PAID (files were already
        # delivered) unless a human operator decides to revoke access via the admin panel.
    return {"transaction": tx.id, "cancel_time": cancel_time, "state": new_state}


async def _check_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = params.get("id")
    async with AsyncSessionLocal() as session:
        tx = await repository.get_payment_transaction_by_provider_id(session, "PAYME", payme_id)
        if not tx:
            raise PaymeError(ERR_TRANSACTION_NOT_FOUND, "Transaction not found")
    return {
        "create_time": tx.provider_create_time,
        "perform_time": tx.provider_perform_time or 0,
        "cancel_time": tx.provider_cancel_time or 0,
        "transaction": tx.id,
        "state": tx.state,
        "reason": tx.cancel_reason,
    }


async def _get_statement(params: Dict[str, Any]) -> Dict[str, Any]:
    from_ts = params.get("from")
    to_ts = params.get("to")
    async with AsyncSessionLocal() as session:
        txs = await repository.get_provider_transactions_in_range(session, "PAYME", from_ts, to_ts)
    return {
        "transactions": [
            {
                "id": tx.provider_trans_id,
                "time": tx.provider_create_time,
                "amount": tx.amount * 100,
                "account": {"order_id": tx.order_id},
                "create_time": tx.provider_create_time,
                "perform_time": tx.provider_perform_time or 0,
                "cancel_time": tx.provider_cancel_time or 0,
                "transaction": tx.id,
                "state": tx.state,
                "reason": tx.cancel_reason,
            }
            for tx in txs
        ]
    }


_METHODS = {
    "CheckPerformTransaction": _check_perform_transaction,
    "CreateTransaction": _create_transaction,
    "PerformTransaction": _perform_transaction,
    "CancelTransaction": _cancel_transaction,
    "CheckTransaction": _check_transaction,
    "GetStatement": _get_statement,
}


async def dispatch(body: Dict[str, Any]) -> Dict[str, Any]:
    request_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    handler = _METHODS.get(method)
    if not handler:
        return _rpc_error(request_id, ERR_METHOD_NOT_FOUND, "Method not found")

    try:
        result = await handler(params)
    except PaymeError as e:
        return _rpc_error(request_id, e.code, e.message, e.data)
    except Exception:
        logger.exception("Unhandled error while processing Payme method %s", method)
        return _rpc_error(request_id, -32400, "System error")

    return _rpc_result(request_id, result)
