"""
Flood protection for the bot (aiogram outer middleware on every update).

Each user has a token bucket: BURST tokens, refilled at RATE tokens per second. A message or a
button press costs 1 token (/start costs 3), so normal use is never slowed down, while scripts and
people hammering /start thousands of times are cut off:
  * an update without a token is dropped (the user gets one short notice per NOTICE_EVERY seconds);
  * a user who keeps flooding (FLOOD_BAN drops in a row) is ignored for BAN_SECONDS entirely.
Admins are never limited. The state lives in memory and is pruned, so it cannot grow without end.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

logger = logging.getLogger(__name__)

NOTICE_EVERY = 20.0   # seconds between "too fast" notices to the same user
FLOOD_BAN = 40        # dropped updates (without a pause) that lead to a temporary ban
PRUNE_EVERY = 300.0


class _Bucket:
    __slots__ = ("tokens", "stamp", "dropped", "noticed", "banned_until")

    def __init__(self, burst: float, now: float):
        self.tokens = burst
        self.stamp = now
        self.dropped = 0
        self.noticed = 0.0
        self.banned_until = 0.0


_instances: list = []


def banned_now() -> int:
    """Users ignored right now for flooding (for the dashboard)."""
    now = time.monotonic()
    return sum(1 for m in _instances for b in m.buckets.values() if b.banned_until > now)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate: float = 1.0, burst: int = 12, ban_seconds: int = 300, admins=(),
                 clock: Callable[[], float] = time.monotonic, dynamic: bool = False):
        self.dynamic = dynamic
        self.rate = max(0.05, float(rate))
        self.burst = max(3, int(burst))
        self.ban_seconds = int(ban_seconds)
        self.admins = set(admins or ())
        self.clock = clock
        self.buckets: Dict[int, _Bucket] = {}
        self._pruned = clock()
        if dynamic:
            _instances.append(self)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _user_and_event(event: TelegramObject):
        ev = event
        if isinstance(event, Update):
            ev = event.message or event.callback_query or event.edited_message or event.inline_query \
                 or event.my_chat_member or event.pre_checkout_query
        user = getattr(ev, "from_user", None)
        return (user.id if user else None), ev

    @staticmethod
    def _cost(ev) -> float:
        if isinstance(ev, Message) and (ev.text or "").startswith("/start"):
            return 3.0
        return 1.0

    def _prune(self, now: float) -> None:
        if now - self._pruned < PRUNE_EVERY:
            return
        self._pruned = now
        full = self.burst / self.rate
        for uid in [u for u, b in self.buckets.items() if now - b.stamp > full and b.banned_until < now]:
            del self.buckets[uid]

    def _refresh_limits(self) -> None:
        """Burst and ban time can be changed in the admin dashboard while the bot runs."""
        if not self.dynamic:
            return
        from services import runtime
        self.burst = max(3, runtime.get_int("throttle_burst", self.burst))
        self.ban_seconds = 60 * max(1, runtime.get_int("throttle_ban_minutes", max(1, self.ban_seconds // 60)))

    def allow(self, user_id: int, cost: float = 1.0) -> Optional[str]:
        """None if the update may pass; otherwise "notice" (tell the user once) or "drop"."""
        self._refresh_limits()
        now = self.clock()
        self._prune(now)
        b = self.buckets.get(user_id)
        if b is None:
            b = self.buckets[user_id] = _Bucket(self.burst, now)
        if b.banned_until > now:
            return "drop"
        b.tokens = min(self.burst, b.tokens + (now - b.stamp) * self.rate)
        b.stamp = now
        if b.tokens >= cost:
            b.tokens -= cost
            b.dropped = 0
            return None
        b.dropped += 1
        if b.dropped >= FLOOD_BAN:
            b.banned_until = now + self.ban_seconds
            b.dropped = 0
            logger.warning("user %s is flooding the bot: ignored for %d s", user_id, self.ban_seconds)
            return "ban"
        if now - b.noticed >= NOTICE_EVERY:
            b.noticed = now
            return "notice"
        return "drop"

    # ------------------------------------------------------------------ middleware
    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: Dict[str, Any]) -> Any:
        user_id, ev = self._user_and_event(event)
        if self.dynamic and user_id is not None:
            from services import runtime
            if runtime.is_admin(user_id):
                return await handler(event, data)
        if user_id is None or user_id in self.admins:
            return await handler(event, data)
        verdict = self.allow(user_id, self._cost(ev))
        if verdict is None:
            return await handler(event, data)
        try:
            if isinstance(ev, CallbackQuery):
                await ev.answer("⏳ Juda tez! Biroz kuting." if verdict != "drop" else None)
            elif isinstance(ev, Message) and verdict == "notice":
                await ev.answer("⏳ Juda ko‘p so‘rov yuboryapsiz. Iltimos, bir necha soniya kuting.")
            elif isinstance(ev, Message) and verdict == "ban":
                await ev.answer(f"⛔️ Juda ko‘p so‘rov. Bot sizga {self.ban_seconds // 60} daqiqa javob bermaydi.")
        except Exception:  # noqa: BLE001 - a notice must never fail the update loop
            pass
        return None
