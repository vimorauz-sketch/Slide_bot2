"""Sends a paid order's PDF and PPTX to the customer (after the webhook, the check button,
the reconciliation loop or an admin's "send again")."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from aiogram.types import FSInputFile
from sqlalchemy import update

from database import repository
from database.connection import AsyncSessionLocal
from database.models import PresentationOrder

logger = logging.getLogger(__name__)

PAID_NOTE = ("🎉 <b>To‘lov qabul qilindi!</b>\n\n"
             "«{topic}» taqdimotingiz tayyor — fayllar pastda.\n"
             "PowerPoint faylidagi matnlarni bemalol tahrirlashingiz mumkin.")


def file_name(topic: str, ext: str) -> str:
    """Safe download name: no / \\ : * ? " < > | characters (they break the file on Windows/phones)."""
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", topic or "")
    name = " ".join(name.split())[:40].strip() or "Taqdimot"
    return f"SlideLab_{name}.{ext}"


async def deliver_order(bot, order_id: str, *, force: bool = False, note: str = "") -> bool:
    """Sends both files once (force=True sends them again). True when they were sent."""
    from services.payment.orders import order_files

    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order or order.status != "PAID" or bot is None:
        return False
    if order.delivered_at and not force:
        return False
    try:
        await bot.send_message(order.user_id, note or PAID_NOTE.format(topic=order.topic[:120]), parse_mode="HTML")
    except Exception as e:  # noqa: BLE001 - the user may have blocked the bot
        logger.warning("order %s: user %s cannot be messaged: %s", order_id, order.user_id, e)
        return False
    pdf, pptx = await order_files(order)
    sent = False
    for path, ext, caption in ((pptx, "pptx", "📊 <b>PowerPoint (.pptx)</b> — tahrirlash mumkin"),
                               (pdf, "pdf", "📄 <b>PDF</b> — chop etish va ko‘rsatish uchun")):
        if not path:
            continue
        try:
            await bot.send_document(order.user_id, FSInputFile(path, filename=file_name(order.topic, ext)),
                                    caption=caption, parse_mode="HTML")
            sent = True
        except Exception:  # noqa: BLE001
            logger.exception("order %s: %s not sent", order_id, ext)
    if not sent:
        await bot.send_message(order.user_id, "⚠️ Fayllarni tayyorlashda muammo bo‘ldi. Admin tez orada yuboradi.")
        return False
    async with AsyncSessionLocal() as session:
        await session.execute(update(PresentationOrder).where(PresentationOrder.id == order_id)
                              .values(delivered_at=datetime.utcnow()))
        await session.commit()
    return True
