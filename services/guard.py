"""
Who may make a new presentation right now (every preview costs AI requests).

Checked when the wizard starts, before the AI writes anything in the background, and again when
the deck is built. Admins are never limited. All limits are dashboard settings:
  orders_mode           auto (closed while no payment system works) / open / closed
  max_unpaid_open       unpaid previews a user may have in 24 hours (pay one to make another)
  max_previews_per_day  previews per user per 24 hours (paid ones included)
  daily_preview_cap     previews per day for the whole bot (protects the AI budget)
  prefetch_mode         background writing during the wizard: paid (customers who paid before or with a
                        free presentation) / all / off
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from config import settings
from database.connection import AsyncSessionLocal
from database.models import PresentationOrder
from services import runtime

logger = logging.getLogger(__name__)

UNPAID = ("PREVIEW_READY", "WAITING_PAYMENT", "CREATED")


@dataclass
class Block:
    reason: str                    # closed, unpaid, daily, cap
    text: str
    pay_order_id: Optional[str] = None


def payments_work() -> bool:
    from services.payment.orders import payment_mode
    return payment_mode() in ("tezcheck", "legacy", "demo")


def creation_open() -> bool:
    mode = runtime.get("orders_mode", "auto")
    if mode == "open":
        return True
    if mode == "closed":
        return False
    return payments_work()


async def check(user_id: int, slide_count: Optional[int] = None) -> Optional[Block]:
    """None when the user may make a new preview, else why not. A user with a free presentation
    (first-time trial or referral bonus, see services/credits.py) may make it even while creation
    is closed and unpaid previews are waiting; slide_count (when known) must fit the free size."""
    if runtime.is_admin(user_id):
        return None
    from services import credits
    free = await credits.usable(user_id, slide_count)
    if not free and not creation_open():
        return Block("closed", "🛠 <b>Taqdimot yaratish vaqtincha to‘xtatilgan.</b>\n\n"
                               "To‘lov tizimi ulanmoqda — tez orada qayta ochamiz. Kuzatib boring!")
    now = datetime.utcnow()
    day = now - timedelta(days=1)
    try:
        async with AsyncSessionLocal() as s:
            mine = (await s.execute(select(PresentationOrder.id, PresentationOrder.status, PresentationOrder.created_at)
                                    .where(PresentationOrder.user_id == user_id, PresentationOrder.created_at >= day)
                                    .order_by(PresentationOrder.created_at.desc()))).all()
            cap = runtime.get_int("daily_preview_cap", 300)
            total_today = 0
            if cap > 0:
                total_today = (await s.execute(select(func.count()).select_from(PresentationOrder)
                                               .where(PresentationOrder.created_at >= day))).scalar() or 0
    except Exception:  # noqa: BLE001 - a database hiccup must not lock everybody out
        logger.exception("limit check failed")
        return None
    unpaid = [r for r in mine if r[1] in UNPAID]
    max_unpaid = runtime.get_int("max_unpaid_open", 2)
    if max_unpaid > 0 and len(unpaid) >= max_unpaid and not free:
        return Block("unpaid", f"💳 <b>Sizda {len(unpaid)} ta to‘lanmagan namuna bor.</b>\n\n"
                               "Yangi taqdimot yaratish uchun avvalgisini to‘lang — fayllar darhol keladi. "
                               "Yoki 24 soatdan so‘ng qayta urinib ko‘ring.", pay_order_id=unpaid[0][0])
    per_day = runtime.get_int("max_previews_per_day", int(settings.MAX_PREVIEWS_PER_DAY))
    if per_day > 0 and len(mine) >= per_day:
        return Block("daily", f"⏳ <b>Bugungi chegara: {per_day} ta taqdimot.</b>\n\nErtaga yana yaratishingiz mumkin.")
    if cap > 0 and total_today >= cap:
        logger.warning("daily preview cap reached (%d)", cap)
        return Block("cap", "⏳ <b>Bugun buyurtmalar juda ko‘p bo‘ldi.</b>\n\nIltimos, birozdan so‘ng yoki ertaga urinib ko‘ring.")
    return None


async def may_prefetch(user_id: int) -> bool:
    """Background writing costs AI requests even when the user leaves the wizard halfway."""
    mode = runtime.get("prefetch_mode", "paid")
    if mode == "off":
        return False
    if await check(user_id) is not None:
        return False
    if mode == "all" or runtime.is_admin(user_id):
        return True
    from services import credits
    if await credits.usable(user_id):  # the free first presentation should feel fast too
        return True
    try:
        async with AsyncSessionLocal() as s:
            paid = (await s.execute(select(func.count()).select_from(PresentationOrder).where(
                PresentationOrder.user_id == user_id, PresentationOrder.status == "PAID"))).scalar() or 0
    except Exception:  # noqa: BLE001
        return False
    return paid > 0
