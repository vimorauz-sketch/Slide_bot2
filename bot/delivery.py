"""Sends a paid order's PDF and PPTX to the customer (after the webhook, the check button,
the reconciliation loop or an admin's "send again")."""
from __future__ import annotations

import asyncio
import json
import logging
import os
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


FONTS_NOTE = ("🔤 <b>Shriftlar</b> — PowerPoint faylingiz siz tanlagan shriftlarda.\n"
              "Kompyuterda bir xil ko‘rinishi uchun arxivni oching va <b>.ttf</b> fayllarni o‘rnating "
              "(Windows: faylni ikki marta bosing → «Установить / Install»). PDF faylga shrift kerak emas.")
FONT_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "font_cache")
INSTALL_TXT = (
    "SlideLab — shriftlarni o'rnatish\r\n\r\n"
    "Windows: har bir .ttf faylni ikki marta bosing va \"Install\" (\"Установить\") tugmasini bosing.\r\n"
    "macOS: .ttf faylni ikki marta bosing -> \"Install Font\".\r\n"
    "So'ng PowerPoint'ni qayta oching: taqdimot siz tanlagan shriftlarda ko'rinadi.\r\n"
    "Telefonda PowerPoint o'rnatilmagan shriftni o'xshash shrift bilan ko'rsatadi; PDF faylda hammasi to'g'ri.\r\n\r\n"
    "Shriftlar SIL Open Font License / Apache License asosida bepul tarqatiladi (fonts.google.com).\r\n")


def chosen_fonts(order) -> list:
    """Library fonts the customer picked for this order (from the saved theme)."""
    try:
        theme = json.loads(order.content_json or "{}").get("theme")
    except ValueError:
        return []
    if not isinstance(theme, dict):
        return []
    from services.deck.fonts import is_library_font
    return [f for f in dict.fromkeys((theme.get("fonts") or {}).values()) if f and is_library_font(f)]


async def font_pack(order) -> str:
    """Shriftlar_....zip with the Regular and Bold TTF files of the chosen fonts ("" when none)."""
    ids = chosen_fonts(order)
    if not ids:
        return ""

    def build() -> str:
        import zipfile
        from services.deck.fonts import customer_font_files, family_name
        files = customer_font_files(ids, FONT_CACHE)
        if not files:
            return ""
        storage = os.path.dirname(order.pptx_path or order.pdf_path or "") or FONT_CACHE
        names = "_".join(family_name(i).replace(" ", "") for i in ids)[:60]
        out = os.path.join(storage, f"Shriftlar_{names}.zip")
        if not os.path.exists(out):
            os.makedirs(storage, exist_ok=True)
            with zipfile.ZipFile(out + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
                for f in files:
                    z.write(f, os.path.basename(f))
                z.writestr("O'RNATISH.txt", INSTALL_TXT)
            os.replace(out + ".tmp", out)
        return out

    try:
        return await asyncio.to_thread(build)
    except Exception:  # noqa: BLE001
        logger.exception("font pack for order %s failed", order.id)
        return ""


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
    pack = await font_pack(order)
    if pack:
        try:
            await bot.send_document(order.user_id, FSInputFile(pack, filename=os.path.basename(pack)),
                                    caption=FONTS_NOTE, parse_mode="HTML")
        except Exception:  # noqa: BLE001 - the presentation itself is already delivered
            logger.exception("order %s: font pack not sent", order_id)
    async with AsyncSessionLocal() as session:
        await session.execute(update(PresentationOrder).where(PresentationOrder.id == order_id)
                              .values(delivered_at=datetime.utcnow()))
        await session.commit()
    return True
