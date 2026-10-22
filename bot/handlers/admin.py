import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from config import settings
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


@router.message(Command("setprice"))
async def cmd_set_price(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Ishlatish: <code>/setprice 350</code>", parse_mode="HTML")
        return

    new_price = args[1]
    async with AsyncSessionLocal() as session:
        await repository.set_setting(session, "price_per_slide", new_price)

    await message.answer(f"✅ 1 slayd narxi <b>{new_price} so'm</b> ga o'zgartirildi.", parse_mode="HTML")

@router.message(Command("setminslides"))
async def cmd_set_min_slides(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Ishlatish: <code>/setminslides 5</code>", parse_mode="HTML")
        return

    new_min = args[1]
    async with AsyncSessionLocal() as session:
        await repository.set_setting(session, "min_slides", new_min)

    await message.answer(f"✅ Minimum slayd miqdori <b>{new_min} ta</b> ga o'zgartirildi.", parse_mode="HTML")

@router.message(Command("setmaxslides"))
async def cmd_set_max_slides(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("⚠️ Ishlatish: <code>/setmaxslides 30</code>", parse_mode="HTML")
        return

    new_max = args[1]
    async with AsyncSessionLocal() as session:
        await repository.set_setting(session, "max_slides", new_max)

    await message.answer(f"✅ Maksimum slayd miqdori <b>{new_max} ta</b> ga o'zgartirildi.", parse_mode="HTML")
