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
    return user_id in settings.admin_id_list

@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with AsyncSessionLocal() as session:
        price_per_slide = await repository.get_setting(session, "price_per_slide", str(settings.DEFAULT_PRICE_PER_SLIDE))
        min_slides = await repository.get_setting(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER))
        max_slides = await repository.get_setting(session, "max_slides", str(settings.MAX_SLIDES_PER_ORDER))

    text = (
        f"⚙️ <b>SlideLab Admin Paneli</b>\n\n"
        f"💰 <b>1 slayd narxi:</b> {price_per_slide} so'm\n"
        f"📑 <b>Minimum slayd soni:</b> {min_slides} ta\n"
        f"📑 <b>Maksimum slayd soni:</b> {max_slides} ta\n\n"
        f"<b>Admin buyruqlari:</b>\n"
        f"/setprice [summa] — 1 slayd narxini o'zgartirish\n"
        f"/setminslides [soni] — minimum slayd sonini o'zgartirish\n"
        f"/setmaxslides [soni] — maksimum slayd sonini o'zgartirish"
    )
    await message.answer(text, parse_mode="HTML")

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
