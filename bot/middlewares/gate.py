"""
Runs before every handler (after the flood protection):
  * users blocked in the admin dashboard are ignored;
  * in maintenance mode everybody except admins gets the maintenance message (at most once a minute);
  * remembers when each user was last active (written to the database at most every 5 minutes).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from services import runtime

logger = logging.getLogger(__name__)

SEEN_EVERY = 300.0
NOTICE_EVERY = 60.0


class GateMiddleware(BaseMiddleware):
    def __init__(self):
        self._seen: Dict[int, float] = {}
        self._noticed: Dict[int, float] = {}

    @staticmethod
    def _event(event: TelegramObject):
        if isinstance(event, Update):
            return event.message or event.callback_query or event.edited_message or event.my_chat_member
        return event

    def _touch(self, user_id: int) -> None:
        now = time.monotonic()
        if now - self._seen.get(user_id, -1e9) < SEEN_EVERY:
            return
        self._seen[user_id] = now
        if len(self._seen) > 50000:
            self._seen.clear()
        asyncio.ensure_future(_write_seen(user_id))

    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: Dict[str, Any]) -> Any:
        ev = self._event(event)
        user = getattr(ev, "from_user", None)
        if user is None:
            return await handler(event, data)
        uid = user.id
        if runtime.is_admin(uid):
            self._touch(uid)
            return await handler(event, data)
        if uid in runtime.blocked_users:
            if isinstance(ev, CallbackQuery):
                try:
                    await ev.answer()
                except Exception:  # noqa: BLE001
                    pass
            return None
        self._touch(uid)
        if runtime.get_bool("maintenance"):
            now = time.monotonic()
            if now - self._noticed.get(uid, -1e9) >= NOTICE_EVERY:
                self._noticed[uid] = now
                try:
                    text = runtime.get("maintenance_text") or runtime.MAINTENANCE_TEXT
                    if isinstance(ev, CallbackQuery):
                        await ev.answer(text[:200], show_alert=True)
                    elif isinstance(ev, Message):
                        await ev.answer(text)
                except Exception:  # noqa: BLE001
                    pass
            elif isinstance(ev, CallbackQuery):
                try:
                    await ev.answer()
                except Exception:  # noqa: BLE001
                    pass
            return None
        return await handler(event, data)


async def _write_seen(user_id: int) -> None:
    from sqlalchemy import update
    from database.connection import AsyncSessionLocal
    from database.models import User
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(update(User).where(User.telegram_id == user_id)
                                  .values(last_seen_at=datetime.utcnow(), bot_blocked=False))
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.debug("last_seen not written: %s", e)
