"""
Order payments end to end (shared by the bot, the TezCheck webhook, the admin dashboard and the
reconciliation loop):

  PREVIEW_READY --(bill created)--> WAITING_PAYMENT --(paid)--> PAID --> files delivered
                                                     \\-> CANCELLED / REFUNDED

mark_paid() is atomic (only one caller can move an order to PAID), so a webhook, the
"✅ Tekshirish" button, a bill watcher and the reconciliation loop arriving together deliver the
files once. The webhook is optional: without TEZCHECK_WEBHOOK_SECRET an opened payment page is
watched (watch_bill: every 5 s while the customer pays) and the reconciliation loop runs every 30 s.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from sqlalchemy import select, update

from config import settings
from database import repository
from database.connection import AsyncSessionLocal
from database.models import PaymentTransaction, PresentationOrder, WebhookEvent
from services.payment import tezcheck

logger = logging.getLogger(__name__)

OPEN_STATES = ("PREVIEW_READY", "WAITING_PAYMENT", "CREATED")
RECONCILE_EVERY = 90          # seconds between checks of unpaid bills (in case a webhook is lost)
RECONCILE_EVERY_NO_WEBHOOK = 30  # without a webhook this loop is the safety net for every payment
RECONCILE_WINDOW = timedelta(days=3)
# Without a webhook each opened payment page is watched: checked often while the customer is paying.
WATCH_FAST = 5                # seconds between checks during the first WATCH_FAST_FOR seconds
WATCH_FAST_FOR = 15 * 60
WATCH_SLOW = 30               # then every WATCH_SLOW seconds until WATCH_FOR
WATCH_FOR = 60 * 60
WATCH_MAX = 200               # bills watched at once (the reconciliation loop covers the rest)
_watching: Dict[str, "asyncio.Future"] = {}


MIN_BILL = 1000               # so'm: TezCheck does not accept smaller bills
CLOSED_STATES = ("CANCELLED", "REFUNDED")
REDELIVER_AFTER = timedelta(minutes=2)   # a paid order still without files is sent again after this
REDELIVER_TRIES = 3
_redelivered: Dict[str, int] = {}
_bill_locks: Dict[str, list] = {}      # order -> [lock, number of callers holding or waiting]


def payment_mode() -> str:
    """TezCheck is the only payment system: "tezcheck" when it is configured, otherwise "off"
    (nobody gets files without paying, except free presentations and the admin dashboard)."""
    return "tezcheck" if tezcheck.is_configured() else "off"


def webhook_enabled() -> bool:
    """TezCheck webhooks are accepted only with TEZCHECK_WEBHOOK_SECRET; without it payments are
    found by asking TezCheck (watch_bill + the reconciliation loop)."""
    return bool((settings.TEZCHECK_WEBHOOK_SECRET or "").strip())


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
    Returns (url, "") or (None, reason) where reason is "paid", "not_found", "denied", "closed"
    (cancelled / refunded order), "off" (TezCheck not configured), "amount" (below MIN_BILL) or "error"."""
    if payment_mode() != "tezcheck":
        return None, "off"
    # one bill at a time per order: two quick presses must not both create one
    entry = _bill_locks.setdefault(order_id, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            return await _payment_link(order_id, user_id, bot_username)
    finally:
        entry[1] -= 1
        if entry[1] <= 0 and _bill_locks.get(order_id) is entry:
            _bill_locks.pop(order_id, None)   # nobody holds or waits: the dict does not grow forever


async def _payment_link(order_id: str, user_id: int, bot_username: str) -> Tuple[Optional[str], str]:
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order:
        return None, "not_found"
    if order.user_id != user_id:
        return None, "denied"
    if order.status == "PAID":
        return None, "paid"
    if order.status in CLOSED_STATES:
        return None, "closed"
    if (order.total_price or 0) < MIN_BILL:
        logger.error("order %s: price %s is below TezCheck's minimum %s", order_id, order.total_price, MIN_BILL)
        return None, "amount"
    if order.bill_id and order.payment_url and (order.bill_expires_at is None or order.bill_expires_at > datetime.utcnow()):
        return order.payment_url, ""
    if order.bill_id:
        # the old bill expired: it may have been paid just before that, so never bill twice
        result, st = await check_bill(order_id)
        if result in ("paid", "already"):
            return None, "paid"
        if result in ("unknown", "error") or (st is not None and st.payment_state == "processing"):
            return None, "pending" if result != "error" else "error"
    async with AsyncSessionLocal() as session:
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
                    provider: str = "", payment_id: str = "", reopen: bool = False) -> bool:
    """Moves an order to PAID once. True only for the call that actually did it.
    A cancelled or refunded order is never reopened by a payment event (a late or repeated event after
    a refund must not hand out the files again); only an admin's explicit «mark paid» (reopen=True) can."""
    blocked = ("PAID",) if reopen else ("PAID",) + CLOSED_STATES
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            update(PresentationOrder)
            .where(PresentationOrder.id == order_id, PresentationOrder.status.notin_(blocked))
            .values(status="PAID", paid_at=datetime.utcnow(), paid_by=by, paid_amount=amount, fee_amount=fee,
                    payment_provider=provider or None))
        changed = (res.rowcount or 0) > 0
        if changed:
            await session.execute(
                update(PaymentTransaction)
                .where(PaymentTransaction.order_id == order_id, PaymentTransaction.status == "WAITING_PAYMENT")
                .values(status="PAID", state=2))
        await session.commit()
    if not changed and not reopen:
        async with AsyncSessionLocal() as session:
            status = (await session.execute(select(PresentationOrder.status)
                                            .where(PresentationOrder.id == order_id))).scalar_one_or_none()
        if status in CLOSED_STATES:
            logger.error("order %s is %s but a payment arrived (%s %s %s, %s so'm): check it in the "
                         "dashboard and mark it paid or refund it", order_id, status, by, provider, payment_id, amount)
    if changed:
        logger.info("order %s paid (%s %s %s)", order_id, by, provider, payment_id)
        from services import credits
        await credits.on_order_paid(order_id, by)  # the customer's inviter gets the referral bonus
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
        if st.amount is None:
            # paid, but TezCheck did not say how much: hold the order (never deliver without a known sum)
            logger.error("order %s: TezCheck reports it paid without an amount — held for a manual check", order_id)
            return "unknown", st
        if st.amount < order.total_price:
            logger.error("order %s: paid %s < price %s — not accepted", order_id, st.amount, order.total_price)
            return "failed", st
        ok = await mark_paid(order_id, by="TEZCHECK", amount=st.amount, fee=st.fee, provider=st.provider)
        return ("paid" if ok else "already"), st
    if st.unknown:
        return "unknown", st
    if st.payment_state in ("failed", "canceled", "expired"):
        return "failed", st
    return "waiting", st


