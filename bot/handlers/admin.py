import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from database.connection import AsyncSessionLocal
from database import repository

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    from services import runtime
    return runtime.is_admin(user_id)

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from bot.admin_web import auth, stats

    s = await stats.overview("1")
    text = (
        f"⚙️ <b>SlideLab — bugun</b>\n\n"
        f"💰 Daromad: <b>{stats.money(s['revenue'])} so‘m</b>\n"
        f"💳 To‘lovlar: <b>{s['payments']}</b> · namunalar: <b>{s['previews']}</b>\n"
        f"👥 Yangi foydalanuvchilar: <b>{s['new_users']}</b>\n"
        f"⏳ To‘lov kutilmoqda: <b>{s['waiting']}</b>\n\n"
    )
    base = auth.public_base_url()
    markup = None
    if base:
        token = await auth.create_login_token(message.from_user.id)
        url = f"{base}/admin/login/tg?t={token}"
        text += "🔐 Dashboardga kirish uchun tugmani bosing. Havola <b>10 daqiqa</b> amal qiladi va <b>bir marta</b> ishlaydi — hech kimga yubormang."
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Admin panelni ochish", url=url)]])
    else:
        text += "⚠️ Server domeni topilmadi: Railway’da domen yarating (Settings → Networking) yoki WEBAPP_URL ni kiriting."
    await message.answer(text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)


MIN_ORDER = 1000          # so'm: TezCheck does not accept a smaller bill (same rule as the dashboard)
LIMITS = {"price_per_slide": (1, 1_000_000), "min_slides": (3, 60), "max_slides": (3, 60)}


async def _current_limits():
    from config import settings
    async with AsyncSessionLocal() as session:
        get = repository.get_setting
        return {"price_per_slide": int(await get(session, "price_per_slide", str(settings.DEFAULT_PRICE_PER_SLIDE))),
                "min_slides": int(await get(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER))),
                "max_slides": int(await get(session, "max_slides", str(settings.MAX_SLIDES_PER_ORDER)))}


async def _set_limit(message: Message, key: str, example: str, done: str) -> None:
    """Checks a /setprice, /setminslides or /setmaxslides value exactly like the dashboard does."""
    if not is_admin(message.from_user.id):
        return
    args = (message.text or "").split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer(f"⚠️ Ishlatish: <code>{example}</code>", parse_mode="HTML")
        return
    value = int(args[1])
    lo, hi = LIMITS[key]
    if not lo <= value <= hi:
        await message.answer(f"⚠️ Qiymat {lo} dan {hi} gacha bo‘lishi kerak.", parse_mode="HTML")
        return
    limits = await _current_limits()
    limits[key] = value
    if limits["min_slides"] > limits["max_slides"]:
        await message.answer(f"⚠️ Minimum ({limits['min_slides']}) maksimumdan ({limits['max_slides']}) katta bo‘lishi mumkin emas.",
                             parse_mode="HTML")
        return
    if limits["price_per_slide"] * limits["min_slides"] < MIN_ORDER:
        await message.answer(f"⚠️ Eng kichik buyurtma {limits['price_per_slide']} × {limits['min_slides']} = "
                             f"{limits['price_per_slide'] * limits['min_slides']} so‘m bo‘lib qoladi. "
                             f"TezCheck {MIN_ORDER} so‘mdan kam to‘lovni qabul qilmaydi.", parse_mode="HTML")
        return
    from services import runtime
    await runtime.set_many({key: str(value)})
    await message.answer(done.format(value), parse_mode="HTML")


@router.message(Command("setprice"))
async def cmd_set_price(message: Message):
    await _set_limit(message, "price_per_slide", "/setprice 350", "✅ 1 slayd narxi <b>{} so'm</b> ga o'zgartirildi.")


@router.message(Command("setminslides"))
async def cmd_set_min_slides(message: Message):
    await _set_limit(message, "min_slides", "/setminslides 5", "✅ Minimum slayd miqdori <b>{} ta</b> ga o'zgartirildi.")


@router.message(Command("setmaxslides"))
async def cmd_set_max_slides(message: Message):
    await _set_limit(message, "max_slides", "/setmaxslides 30", "✅ Maksimum slayd miqdori <b>{} ta</b> ga o'zgartirildi.")
