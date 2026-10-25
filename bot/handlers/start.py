import json
import os
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import settings
from database.connection import AsyncSessionLocal
from database import repository
from bot.keyboards.reply import get_main_menu_keyboard, CANCEL_TEXTS
from bot.utils import escape_html
from bot import texts
from bot.keyboards.inline import referral_keyboard
from services import credits, runtime

router = Router()

def load_locale(lang: str) -> dict:
    fpath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "locales", f"{lang}.json")
    if not os.path.exists(fpath):
        fpath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "locales", "uz.json")
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referred_by = credits.parse_ref(args[1]) if len(args) > 1 else None
    if referred_by == message.from_user.id:
        referred_by = None

    async with AsyncSessionLocal() as session:
        is_new = await repository.get_user(session, message.from_user.id) is None
        if referred_by and (not is_new or await repository.get_user(session, referred_by) is None):
            referred_by = None  # only brand-new users, invited by somebody who really uses the bot
        user = await repository.get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            referred_by=referred_by
        )
        lang = user.language or "uz"
    if referred_by:
        try:
            await message.bot.send_message(
                referred_by,
                texts.friend_joined_text(message.from_user.full_name, runtime.get_int("referral_bonus", 1, lo=0, hi=100),
                                         runtime.get("referral_trigger", "paid")),
                parse_mode="HTML")
        except Exception:  # noqa: BLE001 - the inviter may have blocked the bot
            pass

    # t.me/<bot>?start=paid_<order>: back from the TezCheck payment page
    if len(args) > 1 and args[1].startswith("paid_"):
        from bot.handlers.payment import handle_paid_deeplink
        await message.answer("👋 Xush kelibsiz!", reply_markup=get_main_menu_keyboard(lang))
        await handle_paid_deeplink(message, args[1][5:])
        return

    # t.me/<bot>?start=tpl_<template>[--<colour>] comes from the template gallery Mini App
    if len(args) > 1 and args[1].startswith("tpl_"):
        from bot.handlers.create_pres import apply_template_choice
        if await apply_template_choice(message.bot, message.chat.id, state, args[1][4:]):
            return

    if lang == "uz":
        have = await credits.available(message.from_user.id)
        welcome_text = texts.welcome_text(getattr(message.from_user, "first_name", None) or message.from_user.full_name, trial=have.trial, bonus=have.bonus,
                                          max_slides=credits.max_slides())
    else:
        welcome_text = load_locale(lang).get("welcome", "Welcome to SlideLab!")
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(lang),
        parse_mode="HTML"
    )

@router.message(F.text.in_(["💰 Narxlar", "💰 Цены", "💰 Pricing"]))
async def show_prices(message: Message):
    async with AsyncSessionLocal() as session:
        user = await repository.get_user(session, message.from_user.id)
        lang = user.language if user else "uz"

        price_per_slide = int(await repository.get_setting(session, "price_per_slide", str(settings.DEFAULT_PRICE_PER_SLIDE)))
        min_slides = int(await repository.get_setting(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER)))

    loc = load_locale(lang)
    p_text = loc.get("prices_info", "").format(
        price_per_slide=price_per_slide,
        min_slides=min_slides,
        min_price=min_slides * price_per_slide,
        p5=5 * price_per_slide,
        p10=10 * price_per_slide,
        p15=15 * price_per_slide,
        p20=20 * price_per_slide,
        p30=30 * price_per_slide
    )
    if lang == "uz" and credits.trial_enabled():
        n = credits.max_slides()
        p_text += (f"\n\n🎁 <b>Birinchi taqdimot — BEPUL!</b>{f' ({n} slaydgacha)' if n else ''}\n"
                   "Do‘stlaringizni taklif qilib, yana bepul taqdimotlar oling — «🎁 Referal».")
    await message.answer(p_text, parse_mode="HTML")

@router.message(F.text.in_(["👤 Profil", "👤 Профиль", "👤 Profile"]))
async def show_profile(message: Message):
    bot_info = await message.bot.get_me()
    async with AsyncSessionLocal() as session:
        user = await repository.get_user(session, message.from_user.id)
        if not user:
            user = await repository.get_or_create_user(session, message.from_user.id, message.from_user.full_name, message.from_user.username)

        orders_count = await repository.get_user_orders_count(session, message.from_user.id)
        referrals_count = await repository.get_user_referrals_count(session, message.from_user.id)
        lang = user.language or "uz"

    if lang == "uz":
        have = await credits.available(message.from_user.id)
        await message.answer(texts.profile_text(
            user_id=user.telegram_id, name=user.full_name, orders=orders_count, trial=have.trial, bonus=have.bonus,
            invited=referrals_count, link=credits.link(bot_info.username, user.telegram_id),
            balance=user.balance or 0, trial_on=credits.trial_enabled()), parse_mode="HTML")
        return
    loc = load_locale(lang)
    prof_text = loc.get("profile_info", "").format(
        user_id=user.telegram_id,
        full_name=escape_html(user.full_name) or "Foydalanuvchi",
        balance=user.balance,
        orders_count=orders_count,
        referrals_count=referrals_count,
        bot_username=bot_info.username
    )
    await message.answer(prof_text, parse_mode="HTML")

@router.message(F.text.in_(["🎁 Referal", "🎁 Рефералы", "🎁 Referral"]))
async def show_referral(message: Message):
    await _send_referral(message, message.from_user.id)


@router.callback_query(F.data == "ref_open")
async def show_referral_button(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:  # noqa: BLE001
        pass
    await _send_referral(callback.message, callback.from_user.id)


async def _send_referral(message: Message, user_id: int) -> None:
    bot_info = await message.bot.get_me()
    ref_link = credits.link(bot_info.username, user_id)
    st = await credits.stats(user_id)
    have = await credits.available(user_id)
    trial_on = credits.trial_enabled()
    text = texts.referral_text(
        ref_link, invited=st.invited, rewarded=st.paid, credits_left=have.total,
        bonus_per_friend=runtime.get_int("referral_bonus", 1, lo=0, hi=100),
        trigger=runtime.get("referral_trigger", "paid"), trial_on=trial_on, max_slides=credits.max_slides())
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True,
                         reply_markup=referral_keyboard(ref_link, texts.share_text(trial_on), have.total > 0))

@router.message(F.text.in_(["❓ Yordam", "❓ Помощь", "❓ Help"]))
async def show_help(message: Message):
    async with AsyncSessionLocal() as session:
        user = await repository.get_user(session, message.from_user.id)
        lang = user.language if user else "uz"
    loc = load_locale(lang)
    await message.answer(loc.get("help_info", "Help center"), parse_mode="HTML")


@router.message(Command("cancel"))
@router.message(F.text.in_(CANCEL_TEXTS))
async def cancel_wizard(message: Message, state: FSMContext):
    """The «❌ Bekor qilish» reply button and /cancel: leave any wizard and show the main menu."""
    from bot.states.forms import PresentationForm
    cur = await state.get_state()
    if getattr(cur, "state", cur) == PresentationForm.generating.state:
        await message.answer("⏳ Taqdimot allaqachon tayyorlanmoqda — tayyor bo‘lgach yuboriladi.")
        return
    await state.clear()
    from services import prefetch
    prefetch.drop(message.from_user.id)
    lang = "uz"
    try:
        async with AsyncSessionLocal() as session:
            user = await repository.get_user(session, message.from_user.id)
            lang = (user.language if user else None) or "uz"
    except Exception:  # noqa: BLE001 - the menu works without the database
        pass
    await message.answer("❌ Bekor qilindi. Asosiy menyu:", reply_markup=get_main_menu_keyboard(lang))