# ---------------------------------------------------------------------- watching a bill
def watch_bill(order_id: str, deliver: Callable[[str], Awaitable[Any]],
               notify: Optional[Callable[[str], Awaitable[Any]]] = None) -> bool:
    """Starts asking TezCheck about one order's bill in the background until it is paid (then
    deliver(order_id)), cancelled/expired or WATCH_FOR runs out. notify(text) tells the customer
    about a failed payment (once). False when the bill is already watched or too many are."""
    if payment_mode() != "tezcheck":
        return False
    task = _watching.get(order_id)
    if task is not None and not task.done():
        return False
    if len(_watching) >= WATCH_MAX:
        return False
    task = asyncio.ensure_future(_watch(order_id, deliver, notify))
    _watching[order_id] = task
    task.add_done_callback(lambda t: _watching.pop(order_id, None) if _watching.get(order_id) is t else None)
    return True


async def _watch(order_id: str, deliver, notify) -> None:
    started = asyncio.get_running_loop().time()
    told_failed = False
    while True:
        elapsed = asyncio.get_running_loop().time() - started
        if elapsed >= WATCH_FOR:
            return
        await asyncio.sleep(WATCH_FAST if elapsed < WATCH_FAST_FOR else WATCH_SLOW)
        try:
            result, st = await check_bill(order_id)
        except Exception:  # noqa: BLE001
            logger.exception("watching the bill of %s failed", order_id)
            continue
        if result == "paid":
            try:
                await deliver(order_id)
            except Exception:  # noqa: BLE001
                logger.exception("delivery of %s failed", order_id)
            return
        if result == "already":  # paid and delivered by the button / reconciliation
            return
        if st is not None and st.state in ("canceled", "cancelled", "expired"):
            return
        if result == "failed" and not told_failed and notify is not None:
            told_failed = True  # the customer may try again on the same page: keep watching
            try:
                await notify("❌ To‘lov o‘tmadi" + (f" ({st.problem})" if st and st.problem else "") +
                             ". To‘lov sahifasida qaytadan urinib ko‘ring.")
            except Exception:  # noqa: BLE001
                pass


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
        if amount is None or amount < order.total_price:
            logger.error("order %s: webhook amount %s (price %s) — not accepted", order.id, amount, order.total_price)
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
    """PDF and PPTX (a referat: PDF and DOCX) of an order, rebuilt from the saved content if the
    server lost them (redeploy)."""
    if getattr(order, "kind", None) == "referat":
        return await _referat_files(order)
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


