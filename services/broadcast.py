"""
Messages to many users from the admin dashboard.

A broadcast is stored in the database and sent by one background task at ~20 messages per
second (Telegram allows about 30). Users who blocked the bot are marked (bot_blocked) and skipped
next time; Telegram's "retry after" answers are respected.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import exists, func, select, update

from database.connection import AsyncSessionLocal
from database.models import Broadcast, PresentationOrder, User

logger = logging.getLogger(__name__)

RATE = 20  # messages per second
SEGMENTS = {
    "all": "Hammaga",
    "unpaid": "Namuna yaratib, to‘lamaganlar",
    "paid": "To‘lov qilganlar",
    "idle": "7 kundan beri faol emas",
    "ru": "Rus tilidagilar",
}

_tasks: Dict[int, asyncio.Task] = {}
_stop: set = set()


def _segment_filter(segment: str):
    base = [User.is_blocked.is_(False), User.bot_blocked.is_(False)]
    has_order = exists().where(PresentationOrder.user_id == User.telegram_id)
    has_paid = exists().where(PresentationOrder.user_id == User.telegram_id, PresentationOrder.status == "PAID")
    if segment == "unpaid":
        base += [has_order, ~has_paid]
    elif segment == "paid":
        base += [has_paid]
    elif segment == "idle":
        edge = datetime.utcnow() - timedelta(days=7)
        base += [(User.last_seen_at.is_(None)) | (User.last_seen_at < edge)]
    elif segment == "ru":
        base += [User.language == "ru"]
    return base


async def segment_counts() -> Dict[str, int]:
    out = {}
    async with AsyncSessionLocal() as session:
        for key in SEGMENTS:
            out[key] = (await session.execute(select(func.count()).select_from(User).where(*_segment_filter(key)))).scalar() or 0
    return out


async def recipients(segment: str) -> List[int]:
    async with AsyncSessionLocal() as session:
        return list((await session.execute(select(User.telegram_id).where(*_segment_filter(segment))
                                           .order_by(User.telegram_id))).scalars().all())


def _markup(button_text: Optional[str], button_url: Optional[str]):
    if not button_text or not button_url:
        return None
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    url = button_url if button_url.startswith(("http://", "https://", "tg://")) else "https://" + button_url
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text[:64], url=url)]])


async def send_one(bot, chat_id: int, text: str, photo_path: Optional[str], button_text: Optional[str],
                   button_url: Optional[str], photo_cache: Dict[str, str]) -> str:
    """"ok", "blocked" (the user blocked the bot or deleted the account) or "failed"."""
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
    from aiogram.types import FSInputFile
    markup = _markup(button_text, button_url)
    for _ in range(3):
        try:
            if photo_path:
                photo = photo_cache.get("id") or FSInputFile(photo_path)
                msg = await bot.send_photo(chat_id, photo, caption=text[:1024], parse_mode="HTML", reply_markup=markup)
                if not photo_cache.get("id") and getattr(msg, "photo", None):
                    photo_cache["id"] = msg.photo[-1].file_id  # later messages reuse the uploaded photo
            else:
                await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup,
                                       disable_web_page_preview=True)
            return "ok"
        except TelegramRetryAfter as e:
            await asyncio.sleep(float(getattr(e, "retry_after", 5)) + 0.5)
        except TelegramForbiddenError:
            return "blocked"
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower() or "user is deactivated" in str(e).lower():
                return "blocked"
            logger.info("broadcast to %s failed: %s", chat_id, e)
            return "failed"
        except Exception as e:  # noqa: BLE001
            logger.info("broadcast to %s failed: %s", chat_id, e)
            return "failed"
    return "failed"


async def create(text: str, segment: str, photo_path: Optional[str], button_text: str, button_url: str,
                 admin_id: Optional[int]) -> int:
    async with AsyncSessionLocal() as session:
        b = Broadcast(text=text, segment=segment if segment in SEGMENTS else "all", photo_path=photo_path,
                      button_text=button_text or None, button_url=button_url or None, created_by=admin_id)
        session.add(b)
        await session.commit()
        return b.id


async def run(bot, broadcast_id: int) -> None:
    async with AsyncSessionLocal() as session:
        b = await session.get(Broadcast, broadcast_id)
        if not b:
            return
        text, photo, bt, bu, segment = b.text, b.photo_path, b.button_text, b.button_url, b.segment
    ids = await recipients(segment)
    async with AsyncSessionLocal() as session:
        await session.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(status="sending", total=len(ids)))
        await session.commit()
    sent = failed = blocked = 0
    blocked_ids: List[int] = []
    photo_cache: Dict[str, str] = {}
    status = "done"
    for i, uid in enumerate(ids):
        if broadcast_id in _stop:
            status = "stopped"
            break
        r = await send_one(bot, uid, text, photo, bt, bu, photo_cache)
        if r == "ok":
            sent += 1
        elif r == "blocked":
            blocked += 1
            blocked_ids.append(uid)
        else:
            failed += 1
        if (i + 1) % 25 == 0 or i + 1 == len(ids):
            async with AsyncSessionLocal() as session:
                await session.execute(update(Broadcast).where(Broadcast.id == broadcast_id)
                                      .values(sent=sent, failed=failed, blocked=blocked))
                if blocked_ids:
                    await session.execute(update(User).where(User.telegram_id.in_(blocked_ids)).values(bot_blocked=True))
                    blocked_ids = []
                await session.commit()
        await asyncio.sleep(1 / RATE)
    async with AsyncSessionLocal() as session:
        await session.execute(update(Broadcast).where(Broadcast.id == broadcast_id).values(
            status=status, sent=sent, failed=failed, blocked=blocked, finished_at=datetime.utcnow()))
        if blocked_ids:
            await session.execute(update(User).where(User.telegram_id.in_(blocked_ids)).values(bot_blocked=True))
        await session.commit()
    _stop.discard(broadcast_id)
    logger.info("broadcast %s %s: %d sent, %d blocked, %d failed", broadcast_id, status, sent, blocked, failed)


def start(bot, broadcast_id: int) -> None:
    task = asyncio.ensure_future(run(bot, broadcast_id))
    _tasks[broadcast_id] = task
    task.add_done_callback(lambda t: _tasks.pop(broadcast_id, None))


def stop(broadcast_id: int) -> None:
    _stop.add(broadcast_id)


def running() -> List[int]:
    return [k for k, t in _tasks.items() if not t.done()]
