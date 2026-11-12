"""
Flood protection for the bot (aiogram outer middleware on every update).

Each user has a token bucket: BURST tokens, refilled at RATE tokens per second. A message or a
button press costs 1 token (/start costs 3), so normal use is never slowed down, while scripts and
people hammering /start thousands of times are cut off:
  * an update without a token is dropped (the user gets one short notice per NOTICE_EVERY seconds);
  * a user who keeps flooding is ignored for BAN_SECONDS entirely: FLOOD_BAN dropped updates without a
    CALM_SECONDS pause count, even when some updates in between got through (flooding at twice the allowed
    speed used to pass every other update forever);
  * the same button pressed again or the same text sent again within DUP_WINDOW seconds is ignored
    (a double tap does not start two things); a stream of such repeats counts as flooding;
  * /start and the main menu buttons (they reset the wizard and send big messages) have their own
    small allowance: MENU_BURST at once, then one per MENU_EVERY seconds;
  * every new ban of the same user is twice as long as the previous one (up to MAX_BAN_SECONDS);
  * the dashboard lists who is banned right now and can lift a ban.
Admins are never limited. The state lives in memory and is pruned, so it cannot grow without end.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

logger = logging.getLogger(__name__)

NOTICE_EVERY = 20.0   # seconds between "too fast" notices to the same user
FLOOD_BAN = 30        # dropped updates (without a calm pause) that lead to a temporary ban
CALM_SECONDS = 15.0   # a pause this long without a dropped update forgives the earlier ones
PRUNE_EVERY = 300.0
DUP_WINDOW = 2.0      # seconds: the same button / text again within this time is a double tap
DUP_FREE = 2          # repeats ignored silently before they count as flooding (with a notice)
MENU_BURST = 5        # /start and main menu buttons at once…
MENU_EVERY = 12.0     # …then one per this many seconds (5 a minute)
MAX_BAN_SECONDS = 24 * 3600

# texts of the main menu buttons (all languages): each one resets the wizard and sends a big message
MENU_TEXTS = frozenset({
    "🎨 Presentation yaratish", "📄 Referat yaratish", "🖼 Shablonlar", "🎁 Referal", "👤 Profil", "💰 Narxlar",
    "❓ Yordam", "🎨 Создать презентацию", "📄 Создать реферат", "🖼 Шаблоны", "🎁 Рефералы", "👤 Профиль",
    "💰 Цены", "❓ Помощь", "🎨 Create Presentation", "📄 Create Paper", "🖼 Templates", "🎁 Referral",
    "👤 Profile", "💰 Pricing", "❓ Help",
})


class _Bucket:
    __slots__ = ("tokens", "stamp", "dropped", "last_drop", "noticed", "banned_until", "total_drops", "bans",
                 "menu_tokens", "last_key", "last_key_at", "repeats")

    def __init__(self, burst: float, now: float):
        self.tokens = burst
        self.stamp = now
        self.menu_tokens = float(MENU_BURST)
        self.last_key = None
        self.last_key_at = -1e9
        self.repeats = 0
        self.dropped = 0
        self.last_drop = -1e9
        self.noticed = 0.0
        self.banned_until = 0.0
        self.total_drops = 0
        self.bans = 0


_instances: list = []


def banned_now() -> int:
    """Users ignored right now for flooding (for the dashboard)."""
    return len(banned_list())


def banned_list() -> List[Dict[str, Any]]:
    """[{user_id, seconds_left, drops, bans}] of users ignored right now, longest ban first."""
    out = []
    for m in _instances:
        now = m.clock()
        for uid, b in m.buckets.items():
            if b.banned_until > now:
                out.append({"user_id": uid, "seconds_left": int(b.banned_until - now), "drops": b.total_drops,
                            "bans": b.bans})
    return sorted(out, key=lambda r: -r["seconds_left"])


def noisy_list(limit: int = 20) -> List[Dict[str, Any]]:
    """Users whose updates were dropped lately (still in memory), most dropped first."""
    rows = []
    for m in _instances:
        now = m.clock()
        for uid, b in m.buckets.items():
            if b.total_drops:
                rows.append({"user_id": uid, "drops": b.total_drops, "bans": b.bans,
                             "banned": b.banned_until > now})
    return sorted(rows, key=lambda r: -r["drops"])[:limit]


def unban(user_id: int) -> bool:
    """Lifts a flood ban (dashboard). True when the user was banned."""
    found = False
    for m in _instances:
        b = m.buckets.get(user_id)
        if b is not None:
            found = found or b.banned_until > m.clock()
            b.banned_until = 0.0
            b.dropped = 0
            b.tokens = m.burst
            b.menu_tokens = float(MENU_BURST)
    return found


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

    @staticmethod
    def _is_menu(ev) -> bool:
        if not isinstance(ev, Message):
            return False
        text = (ev.text or "").strip()
        return text.startswith("/start") or text in MENU_TEXTS

    @staticmethod
    def _key(ev):
        """What makes two updates "the same" (a double tap): the button's data on the same message, or the text."""
        if isinstance(ev, CallbackQuery):
            msg = getattr(ev, "message", None)
            return ("c", ev.data, getattr(msg, "message_id", None))
        if isinstance(ev, Message) and ev.text:
            return ("m", ev.text.strip())
        return None

    def _ban_length(self, b: _Bucket) -> int:
        """Twice as long for every earlier ban of the same user (5 min, 10, 20, 40… up to a day)."""
        return int(min(MAX_BAN_SECONDS, self.ban_seconds * (2 ** min(b.bans, 10))))

    def _prune(self, now: float) -> None:
        if now - self._pruned < PRUNE_EVERY:
            return
        self._pruned = now
        full = self.burst / self.rate
        # a user banned within the last day is kept, so a new ban of the same user is longer
        for uid in [u for u, b in self.buckets.items() if now - b.stamp > full and b.banned_until < now
                    and (not b.bans or now - b.banned_until > MAX_BAN_SECONDS)]:
            del self.buckets[uid]

    def _refresh_limits(self) -> None:
        """Burst and ban time can be changed in the admin dashboard while the bot runs."""
        if not self.dynamic:
            return
        from services import runtime
        self.burst = max(3, runtime.get_int("throttle_burst", self.burst))
        self.rate = max(0.05, runtime.get_int("throttle_rate_pm", int(self.rate * 60)) / 60.0)
        self.ban_seconds = 60 * max(1, runtime.get_int("throttle_ban_minutes", max(1, self.ban_seconds // 60)))

    def allow(self, user_id: int, cost: float = 1.0, key=None, menu: bool = False) -> Optional[str]:
        """None if the update may pass; otherwise "silent" (an ignored double tap), "notice" (tell the
        user once), "ban" (the user is now ignored for a while) or "drop".
        key: what identifies a repeat of the same update; menu: /start or a main menu button."""
        self._refresh_limits()
        now = self.clock()
        self._prune(now)
        b = self.buckets.get(user_id)
        if b is None:
            b = self.buckets[user_id] = _Bucket(self.burst, now)
        if b.banned_until > now:
            return "drop"
        elapsed = now - b.stamp
        b.tokens = min(self.burst, b.tokens + elapsed * self.rate)
        b.menu_tokens = min(float(MENU_BURST), b.menu_tokens + elapsed / MENU_EVERY)
        b.stamp = now
        if now - b.last_drop >= CALM_SECONDS:
            b.dropped = 0      # calmed down: earlier drops are forgiven
        if key is not None and key == b.last_key and now - b.last_key_at < DUP_WINDOW:
            b.last_key_at = now
            b.repeats += 1
            if b.repeats <= DUP_FREE:
                return "silent"    # a double tap: ignored without a word
            return self._dropped(b, user_id, now)
        if key is not None:
            b.last_key, b.last_key_at, b.repeats = key, now, 0
        if b.tokens >= cost and (not menu or b.menu_tokens >= 1):
            b.tokens -= cost
            if menu:
                b.menu_tokens -= 1
            return None
        return self._dropped(b, user_id, now)

    def _dropped(self, b: _Bucket, user_id: int, now: float) -> str:
        b.dropped += 1
        b.total_drops += 1
        b.last_drop = now
        if b.dropped >= FLOOD_BAN:
            length = self._ban_length(b)
            b.banned_until = now + length
            b.dropped = 0
            b.bans += 1
            logger.warning("user %s is flooding the bot: ignored for %d s (ban #%d)", user_id, length, b.bans)
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
        verdict = self.allow(user_id, self._cost(ev), key=self._key(ev), menu=self._is_menu(ev))
        if verdict is None:
            return await handler(event, data)
        try:
            if isinstance(ev, CallbackQuery):
                await ev.answer("⏳ Juda tez! Biroz kuting." if verdict in ("notice", "ban") else None)
            elif isinstance(ev, Message) and verdict == "notice":
                await ev.answer("⏳ Juda ko‘p so‘rov yuboryapsiz. Iltimos, bir necha soniya kuting.")
            elif isinstance(ev, Message) and verdict == "ban":
                b = self.buckets.get(user_id)
                minutes = max(1, int(((b.banned_until if b else 0) - self.clock()) // 60) + 1)
                await ev.answer(f"⛔️ Juda ko‘p so‘rov. Bot sizga {minutes} daqiqa javob bermaydi.")
        except Exception:  # noqa: BLE001 - a notice must never fail the update loop
            pass
        return None
