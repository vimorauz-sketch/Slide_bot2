"""
«📄 Referat yaratish»: template (Mini App or numbered pictures) → subject → topic → size → name →
level → institution → class/group → teacher → city → language → pictures? → extra wishes →
confirmation → the referat is written (AI), real photos are added if wanted, Word + PDF are made,
two watermarked pages are shown and the files come after payment (or at once, if free).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Optional

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto,
                           KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo)

from bot.keyboards.reply import (CANCEL_TEXT, NO_TEXT, SKIP_TEXT, SKIP_TEXTS, YES_TEXT, class_options,
                                 get_cancel_keyboard, get_language_keyboard, get_level_keyboard, get_main_menu_keyboard,
                                 get_skip_keyboard, get_subject_keyboard, get_yes_no_keyboard)
from bot.states.forms import ReferatForm
from bot.utils import escape_html
from database import repository
from database.connection import AsyncSessionLocal
from services import credits, runtime
from services.referat import designs, gallery, writer

logger = logging.getLogger(__name__)
router = Router()

LANG_NAMES = {"uz": "🇺🇿 O‘zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}
CITIES = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Farg‘ona", "Qarshi", "Nukus", "Urganch",
          "Termiz", "Jizzax", "Navoiy", "Guliston"]
IMG_YES, IMG_NO = "🖼 Ha, rasmlar bo‘lsin", "📄 Yo‘q, faqat matn"
MAX_TEXT = 300


def _clean(text) -> str:
    return " ".join(str(text or "").split())[:MAX_TEXT]


def _kb(rows, placeholder: str = "") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in r] for r in rows], resize_keyboard=True,
                               input_field_placeholder=placeholder[:64] or None)


def size_keyboard(price: int) -> ReplyKeyboardMarkup:
    rows = [[f"{s['label']} · {price * s['pages']:,} so‘m".replace(",", " ")] for s in writer.SIZES.values()]
    return _kb(rows + [[CANCEL_TEXT]])


def _size_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for key, s in writer.SIZES.items():
        if s["label"].lower() in t or t.startswith(s["label"].split("–")[0]):
            return key
    m = re.search(r"\d+", t)
    if m:
        n = int(m.group())
        return "short" if n <= 7 else "medium" if n <= 10 else "long" if n <= 15 else "xl"
    return None


async def _price_per_page() -> int:
    return runtime.get_int("referat_price_per_page", 500, lo=50, hi=1_000_000)


def webapp_url() -> str:
    from bot.handlers.create_pres import webapp_url as base
    url = base()
    return (url.rstrip("/") + "/referat/") if url else ""


# ---------------------------------------------------------------------- start: template
def gallery_keyboard(page: int) -> InlineKeyboardMarkup:
    ids = gallery.page_ids(page)
    rows, row = [], []
    for tid in ids:
        t = designs.get(tid)
        row.append(InlineKeyboardButton(text=str(t["code"]), callback_data=f"rf_t:{tid}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    pages = gallery.pages()
    rows.append([InlineKeyboardButton(text="◀️", callback_data=f"rf_g:{(page - 1) % pages}"),
                 InlineKeyboardButton(text=f"{page + 1} / {pages}", callback_data="gal_noop"),
                 InlineKeyboardButton(text="▶️", callback_data=f"rf_g:{(page + 1) % pages}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _gallery_caption(page: int) -> str:
    return (f"📄 <b>{len(designs.TEMPLATES)} TA REFERAT SHABLONI</b>\n\n"
            "Har birida titul varag‘i, sarlavhalar va ranglar o‘ziga xos; ichki sahifalar akademik talabga mos "
            "(A4, 14 pt, 1,5 interval).\n\n"
            f"👉 Raqamni bosing yoki yozing (<code>1</code> – <code>{len(designs.TEMPLATES)}</code>).")


@router.message(F.text.in_(["📄 Referat yaratish", "📄 Создать реферат", "📄 Create Paper"]))
async def start_referat(message: Message, state: FSMContext):
    await open_referat(message, message.from_user.id, state)


@router.callback_query(F.data == "new_referat")
async def start_referat_button(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:  # noqa: BLE001
        pass
    await open_referat(callback.message, callback.from_user.id, state)


async def open_referat(message: Message, user_id: int, state: FSMContext) -> None:
    from bot.handlers.create_pres import _blocked
    from services import prefetch
    cur = await state.get_state()
    if getattr(cur, "state", cur) in (ReferatForm.generating.state, "PresentationForm:generating"):
        await message.answer("⏳ Hozir hujjatingiz tayyorlanmoqda — tayyor bo‘lgach yuboriladi.")
        return
    prefetch.drop(user_id)
    await state.clear()
    if await _blocked(message, user_id):
        return
    await state.set_state(ReferatForm.template)
    url = webapp_url()
    sheet = await gallery.sheet(0)
    caption = _gallery_caption(0)
    if sheet:
        await message.answer_photo(FSInputFile(sheet), caption=caption, parse_mode="HTML", reply_markup=gallery_keyboard(0))
    else:
        await message.answer(caption, parse_mode="HTML", reply_markup=gallery_keyboard(0))
    if url:
        await message.answer("🎨 Shablonlarni kattaroq ko‘rish uchun pastdagi tugmani bosing:",
                             reply_markup=ReplyKeyboardMarkup(keyboard=[
                                 [KeyboardButton(text="📄 Referat shablonlari", web_app=WebAppInfo(url=url))],
                                 [KeyboardButton(text=CANCEL_TEXT)]], resize_keyboard=True))


@router.callback_query(F.data.startswith("rf_g:"))
async def gallery_page(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split(":", 1)[1]) % gallery.pages()
    except ValueError:
        page = 0
    try:
        await callback.answer("⏳")
    except Exception:  # noqa: BLE001
        pass
    sheet = await gallery.sheet(page)
    try:
        if sheet and getattr(callback.message, "photo", None):
            await callback.message.edit_media(InputMediaPhoto(media=FSInputFile(sheet), caption=_gallery_caption(page),
                                                              parse_mode="HTML"), reply_markup=gallery_keyboard(page))
            return
    except Exception:  # noqa: BLE001
        pass
    if sheet:
        await callback.message.answer_photo(FSInputFile(sheet), caption=_gallery_caption(page), parse_mode="HTML",
                                            reply_markup=gallery_keyboard(page))


@router.callback_query(F.data.startswith("rf_t:"))
async def template_button(callback: CallbackQuery, state: FSMContext):
    tid = callback.data.split(":", 1)[1]
    try:
        await callback.answer("✅ Tanlandi")
    except Exception:  # noqa: BLE001
        pass
    await apply_template_choice(callback.bot, callback.message.chat.id, state, tid)


@router.message(ReferatForm.template, F.text)
async def template_number(message: Message, state: FSMContext):
    text = message.text.strip().lstrip("#№ ").strip()
    if text.isdigit() and 1 <= int(text) <= len(designs.TEMPLATES):
        await apply_template_choice(message.bot, message.chat.id, state, designs.by_number(int(text))["id"])
        return
    await message.answer(f"⚠️ Iltimos, <b>1 dan {len(designs.TEMPLATES)} gacha</b> shablon raqamini yuboring yoki "
                         "rasm ostidagi tugmani bosing.", parse_mode="HTML")


async def apply_template_choice(bot, chat_id: int, state: FSMContext, template_id: str) -> bool:
    """Shared by the buttons, typed numbers and the Mini App."""
    if template_id not in designs.BY_ID:
        return False
    t = designs.get(template_id)
    cur = await state.get_state()
    cur = getattr(cur, "state", cur)
    starting = cur in (None, ReferatForm.template.state) or not str(cur or "").startswith("ReferatForm:")
    if starting:
        if cur is None or not str(cur).startswith("ReferatForm:"):
            from services import guard
            block = await guard.check(chat_id)
            if block is not None:
                await bot.send_message(chat_id, block.text, parse_mode="HTML")
                return True
            await state.set_data({})
        await state.update_data(referat_template=template_id)
        await state.set_state(ReferatForm.subject)
        text = (f"✅ <b>№ {t['code']} · {escape_html(t['name'])}</b> tanlandi!\n\n"
                "📚 <b>Fan nomini kiriting:</b>\n(Masalan: <i>Tarix, Biologiya, Iqtisodiyot</i>)")
        markup = get_subject_keyboard()
    else:
        await state.update_data(referat_template=template_id)
        text = f"🎨 <b>Shablon o‘zgartirildi:</b> № {t['code']} · {escape_html(t['name'])}"
        markup = None
    p1, p4 = await gallery.page_path(template_id, 1), await gallery.page_path(template_id, 4)
    if p1 and p4 and hasattr(bot, "send_media_group"):
        try:
            await bot.send_media_group(chat_id, [InputMediaPhoto(media=FSInputFile(p1)), InputMediaPhoto(media=FSInputFile(p4))])
        except Exception:  # noqa: BLE001
            logger.exception("referat template pages not sent")
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
    return True


# ---------------------------------------------------------------------- questions
@router.message(ReferatForm.subject, F.text)
async def ask_topic(message: Message, state: FSMContext):
    await state.update_data(subject=_clean(message.text))
    await state.set_state(ReferatForm.topic)
    await message.answer("📌 <b>Referat mavzusini kiriting:</b>\n\n(Masalan: <i>Amir Temur davlatining tashkil topishi</i>)",
                         parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(ReferatForm.topic, F.text)
async def ask_size(message: Message, state: FSMContext):
    await state.update_data(topic=_clean(message.text))
    await state.set_state(ReferatForm.size)
    price = await _price_per_page()
    free = ""
    have = await credits.available(message.from_user.id)
    if have.total > 0:
        n = credits.max_slides()
        free = (f"\n\n🎁 <b>{'Birinchi hujjatingiz' if have.trial else 'Keyingi hujjatingiz'} bepul</b>"
                f"{f' ({n} betgacha)' if n else ''}!")
    await message.answer(f"📏 <b>Referat hajmi qancha bo‘lsin?</b>\n\nNarxi: 1 bet = {price:,} so‘m".replace(",", " ")
                         + free, parse_mode="HTML", reply_markup=size_keyboard(price))


@router.message(ReferatForm.size, F.text)
async def ask_author(message: Message, state: FSMContext):
    key = _size_from_text(message.text)
    if not key:
        await message.answer("⚠️ Iltimos, tugmalardan birini tanlang.", reply_markup=size_keyboard(await _price_per_page()))
        return
    await state.update_data(size=key)
    await state.set_state(ReferatForm.author)
    await message.answer("👤 <b>Ism va familiyangizni kiriting:</b>\n\n(Masalan: <i>Doniyorbek Normurodov</i>)",
                         parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(ReferatForm.author, F.text)
async def ask_level(message: Message, state: FSMContext):
    await state.update_data(author_name=_clean(message.text))
    await state.set_state(ReferatForm.level)
    await message.answer("🎓 <b>Ta’lim darajangizni tanlang:</b>", parse_mode="HTML", reply_markup=get_level_keyboard())


@router.message(ReferatForm.level, F.text)
async def ask_institution(message: Message, state: FSMContext):
    await state.update_data(level=_clean(message.text))
    await state.set_state(ReferatForm.institution)
    await message.answer("🏫 <b>Ta’lim muassasangiz nomi</b> (ixtiyoriy)\n\nTitul varag‘ida yoziladi. "
                         "(Masalan: <i>Toshkent davlat iqtisodiyot universiteti</i>)\n\n"
                         "<i>Kerak bo‘lmasa «⏭ O‘tkazib yuborish».</i>", parse_mode="HTML", reply_markup=get_skip_keyboard())


@router.message(ReferatForm.institution, F.text)
async def ask_group(message: Message, state: FSMContext):
    await state.update_data(institution="" if message.text.strip() in SKIP_TEXTS else _clean(message.text))
    level = (await state.get_data()).get("level", "")
    opts = class_options(level)
    school = bool(opts) and "sinf" in opts[0]
    await state.set_state(ReferatForm.group)
    if school:
        rows = [opts[i:i + 4] for i in range(0, len(opts), 4)] + [[SKIP_TEXT], [CANCEL_TEXT]]
        await message.answer("🎓 <b>Nechanchi sinfda o‘qiysiz?</b>", parse_mode="HTML", reply_markup=_kb(rows))
    else:
        await message.answer("👥 <b>Guruhingiz</b> (ixtiyoriy)\n\n(Masalan: <i>211-21</i> yoki <i>2-kurs</i>)\n\n"
                             "<i>Kerak bo‘lmasa «⏭ O‘tkazib yuborish».</i>", parse_mode="HTML",
                             reply_markup=get_skip_keyboard())


@router.message(ReferatForm.group, F.text)
async def ask_teacher(message: Message, state: FSMContext):
    await state.update_data(group="" if message.text.strip() in SKIP_TEXTS else _clean(message.text))
    await state.set_state(ReferatForm.teacher)
    await message.answer("👨‍🏫 <b>Tekshiruvchi o‘qituvchi ism-familiyasi</b> (ixtiyoriy)\n\n"
                         "<i>Kerak bo‘lmasa «⏭ O‘tkazib yuborish».</i>", parse_mode="HTML", reply_markup=get_skip_keyboard())


@router.message(ReferatForm.teacher, F.text)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(teacher_name="" if message.text.strip() in SKIP_TEXTS else _clean(message.text))
    await state.set_state(ReferatForm.city)
    rows = [CITIES[i:i + 3] for i in range(0, len(CITIES), 3)] + [[CANCEL_TEXT]]
    await message.answer("🏙 <b>Titul varag‘i pastiga qaysi shahar yozilsin?</b>\n\n<i>Tugmani bosing yoki yozing.</i>",
                         parse_mode="HTML", reply_markup=_kb(rows, "Yoki shahar nomini yozing…"))


@router.message(ReferatForm.city, F.text)
async def ask_language(message: Message, state: FSMContext):
    await state.update_data(city="" if message.text.strip() in SKIP_TEXTS else _clean(message.text)[:40])
    await state.set_state(ReferatForm.language)
    await message.answer("🌐 <b>Referat qaysi tilda yozilsin?</b>", parse_mode="HTML", reply_markup=get_language_keyboard())


@router.message(ReferatForm.language, F.text)
async def ask_images(message: Message, state: FSMContext):
    t = message.text.lower()
    lang = "ru" if ("рус" in t or "rus" in t) else "en" if ("english" in t or "ingliz" in t) else "uz"
    await state.update_data(language=lang)
    await state.set_state(ReferatForm.images)
    await message.answer("🖼 <b>Referatga rasmlar qo‘shilsinmi?</b>\n\n"
                         "«Ha» desangiz, mavzuga mos <b>haqiqiy fotosuratlar</b> avtomatik qo‘yiladi "
                         "(«1-rasm. …» kabi izoh bilan).", parse_mode="HTML",
                         reply_markup=_kb([[IMG_YES, IMG_NO], [CANCEL_TEXT]]))


@router.message(ReferatForm.images, F.text)
async def ask_notes(message: Message, state: FSMContext):
    t = message.text.strip().lower()
    yes = message.text.strip() == IMG_YES or t.startswith(("ha", "xa", "да", "yes"))
    await state.update_data(with_images=yes)
    await state.set_state(ReferatForm.notes_choice)
    await message.answer("📝 <b>Qo‘shimcha talablaringiz bormi?</b>\n\n"
                         "<i>Masalan: «O‘zbekiston misolida yozilsin», «Statistik ma’lumotlar ko‘proq bo‘lsin».</i>",
                         parse_mode="HTML", reply_markup=get_yes_no_keyboard())


@router.message(ReferatForm.notes_choice, F.text)
async def notes_choice(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == YES_TEXT or text.lower() in ("ha", "xa", "да", "yes", "bor"):
        await state.set_state(ReferatForm.notes)
        await message.answer("✍️ <b>Talablaringizni yozing:</b>", parse_mode="HTML", reply_markup=get_cancel_keyboard())
        return
    if text == NO_TEXT or text in SKIP_TEXTS or text.lower() in ("yo'q", "yoq", "yo‘q", "нет", "no"):
        await _confirm(message, state, "")
        return
    await _confirm(message, state, _clean(message.text))


@router.message(ReferatForm.notes, F.text)
async def notes_text(message: Message, state: FSMContext):
    await _confirm(message, state, "" if message.text.strip() in SKIP_TEXTS else _clean(message.text))


async def _confirm(message: Message, state: FSMContext, notes: str) -> None:
    await state.update_data(additional_notes=notes)
    data = await state.get_data()
    size = writer.size_of(data.get("size"))
    price = await _price_per_page() * size["pages"]
    await state.update_data(total_price=price)
    t = designs.get(data.get("referat_template"))
    rows = [("🎨", "Shablon", f"№ {t['code']} · {t['name']}"), ("📚", "Fan", data.get("subject")),
            ("📌", "Mavzu", data.get("topic")), ("📏", "Hajmi", size["label"]), ("👤", "Muallif", data.get("author_name")),
            ("🎓", "Daraja", data.get("level")), ("🏫", "Muassasa", data.get("institution")),
            ("👥", "Guruh / sinf", data.get("group")), ("👨‍🏫", "O‘qituvchi", data.get("teacher_name")),
            ("🏙", "Shahar", data.get("city")), ("🌐", "Til", LANG_NAMES.get(data.get("language"), "")),
            ("🖼", "Rasmlar", "ha, haqiqiy fotosuratlar" if data.get("with_images") else "yo‘q"), ("📝", "Talablar", notes)]
    lines = "".join(f"{e} <b>{k}:</b> {escape_html(v)}\n" for e, k, v in rows if v)
    if await credits.usable(message.from_user.id, size["pages"]):
        from bot import texts
        price_line = texts.free_price_line(price, trial=(await credits.available(message.from_user.id)).trial)
    else:
        price_line = f"💰 <b>Narxi:</b> {price:,} so‘m".replace(",", " ")
    await state.set_state(ReferatForm.confirmation)
    await message.answer("👌 Ma’lumotlar qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(f"📄 <b>REFERAT — TASDIQLASH</b>\n\n{lines}\n{price_line}\n\nReferatni yozishni boshlaymizmi?",
                         parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="✅ Tasdiqlash va yozish", callback_data="rf_go")],
                             [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="rf_cancel")]]))


@router.callback_query(F.data == "rf_cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:  # noqa: BLE001
        pass
    cur = await state.get_state()
    if getattr(cur, "state", cur) == ReferatForm.generating.state:
        await callback.message.answer("⏳ Referat allaqachon tayyorlanmoqda.")
        return
    await state.clear()
    try:
        await callback.message.edit_text("❌ Referat yaratish bekor qilindi.")
    except Exception:  # noqa: BLE001
        pass
    await callback.message.answer("🏠 Asosiy menyu", reply_markup=get_main_menu_keyboard())


# ---------------------------------------------------------------------- build
@router.callback_query(ReferatForm.confirmation, F.data == "rf_go")
async def confirm(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer("⚡️ Referat yozilmoqda…")
    except Exception:  # noqa: BLE001
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await build_and_send(callback.message, callback.from_user.id, state)


async def build_and_send(message: Message, user_id: int, state: FSMContext) -> None:
    from bot.handlers.create_pres import _blocked, _build_slot, _deliver_free, _payment_keyboard, _state_is
    from bot.progress import REFERAT_STAGES, ProgressMessage
    from services.referat import builder

    await state.set_state(ReferatForm.generating)
    data = await state.get_data()
    size = writer.size_of(data.get("size"))
    if await _blocked(message, user_id, size["pages"]):
        await state.set_state(ReferatForm.confirmation)
        return
    await message.answer("✅ Qabul qilindi! Referat tayyor bo‘lishi bilan shu yerga yuboraman.",
                         reply_markup=get_main_menu_keyboard())
    status = await message.answer("📄 <b>Referatingiz tayyorlanmoqda</b>\n\n<code>▱▱▱▱▱▱▱▱▱▱▱▱</code>  <b>0%</b>",
                                  parse_mode="HTML")
    bar = ProgressMessage(status, title="📄 <b>Referatingiz tayyorlanmoqda</b>", stages=REFERAT_STAGES).start()
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    storage_dir = os.path.join(root, "storage", str(uuid.uuid4()))
    try:
        async with _build_slot(bar):
            result = await builder.build_referat(data, storage_dir, progress=bar.set)
    except Exception:
        await bar.stop()
        logger.exception("Referat build failed")
        if await _state_is(state, ReferatForm.generating):
            await state.set_state(ReferatForm.confirmation)
        await message.answer("⚠️ Referatni yaratishda xatolik yuz berdi. Birozdan so‘ng qaytadan urinib ko‘ring.",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="🔄 Qayta urinish", callback_data="rf_go")]]))
        return
    await bar.finish()
    try:
        await status.delete()
    except Exception:  # noqa: BLE001
        pass

    price = int(data.get("total_price") or (await _price_per_page()) * size["pages"])
    async with AsyncSessionLocal() as session:
        order = await repository.create_presentation_order(
            session=session, user_id=user_id, topic=data.get("topic", ""), subject=data.get("subject", ""),
            slide_count=result.pages, template_id=data.get("referat_template", designs.DEFAULT), total_price=price,
            pptx_path=result.docx_path, pdf_path=result.pdf_path, content_json=builder.content_for_db(result.saved),
            language=data.get("language"), kind="referat")
        order_id = order.id

    free_kind = await credits.claim(user_id, size["pages"])
    if free_kind:
        await _deliver_free(message, user_id, order_id, data, result.pages, free_kind, referat=True)
        if await _state_is(state, ReferatForm.generating):
            await state.clear()
        return

    media = [InputMediaPhoto(media=FSInputFile(p), caption="🔍 Namuna sahifalar (NAMUNA • SLIDELAB)" if i == 0 else "")
             for i, p in enumerate(result.previews)]
    try:
        if len(media) >= 2:
            await message.answer_media_group(media=media)
        elif media:
            await message.answer_photo(media[0].media, caption=media[0].caption)
    except Exception:  # noqa: BLE001
        logger.exception("referat previews not sent")
    text = (f"📄 <b>Referatingiz tayyor!</b>\n\n"
            f"Yuqorida titul varag‘i va ichki sahifa namunasi (<i>NAMUNA</i> belgisi bilan).\n\n"
            f"💳 <b>To‘lovdan so‘ng</b> shu yerga avtomatik keladi:\n"
            f"• 📝 <b>Word (.docx)</b> — matni, ism-familiya va boshqa ma’lumotlarni tahrirlash mumkin;\n"
            f"• 📄 <b>PDF</b> — chop etish uchun tayyor.\n\n"
            f"📏 <b>Hajmi:</b> {result.pages} bet\n"
            f"💰 <b>Narxi:</b> {price:,} so‘m".replace(",", " "))
    markup, note = _payment_keyboard(user_id, order_id, price)
    await message.answer(text + note, parse_mode="HTML", reply_markup=markup)
    if await _state_is(state, ReferatForm.generating):
        await state.clear()


# ---------------------------------------------------------------------- anything else in the wizard
@router.message(StateFilter(ReferatForm.generating))
async def busy(message: Message, state: FSMContext):
    await message.answer("⏳ Referatingiz tayyorlanmoqda, bir oz kuting…")


@router.message(StateFilter(ReferatForm.confirmation))
async def press_button(message: Message, state: FSMContext):
    await message.answer("👆 Iltimos, yuqoridagi xabardagi tugmalardan birini bosing.")


@router.message(StateFilter(ReferatForm))
async def text_expected(message: Message, state: FSMContext):
    await message.answer("✍️ Iltimos, javobni <b>matn</b> ko‘rinishida yuboring.\n"
                         "<i>Bekor qilish uchun «❌ Bekor qilish» yoki /cancel.</i>", parse_mode="HTML")
