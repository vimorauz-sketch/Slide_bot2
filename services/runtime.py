"""
Settings the admin dashboard can change while the bot is running (stored in system_settings).

The values are cached in memory (load() at start, set_many() from the dashboard), so the bot reads
them on every update without touching the database. Keys that are not stored fall back to the
defaults from config/.env.
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, Set

from config import settings

logger = logging.getLogger(__name__)

MAINTENANCE_TEXT = ("🛠 Hozir botda texnik ishlar olib borilmoqda. "
                    "Taxminan 30 daqiqadan so‘ng qaytadan urinib ko‘ring.")


def defaults() -> Dict[str, str]:
    return {
        "price_per_slide": str(settings.DEFAULT_PRICE_PER_SLIDE),
        "min_slides": str(settings.MIN_SLIDES_PER_ORDER),
        "max_slides": str(settings.MAX_SLIDES_PER_ORDER),
        "max_previews_per_day": str(settings.MAX_PREVIEWS_PER_DAY),
        "max_parallel_builds": str(settings.MAX_PARALLEL_BUILDS),
        "throttle_burst": str(settings.THROTTLE_BURST),
        "throttle_ban_minutes": str(max(1, int(settings.THROTTLE_BAN_SECONDS) // 60)),
        "ai_fast_model": settings.OPENAI_FAST_MODEL,
        "ai_effort": settings.OPENAI_REASONING_EFFORT,
        "orders_mode": "auto",
        "max_unpaid_open": "2",
        "daily_preview_cap": "300",
        "prefetch_mode": "paid",
        "maintenance": "0",
        "maintenance_text": MAINTENANCE_TEXT,
        "extra_admins": "",
        "free_trial": "1",              # every user's first presentation is free
        "free_max_slides": "15",        # the free (trial / bonus) presentation covers up to this many slides
        "referral_bonus": "1",          # free presentations the inviter gets per friend
        "referral_trigger": "paid",     # paid: when the friend pays for the first time / first: first presentation
    }


_values: Dict[str, str] = {}
blocked_users: Set[int] = set()


def get(key: str, default: str = "") -> str:
    if key in _values:
        return _values[key]
    return defaults().get(key, default)


def get_int(key: str, default: int = 0, lo: int = 0, hi: int = 10 ** 9) -> int:
    try:
        return max(lo, min(hi, int(str(get(key, str(default))).strip())))
    except ValueError:
        return default


def get_bool(key: str) -> bool:
    return str(get(key, "0")).strip().lower() in ("1", "true", "yes", "on")


def admin_ids() -> Set[int]:
    extra = {int(x) for x in get("extra_admins").replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()}
    return set(settings.admin_id_list) | extra


def is_admin(user_id) -> bool:
    try:
        return int(user_id) in admin_ids()
    except (TypeError, ValueError):
        return False


async def load() -> None:
    """Reads stored settings and blocked users from the database (called at start)."""
    from sqlalchemy import select
    from database.connection import AsyncSessionLocal
    from database.models import SystemSetting, User
    try:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(select(SystemSetting))).scalars().all()
            _values.clear()
            _values.update({r.key: r.value for r in rows})
            ids = (await session.execute(select(User.telegram_id).where(User.is_blocked.is_(True)))).scalars().all()
            blocked_users.clear()
            blocked_users.update(int(i) for i in ids)
    except Exception:  # noqa: BLE001 - the bot still works with the defaults
        logger.exception("runtime settings could not be loaded")


async def set_many(values: Dict[str, str]) -> None:
    from database.connection import AsyncSessionLocal
    from database import repository
    async with AsyncSessionLocal() as session:
        for k, v in values.items():
            await repository.set_setting(session, k, str(v))
    _values.update({k: str(v) for k, v in values.items()})


def set_blocked(user_ids: Iterable[int], blocked: bool) -> None:
    for uid in user_ids:
        (blocked_users.add if blocked else blocked_users.discard)(int(uid))
