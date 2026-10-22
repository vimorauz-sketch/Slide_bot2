"""
Order payments end to end (shared by the bot, the TezCheck webhook, the admin dashboard and the
reconciliation loop):

  PREVIEW_READY --(bill created)--> WAITING_PAYMENT --(paid)--> PAID --> files delivered
                                                     \\-> CANCELLED / REFUNDED

mark_paid() is atomic (only one caller can move an order to PAID), so a webhook, the
"✅ Tekshirish" button and the reconciliation loop arriving together deliver the files once.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select, update

from config import settings
from database import repository
from database.connection import AsyncSessionLocal
from database.models import PaymentTransaction, PresentationOrder, WebhookEvent
from services.payment import tezcheck

logger = logging.getLogger(__name__)

OPEN_STATES = ("PREVIEW_READY", "WAITING_PAYMENT", "CREATED")
RECONCILE_EVERY = 90          # seconds between checks of unpaid bills (in case a webhook is lost)
RECONCILE_WINDOW = timedelta(days=3)


def payment_mode() -> str:
    """"tezcheck" when TezCheck is configured, "legacy" for the old Click/Payme code, else "demo"."""
    if tezcheck.is_configured():
        return "tezcheck"
    return "legacy" if (settings.PAYMENT_ENV or "").upper() == "PRODUCTION" else "demo"


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) - (dt.utcoffset() or timedelta(0))
    except ValueError:
        return None


# ---------------------------------------------------------------------- bills
async def get_payment_link(order_id: str, user_id: int, bot_username: str = "") -> Tuple[Optional[str], str]:
    """Payment page for an order (an existing active bill is reused).
    Returns (url, "") or (None, reason) where reason is "paid", "not_found", "denied" or "error"."""
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
        if not order:
            return None, "not_found"
        if order.user_id != user_id:
            return None, "denied"
        if order.status == "PAID":
            return None, "paid"
        now = datetime.utcnow()
        if order.bill_id and order.payment_url and (order.bill_expires_at is None or order.bill_expires_at > now) \
                and order.status != "CANCELLED":
            return order.payment_url, ""
        attempts = len([t for t in (await session.execute(select(PaymentTransaction).where(
            PaymentTransaction.order_id == order_id, PaymentTransaction.provider == "TEZCHECK"))).scalars().all()])
        amount, topic = order.total_price, order.topic
    return_url = f"https://t.me/{bot_username}?start=paid_{order_id}" if bot_username else ""
    try:
        data = await tezcheck.TezCheckClient().create_bill(
            amount, f"SlideLab: {topic[:150]}", order_id,
            description=f"Taqdimot · {order_id[:8]}", return_url=return_url,
            idempotency_key=f"order-{order_id}-{attempts + 1}")
    except tezcheck.TezCheckError as e:
        logger.error("TezCheck bill for order %s failed: %s", order_id, e)
        return None, "error"
    except Exception:  # noqa: BLE001 - network
        logger.exception("TezCheck bill for order %s failed", order_id)
        return None, "error"
    bill, url = data.get("bill") or {}, data.get("payment_url")
    if not bill.get("id") or not url:
        return None, "error"
    async with AsyncSessionLocal() as session:
        await session.execute(update(PresentationOrder).where(PresentationOrder.id == order_id).values(
            bill_id=bill["id"], payment_url=url, bill_expires_at=_parse_time(bill.get("available_until")),
            status="WAITING_PAYMENT"))
        session.add(PaymentTransaction(order_id=order_id, user_id=user_id, amount=amount, provider="TEZCHECK",
                                       provider_trans_id=bill["id"], status="WAITING_PAYMENT"))
        await session.commit()
    return url, ""


async def mark_paid(order_id: str, *, by: str, amount: Optional[int] = None, fee: Optional[int] = None,
                    provider: str = "", payment_id: str = "") -> bool:
    """Moves an order to PAID once. True only for the call that actually did it."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            update(PresentationOrder)
            .where(PresentationOrder.id == order_id, PresentationOrder.status != "PAID")
            .values(status="PAID", paid_at=datetime.utcnow(), paid_by=by, paid_amount=amount, fee_amount=fee,
                    payment_provider=provider or None))
        changed = (res.rowcount or 0) > 0
        if changed:
            await session.execute(
                update(PaymentTransaction)
                .where(PaymentTransaction.order_id == order_id, PaymentTransaction.status == "WAITING_PAYMENT")
                .values(status="PAID", state=2))
        await session.commit()
    if changed:
        logger.info("order %s paid (%s %s %s)", order_id, by, provider, payment_id)
    return changed


