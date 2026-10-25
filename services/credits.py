"""
Free presentations and the referral programme.

  * Trial: every user's first presentation is free (once per Telegram account, dashboard: free_trial).
  * Bonus: extra free presentations — one per invited friend (referral_bonus) and admin gifts.
  * A free presentation covers up to free_max_slides slides; a bigger one is paid as usual.

The friend's inviter gets the bonus once, when the friend pays for the first time
(referral_trigger "paid", the default — fake accounts earn nothing) or makes the first
presentation ("first"). Claiming and rewarding are single UPDATE statements, so two presses at
the same moment can never spend one credit twice or reward one friend twice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update

from database.connection import AsyncSessionLocal
from database.models import PresentationOrder, User
from services import runtime

logger = logging.getLogger(__name__)

TRIAL, BONUS = "TRIAL", "BONUS"
FREE_KINDS = (TRIAL, BONUS)
NOT_A_PURCHASE = FREE_KINDS + ("TEST",)

_bot = None  # set at start: the inviter is told about the reward


def set_bot(bot) -> None:
    global _bot
    _bot = bot


@dataclass
class Credits:
    trial: bool = False
    bonus: int = 0

    @property
    def total(self) -> int:
        return int(self.trial) + max(0, self.bonus)


def trial_enabled() -> bool:
    return runtime.get_bool("free_trial")


def max_slides() -> int:
    """0 = any size."""
    return runtime.get_int("free_max_slides", 15, lo=0, hi=100)


def covers(slide_count: Optional[int]) -> bool:
    limit = max_slides()
    return slide_count is None or limit <= 0 or int(slide_count) <= limit


async def available(user_id: int) -> Credits:
    try:
        async with AsyncSessionLocal() as s:
            row = (await s.execute(select(User.trial_used_at, User.bonus_credits)
                                   .where(User.telegram_id == user_id))).first()
    except Exception:  # noqa: BLE001 - no free presentation is better than a crash
        logger.exception("credits of %s could not be read", user_id)
        return Credits()
    if row is None:  # never pressed /start: the trial is waiting for them
        return Credits(trial=trial_enabled())
    return Credits(trial=trial_enabled() and row[0] is None, bonus=int(row[1] or 0))


async def usable(user_id: int, slide_count: Optional[int] = None) -> bool:
    """A free presentation of this size can be made now."""
    return covers(slide_count) and (await available(user_id)).total > 0


async def claim(user_id: int, slide_count: int) -> Optional[str]:
    """Spends one free presentation: TRIAL first, then BONUS. None when nothing applies."""
    if not covers(slide_count):
        return None
    async with AsyncSessionLocal() as s:
        if await s.get(User, user_id) is None:
            s.add(User(telegram_id=user_id))
            await s.flush()
        if trial_enabled():
            res = await s.execute(update(User).where(User.telegram_id == user_id, User.trial_used_at.is_(None))
                                  .values(trial_used_at=datetime.utcnow()))
            if (res.rowcount or 0) > 0:
                await s.commit()
                return TRIAL
        res = await s.execute(update(User).where(User.telegram_id == user_id, User.bonus_credits > 0)
                              .values(bonus_credits=User.bonus_credits - 1))
        await s.commit()
        return BONUS if (res.rowcount or 0) > 0 else None


async def give_back(user_id: int, kind: Optional[str]) -> None:
    """The free presentation could not be delivered: it is returned."""
    if kind not in FREE_KINDS:
        return
    async with AsyncSessionLocal() as s:
        if kind == TRIAL:
            await s.execute(update(User).where(User.telegram_id == user_id).values(trial_used_at=None))
        else:
            await s.execute(update(User).where(User.telegram_id == user_id)
                            .values(bonus_credits=func.coalesce(User.bonus_credits, 0) + 1))
        await s.commit()


async def add_bonus(user_id: int, count: int) -> None:
    async with AsyncSessionLocal() as s:
        if await s.get(User, user_id) is None:
            s.add(User(telegram_id=user_id))
            await s.flush()
        from database.connection import IS_POSTGRES
        clamp = func.greatest if IS_POSTGRES else func.max  # SQLite's two-argument max() is a scalar
        await s.execute(update(User).where(User.telegram_id == user_id).values(
            bonus_credits=clamp(0, func.coalesce(User.bonus_credits, 0) + count)))
        await s.commit()


# ---------------------------------------------------------------------- referrals
def parse_ref(arg: str) -> Optional[int]:
    """/start payload of an invitation link: "ref_123" (new links) or "123" (old links)."""
    arg = (arg or "").strip()
    if arg.startswith("ref_"):
        arg = arg[4:]
    return int(arg) if arg.isdigit() else None


def link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


@dataclass
class RefStats:
    invited: int = 0
    paid: int = 0          # friends who already brought a bonus
    earned: int = 0        # free presentations earned with referrals


async def stats(user_id: int) -> RefStats:
    try:
        async with AsyncSessionLocal() as s:
            invited = (await s.execute(select(func.count()).select_from(User)
                                       .where(User.referred_by == user_id))).scalar() or 0
            paid = (await s.execute(select(func.count()).select_from(User)
                                    .where(User.referred_by == user_id, User.referral_rewarded.is_(True)))).scalar() or 0
    except Exception:  # noqa: BLE001
        logger.exception("referral stats of %s failed", user_id)
        return RefStats()
    return RefStats(invited=invited, paid=paid, earned=paid * runtime.get_int("referral_bonus", 1, lo=0, hi=100))


def _counts_for_referral(paid_by: str) -> bool:
    if runtime.get("referral_trigger", "paid") == "first":
        return paid_by != "TEST"
    return paid_by not in NOT_A_PURCHASE


async def on_order_paid(order_id: str, paid_by: str) -> Optional[int]:
    """Called once an order became PAID: rewards the customer's inviter (once per friend).
    Returns the inviter's id when a reward was given."""
    bonus = runtime.get_int("referral_bonus", 1, lo=0, hi=100)
    if bonus <= 0 or not _counts_for_referral(paid_by or ""):
        return None
    try:
        async with AsyncSessionLocal() as s:
            friend = (await s.execute(select(PresentationOrder.user_id)
                                      .where(PresentationOrder.id == order_id))).scalar()
            if friend is None:
                return None
            inviter = (await s.execute(select(User.referred_by).where(User.telegram_id == friend))).scalar()
            if not inviter or inviter == friend:
                return None
            res = await s.execute(update(User).where(User.telegram_id == friend,
                                                     User.referral_rewarded.is_(False))
                                  .values(referral_rewarded=True))
            if not (res.rowcount or 0):
                await s.commit()
                return None
            if await s.get(User, inviter) is None:
                s.add(User(telegram_id=inviter))
                await s.flush()
            await s.execute(update(User).where(User.telegram_id == inviter)
                            .values(bonus_credits=func.coalesce(User.bonus_credits, 0) + bonus))
            friend_name = (await s.execute(select(User.full_name).where(User.telegram_id == friend))).scalar()
            left = (await s.execute(select(User.bonus_credits).where(User.telegram_id == inviter))).scalar() or 0
            await s.commit()
    except Exception:  # noqa: BLE001 - a payment must never fail because of the referral bonus
        logger.exception("referral reward for order %s failed", order_id)
        return None
    logger.info("referral: %s rewarded with %d for friend %s", inviter, bonus, friend)
    if _bot is not None:
        from bot.texts import referral_reward_text
        from bot.keyboards.inline import create_now_keyboard
        try:
            await _bot.send_message(inviter, referral_reward_text(friend_name, bonus, left),
                                    parse_mode="HTML", reply_markup=create_now_keyboard())
        except Exception:  # noqa: BLE001 - they may have blocked the bot
            pass
    return inviter
