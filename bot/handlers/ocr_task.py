import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from config import settings
from database.connection import AsyncSessionLocal
from database import repository
from bot.states.forms import PresentationForm
from bot.utils import escape_html
from services import ai_service

logger = logging.getLogger(__name__)
router = Router()

@router.message(PresentationForm.ocr_photo_upload, F.photo)
async def handle_ocr_task_photo(message: Message, state: FSMContext):
    msg_wait = await message.answer("🔍 <b>Topshiriq rasmi tahlil qilinmoqda (Vision AI)...</b>", parse_mode="HTML")

    photo = message.photo[-1]
    bot = message.bot
    file_info = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file_info.file_path)

    ocr_result = await ai_service.parse_task_image(file_bytes.read())

    async with AsyncSessionLocal() as session:
        min_slides = int(await repository.get_setting(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER)))
        max_slides = int(await repository.get_setting(session, "max_slides", str(settings.MAX_SLIDES_PER_ORDER)))

    subject = ocr_result.get("subject") or "Biologiya"
    topic = ocr_result.get("topic") or "Fotosintez jarayoni"
    try:
        slide_count = int(ocr_result.get("slide_count") or 10)
    except (TypeError, ValueError):
        slide_count = 10
    slide_count = max(min_slides, min(slide_count, max_slides))
    language = ocr_result.get("language") or "uz"
    requirements = ocr_result.get("requirements") or ""

    await state.update_data(
        subject=subject,
        topic=topic,
        slide_count=slide_count,
        language=language,
        additional_notes=requirements,
        template_id="01_midnight_tech"
    )

    confirm_msg = (
        f"🤖 <b>AI Topshiriq rasmini tahlil qildi:</b>\n\n"
        f"📚 <b>Fan:</b> {escape_html(subject)}\n"
        f"📌 <b>Mavzu:</b> {escape_html(topic)}\n"
        f"📑 <b>Slaydlar soni:</b> {slide_count} ta\n"
        f"🌐 <b>Til:</b> {escape_html(language)}\n"
        f"📝 <b>Talablar:</b> {escape_html(requirements)}\n\n"
        f"Endi prezentatsiya muallifi ma'lumotlarini kiriting.\n\n"
        f"<b>Ism va familiyangizni kiriting:</b>"
    )

    await state.set_state(PresentationForm.author_name)
    await msg_wait.delete()
    await message.answer(confirm_msg, parse_mode="HTML")