async def _referat_files(order) -> Tuple[Optional[str], Optional[str]]:
    from services.referat import builder
    storage = os.path.dirname(order.pdf_path or order.pptx_path or "") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", order.id)
    saved_path = os.path.join(storage, builder.SAVE_NAME)
    if not os.path.exists(saved_path) and order.content_json:
        try:
            saved = json.loads(order.content_json).get("referat")
        except ValueError:
            saved = None
        if saved:
            os.makedirs(storage, exist_ok=True)
            with open(saved_path, "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False)
    try:
        res = await builder.ensure_files(storage)
    except Exception:  # noqa: BLE001
        logger.exception("referat files for order %s could not be built", order.id)
        return None, None
    if (order.pdf_path or "") != res.pdf_path or (order.pptx_path or "") != res.docx_path:
        async with AsyncSessionLocal() as session:
            await session.execute(update(PresentationOrder).where(PresentationOrder.id == order.id)
                                  .values(pdf_path=res.pdf_path, pptx_path=res.docx_path))
            await session.commit()
    return ((res.pdf_path if os.path.exists(res.pdf_path) else None),
            (res.docx_path if res.docx_path and os.path.exists(res.docx_path) else None))


def content_for_db(content: Dict[str, Any], theme_key: Any) -> str:
    return json.dumps({"content": content, "theme": theme_key}, ensure_ascii=False)


# ---------------------------------------------------------------------- reconciliation
async def reconcile_once(deliver) -> int:
    """Checks unpaid bills of the last days (a lost webhook or a restart must not lose a sale) and
    sends the files again for paid orders whose delivery failed. Bills that expired long ago (they
    can no longer be paid) and bills a watcher is already asking about are skipped."""
    if payment_mode() != "tezcheck":
        return 0
    now = datetime.utcnow()
    since = now - RECONCILE_WINDOW
    async with AsyncSessionLocal() as session:
        ids = (await session.execute(select(PresentationOrder.id).where(
            PresentationOrder.status == "WAITING_PAYMENT", PresentationOrder.bill_id.isnot(None),
            PresentationOrder.created_at >= since,
            (PresentationOrder.bill_expires_at.is_(None)) | (PresentationOrder.bill_expires_at >= now - timedelta(minutes=10)))
            .order_by(PresentationOrder.created_at.desc()).limit(100))).scalars().all()
        undelivered = (await session.execute(select(PresentationOrder.id).where(
            PresentationOrder.status == "PAID", PresentationOrder.paid_by == "TEZCHECK",
            PresentationOrder.delivered_at.is_(None), PresentationOrder.paid_at >= since,
            PresentationOrder.paid_at <= now - REDELIVER_AFTER).limit(20))).scalars().all()
    paid = 0
    for oid in ids:
        if oid in _watching:
            continue
        result, _ = await check_bill(oid)
        if result == "paid":
            paid += 1
            try:
                await deliver(oid)
            except Exception:  # noqa: BLE001
                logger.exception("delivery of %s failed", oid)
        await asyncio.sleep(0.2)
    for oid in [k for k in _redelivered if k not in undelivered]:
        _redelivered.pop(oid, None)      # delivered or older than the window: the counter is not needed
    for oid in undelivered:
        if _redelivered.get(oid, 0) >= REDELIVER_TRIES:
            continue
        _redelivered[oid] = _redelivered.get(oid, 0) + 1
        logger.warning("order %s is paid but its files were not delivered: try %d", oid, _redelivered[oid])
        try:
            await deliver(oid)
        except Exception:  # noqa: BLE001
            logger.exception("delivery of %s failed", oid)
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
        await asyncio.sleep(RECONCILE_EVERY if webhook_enabled() else RECONCILE_EVERY_NO_WEBHOOK)