async def check_bill(order_id: str) -> Tuple[str, Optional[tezcheck.BillStatus]]:
    """Asks TezCheck about an order's bill. Returns (result, status) where result is
    "paid" (just became paid), "already", "waiting", "unknown", "failed", "no_bill" or "error"."""
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order:
        return "error", None
    if order.status == "PAID":
        return "already", None
    if not order.bill_id:
        return "no_bill", None
    try:
        st = tezcheck.parse_bill(await tezcheck.TezCheckClient().get_bill(order.bill_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("TezCheck check for %s failed: %s", order_id, e)
        return "error", None
    if st.accepted:
        if st.amount is not None and st.amount < order.total_price:
            logger.error("order %s: paid %s < price %s — not accepted", order_id, st.amount, order.total_price)
            return "failed", st
        ok = await mark_paid(order_id, by="TEZCHECK", amount=st.amount, fee=st.fee, provider=st.provider)
        return ("paid" if ok else "already"), st
    if st.unknown:
        return "unknown", st
    if st.payment_state in ("failed", "canceled", "expired"):
        return "failed", st
    return "waiting", st


# ---------------------------------------------------------------------- webhooks
async def handle_webhook(event: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Processes one verified webhook body. Returns (result, order_id_to_deliver_or_notify).
    result: "paid", "duplicate", "ignored", "failed", "refunded", "unknown_order"."""
    event_id = str(event.get("id") or "")
    data = event.get("data") or {}
    etype = str(event.get("type") or "")
    if not event_id:
        return "ignored", None
    async with AsyncSessionLocal() as session:
        if await session.get(WebhookEvent, event_id):
            return "duplicate", None
    result = await _process_event(etype, data, event_id)
    # remembered only after it was processed: if processing failed, TezCheck's retry runs it again
    try:
        async with AsyncSessionLocal() as session:
            session.add(WebhookEvent(id=event_id, type=etype, bill_id=str(data.get("bill_id") or "")[:64]))
            await session.commit()
    except Exception:  # noqa: BLE001 - the same event arrived twice at once: already recorded
        pass
    return result


async def _process_event(etype: str, data: Dict[str, Any], event_id: str) -> Tuple[str, Optional[str]]:
    order_id = str(data.get("external_reference") or "")
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id) if order_id else None
        if order is None and data.get("bill_id"):
            order = (await session.execute(select(PresentationOrder).where(
                PresentationOrder.bill_id == str(data["bill_id"])))).scalar_one_or_none()
    if order is None:
        logger.warning("TezCheck webhook %s for an unknown order (%s)", event_id, order_id or data.get("bill_id"))
        return "unknown_order", None

    env = data.get("environment")
    real = env == "live"
    if etype == "payment.succeeded" or data.get("state") == "succeeded":
        if not real and not settings.TEZCHECK_ACCEPT_TEST:
            logger.info("test payment for order %s ignored (TEZCHECK_ACCEPT_TEST is off)", order.id)
            return "ignored", None
        amount = tezcheck.from_minor(data.get("amount_minor"))
        if amount is not None and amount < order.total_price:
            logger.error("order %s: webhook amount %s < price %s", order.id, amount, order.total_price)
            return "ignored", None
        ok = await mark_paid(order.id, by="TEZCHECK", amount=amount, fee=tezcheck.from_minor(data.get("fee_minor")),
                             provider=str(data.get("provider_code") or ""), payment_id=str(data.get("payment_id") or ""))
        return ("paid" if ok else "duplicate"), (order.id if ok else None)
    if etype in ("payment.refunded", "payment.charged_back") and order.status == "PAID":
        async with AsyncSessionLocal() as session:
            await session.execute(update(PresentationOrder).where(PresentationOrder.id == order.id)
                                  .values(status="REFUNDED"))
            await session.commit()
        return "refunded", order.id
    problem = data.get("problem") or {}
    if etype == "payment.failed" and not problem.get("unknown_reason"):
        return "failed", order.id
    return "ignored", None


# ---------------------------------------------------------------------- files after payment
async def order_files(order) -> Tuple[Optional[str], Optional[str]]:
    """PDF and PPTX of an order, rebuilt from the saved deck if the server lost them (redeploy)."""
    from services.presentation import ensure_files
    storage = os.path.dirname(order.pdf_path or order.pptx_path or "") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", order.id)
    content_path = os.path.join(storage, "content.json")
    if not os.path.exists(content_path) and order.content_json:
        os.makedirs(storage, exist_ok=True)
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(order.content_json)
    try:
        await ensure_files(storage)
    except Exception:  # noqa: BLE001
        logger.exception("files for order %s could not be built", order.id)
    pdf = os.path.join(storage, "presentation.pdf")
    pptx = os.path.join(storage, "presentation.pptx")
    if (order.pdf_path or "") != pdf or (order.pptx_path or "") != pptx:
        async with AsyncSessionLocal() as session:
            await session.execute(update(PresentationOrder).where(PresentationOrder.id == order.id)
                                  .values(pdf_path=pdf, pptx_path=pptx))
            await session.commit()
    return (pdf if os.path.exists(pdf) else None), (pptx if os.path.exists(pptx) else None)


def content_for_db(content: Dict[str, Any], theme_key: Any) -> str:
    return json.dumps({"content": content, "theme": theme_key}, ensure_ascii=False)


# ---------------------------------------------------------------------- reconciliation
async def reconcile_once(deliver) -> int:
    """Checks unpaid bills of the last days (a lost webhook must not lose a sale)."""
    if payment_mode() != "tezcheck":
        return 0
    since = datetime.utcnow() - RECONCILE_WINDOW
    async with AsyncSessionLocal() as session:
        ids = (await session.execute(select(PresentationOrder.id).where(
            PresentationOrder.status == "WAITING_PAYMENT", PresentationOrder.bill_id.isnot(None),
            PresentationOrder.created_at >= since).order_by(PresentationOrder.created_at.desc()).limit(40))).scalars().all()
    paid = 0
    for oid in ids:
        result, _ = await check_bill(oid)
        if result == "paid":
            paid += 1
            try:
                await deliver(oid)
            except Exception:  # noqa: BLE001
                logger.exception("delivery of %s failed", oid)
        await asyncio.sleep(0.5)
    return paid


async def reconcile_loop(deliver) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            n = await reconcile_once(deliver)
            if n:
                logger.info("reconciliation: %d payment(s) found without a webhook", n)
        except Exception:  # noqa: BLE001
            logger.exception("reconciliation failed")
        await asyncio.sleep(RECONCILE_EVERY)
