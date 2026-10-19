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
from services.deck import themes
from bot.keyboards.reply import get_cancel_keyboard, get_subject_keyboard, CANCEL_TEXTS
from bot.handlers.create_pres import SUBJECT_PROMPT

logger = logging.getLogger(__name__)
router = Router()

IMAGE_DOC = F.document.mime_type.startswith("image/")


@router.message(PresentationForm.ocr_photo_upload, F.photo | IMAGE_DOC)
async def handle_ocr_task_photo(message: Message, state: FSMContext):
    msg_wait = await message.answer("🔍 <b>Topshiriq rasmi tahlil qilinmoqda (Vision AI)...</b>", parse_mode="HTML")

    bot = message.bot
    try:
        file_id = message.photo[-1].file_id if message.photo else message.document.file_id
        file_info = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        ocr_result = await ai_service.parse_task_image(file_bytes.read())
    except Exception:  # noqa: BLE001
        logger.exception("task photo could not be read")
        ocr_result = {"ok": False}

    try:
        await msg_wait.delete()
    except Exception:  # noqa: BLE001
        pass

    data = await state.get_data()
    template_id = data.get("template_id") or themes.DEFAULT_THEME
    if ocr_result.get("ok") is False or not (ocr_result.get("topic") or "").strip():
        # nothing reliable was read: never invent a topic, ask the user instead
        await state.update_data(template_id=template_id)
        await state.set_state(PresentationForm.subject)
        await message.answer("⚠️ Rasmdan topshiriqni o‘qib bo‘lmadi (rasm xira yoki AI vaqtincha ishlamayapti).\n\n"
                             "Keling, ma’lumotlarni qo‘lda kiritamiz.\n\n" + SUBJECT_PROMPT,
                             parse_mode="HTML", reply_markup=get_subject_keyboard())
        return

    async with AsyncSessionLocal() as session:
        min_slides = int(await repository.get_setting(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER)))
        max_slides = int(await repository.get_setting(session, "max_slides", str(settings.MAX_SLIDES_PER_ORDER)))

    subject = str(ocr_result.get("subject") or "Umumiy")[:300]
    topic = str(ocr_result.get("topic"))[:300]
    try:
        slide_count = int(ocr_result.get("slide_count") or 10)
    except (TypeError, ValueError):
        slide_count = 10
    slide_count = max(min_slides, min(slide_count, max_slides))
    language = ocr_result.get("language") if ocr_result.get("language") in ("uz", "ru", "en") else "uz"
    requirements = str(ocr_result.get("requirements") or "")[:600]

    await state.update_data(
        subject=subject,
        topic=topic,
        slide_count=slide_count,
        language=language,
        additional_notes=requirements,
        ocr_notes=requirements,
        template_id=template_id
    )

    confirm_msg = (
        f"🤖 <b>AI Topshiriq rasmini tahlil qildi:</b>\n\n"
        f"📚 <b>Fan:</b> {escape_html(subject)}\n"
        f"📌 <b>Mavzu:</b> {escape_html(topic)}\n"
        f"📑 <b>Slaydlar soni:</b> {slide_count} ta\n"
        f"🌐 <b>Til:</b> {escape_html(language)}\n"
        f"📝 <b>Talablar:</b> {escape_html(requirements) or '—'}\n\n"
        f"Endi prezentatsiya muallifi ma'lumotlarini kiriting.\n\n"
        f"<b>Ism va familiyangizni kiriting:</b>"
    )

    await state.set_state(PresentationForm.author_name)
    await message.answer(confirm_msg, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(PresentationForm.ocr_photo_upload, ~F.text.in_(CANCEL_TEXTS))
async def ocr_expects_a_photo(message: Message, state: FSMContext):
    await message.answer("📸 Iltimos, topshiriq yozilgan <b>rasm</b>ni yuboring.\n"
                         "<i>Bekor qilish uchun «❌ Bekor qilish» yoki /cancel.</i>", parse_mode="HTML")
