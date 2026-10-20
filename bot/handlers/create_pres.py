import json
import os
import re
import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from config import settings
from database.connection import AsyncSessionLocal
from database import repository
from bot.states.forms import PresentationForm
from bot.utils import escape_html
from bot.keyboards.inline import (
    get_template_selection_inline_keyboard, get_confirmation_inline_keyboard,
    get_payment_inline_keyboard, get_production_payment_inline_keyboard, get_outline_inline_keyboard,
    get_gallery_categories_keyboard, get_gallery_list_keyboard, get_gallery_colors_keyboard
)
from bot.keyboards.reply import (
    get_level_keyboard, get_course_keyboard, get_language_keyboard, get_cancel_keyboard, get_webapp_keyboard,
    get_skip_keyboard, get_main_menu_keyboard, SKIP_TEXTS, get_subject_keyboard, get_slide_count_keyboard,
    get_date_keyboard, get_yes_no_keyboard, class_options, YES_TEXT, NO_TEXT
)
from services import ai_service
from services.presentation import build_presentation, start_files
from services import prefetch
from bot.progress import ProgressMessage
import asyncio
from services.deck import themes
from services import gallery

logger = logging.getLogger(__name__)
router = Router()

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUBJECT_PROMPT = "📚 <b>Fan nomini kiriting:</b>\n\n(Masalan: <i>Biologiya, Fizika, Tarix, Menejment</i>)"
TEACHER_PROMPT = ("👨‍🏫 <b>O‘qituvchingiz ism-familiyasi</b> (ixtiyoriy).\n\n"
                  "<i>Kerak bo‘lmasa «⏭ O‘tkazib yuborish» tugmasini bosing.</i>")
LANG_NAMES = {"uz": "🇺🇿 O‘zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}
MAX_TEXT = 300  # longest answer kept for one wizard field


def _clean(text) -> str:
    return " ".join(str(text or "").split())[:MAX_TEXT]


async def _safe_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False) -> None:
    """Answers a button press; Telegram rejects answers after ~15 s, which must not raise."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception:  # noqa: BLE001
        pass


async def _state_is(state: FSMContext, wanted) -> bool:
    cur = await state.get_state()
    return getattr(cur, "state", cur) == wanted.state


_PLACEHOLDER_HOSTS = {"domeningiz", "your-domain", "your-domain.uz", "example.com", "domain.uz", "localhost"}
_webapp_disabled = False


def webapp_url() -> str:
    """WEBAPP_URL if it can work as a Telegram Mini App address (public https URL), else ""."""
    from urllib.parse import urlparse
    url = (settings.WEBAPP_URL or "").strip()
    if not url or _webapp_disabled:
        return ""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or "." not in host or host in _PLACEHOLDER_HOSTS or host.startswith("127.") or host.endswith(".local"):
        logger.warning("WEBAPP_URL=%r ishlatilmaydi: Mini App uchun haqiqiy https:// manzil kerak (masalan https://bot.sizning-domen.uz/webapp/).", url)
        return ""
    return url if url.endswith("/") else url + "/"


async def webapp_link(bot) -> str:
    """Mini App URL with the bot's username (lets the page hand a choice back via t.me deep link)."""
    url = webapp_url()
    if not url:
        return ""
    try:
        me = await bot.me()
        if getattr(me, "username", None):
            url += ("&" if "?" in url else "?") + "bot=" + me.username
    except Exception:  # noqa: BLE001 - the link works without it
        pass
    return url


def _picker_caption(with_webapp: bool) -> str:
    n = len(themes.list_theme_ids())
    lines = [f"🖼 <b>{n} TA SHABLON — HAR BIRIDA 10 XIL RANG</b>\n",
             "Har bir shablonning tuzilishi, rasmlari va shriftlari o‘ziga xos.\n",
             "📷 <b>201–400: Real foto</b> — slaydlarga mavzuga mos haqiqiy fotosuratlar qo‘yiladi.\n"]
    if with_webapp:
        lines.append("🎨 <b>Dizayn laboratoriyasi</b>da shablonga kirib, slaydlarini va barcha ranglarini ko‘ring.\n")
    lines.append(f"👉 Yoki <b>shablon raqamini</b> yuboring (<code>1</code> – <code>{n}</code>), yoki kategoriyalar bo‘yicha ko‘ring:")
    return "\n".join(lines)


async def apply_template_choice(bot, chat_id: int, state: FSMContext, key) -> bool:
    """Saves the chosen template/colour and moves the wizard on. Shared by buttons, typed numbers,
    the Mini App and /start deep links."""
    key = str(key or "").strip().replace("--", themes.COLOR_SEP)
    if not themes.is_known_theme(key):
        return False
    tid = themes.resolve_theme_id(key)
    t = themes.get_theme(tid)
    current = await state.get_state()
    current = getattr(current, "state", current)
    label = f"№ {int(t.get('code') or 0)} · {escape_html(t.get('name', tid))} · {escape_html(t.get('color_name', ''))}"
    if current in (None, PresentationForm.template_selection.state, PresentationForm.custom_design_prompt.state):
        if current is None:
            await state.set_data({})
        await state.update_data(template_id=tid)
        await state.set_state(PresentationForm.subject)
        started = True
        text = f"✅ <b>{label}</b> tanlandi!\n\n{SUBJECT_PROMPT}"
    else:
        await state.update_data(template_id=tid)
        started = False
        text = f"🎨 <b>Dizayn o‘zgartirildi:</b> {label}"
    try:
        thumb = await gallery.cover_path(tid)
    except Exception:  # noqa: BLE001
        thumb = None
    if thumb and hasattr(bot, "send_photo"):
        try:
            await bot.send_photo(chat_id, FSInputFile(thumb), caption=text, parse_mode="HTML",
                                 reply_markup=get_subject_keyboard() if started else None)
            return True
        except Exception:  # noqa: BLE001 - fall back to text
            logger.exception("cover preview could not be sent")
    await bot.send_message(chat_id, text, parse_mode="HTML",
                           reply_markup=get_subject_keyboard() if started else None)
    return True


@router.message(F.text.in_([
    "🎨 Presentation yaratish", "🎨 Создать презентацию", "🎨 Create Presentation",
    "🖼 Shablonlar", "🖼 Шаблоны", "🖼 Templates",
]))
async def start_pres_wizard(message: Message, state: FSMContext):
    prefetch.drop(message.from_user.id)
    await state.clear()
    await state.set_state(PresentationForm.template_selection)

    global _webapp_disabled
    overview_path = os.path.join(_ROOT, "themes", "overview.jpg")

    async def send_picker(url: str) -> None:
        markup = get_template_selection_inline_keyboard(url)
        if os.path.exists(overview_path):
            await message.answer_photo(photo=FSInputFile(overview_path), caption=_picker_caption(bool(url)),
                                       reply_markup=markup, parse_mode="HTML")
        else:
            await message.answer(_picker_caption(bool(url)), reply_markup=markup, parse_mode="HTML")

    url = await webapp_link(message.bot)
    try:
        await send_picker(url)
    except TelegramBadRequest as e:
        if not url or "web app" not in str(e).lower():
            raise
        # Telegram rejected the Mini App address: keep the bot usable with the inline gallery.
        logger.error("Telegram WEBAPP_URL=%r ni qabul qilmadi (%s). Mini App tugmasi o‘chirildi; .env dagi WEBAPP_URL ni tuzating.", settings.WEBAPP_URL, e)
        _webapp_disabled = True
        await send_picker("")
        return
    if url:
        await message.answer("👇 Galereyani pastdagi tugma orqali ham ochishingiz mumkin.",
                             reply_markup=get_webapp_keyboard(url))


@router.message(F.text.in_(["📄 Referat yaratish", "📄 Создать реферат", "📄 Create Paper"]))
async def referat_soon(message: Message, state: FSMContext):
    await message.answer(
        "📄 <b>Referat xizmati tez orada ishga tushadi.</b>\n\n"
        "Hozircha «🎨 Presentation yaratish» orqali taqdimot tayyorlashingiz mumkin.", parse_mode="HTML")


# ---------------------------------------------------------------- inline gallery (works without the Mini App)
PAGE_SIZE = 8


def _category_ids(category: str) -> list:
    if category == "all":
        return themes.list_theme_ids()
    return [t["id"] for t in themes.catalog() if category in t["categories"]]


async def _show_photo(callback: CallbackQuery, path: str, caption: str, markup) -> None:
    """Replaces the gallery message's photo (or sends a new one if that is not possible)."""
    try:
        await callback.message.edit_media(InputMediaPhoto(media=FSInputFile(path), caption=caption, parse_mode="HTML"),
                                          reply_markup=markup)
    except Exception:  # noqa: BLE001 - not a photo message / too old
        await callback.message.answer_photo(FSInputFile(path), caption=caption, reply_markup=markup, parse_mode="HTML")


async def _edit_markup(callback: CallbackQuery, markup) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except Exception:  # noqa: BLE001 - message too old / unchanged
        await callback.message.answer("👇", reply_markup=markup)


@router.callback_query(F.data == "gal_noop")
async def gallery_noop(callback: CallbackQuery, state: FSMContext):
    await callback.answer()


@router.callback_query(F.data == "gal_home")
async def gallery_home(callback: CallbackQuery, state: FSMContext):
    url = await webapp_link(callback.bot)
    overview_path = os.path.join(_ROOT, "themes", "overview.jpg")
    markup = get_template_selection_inline_keyboard(url)
    if os.path.exists(overview_path) and getattr(callback.message, "photo", None):
        await _show_photo(callback, overview_path, _picker_caption(bool(url)), markup)
    else:
        await _edit_markup(callback, markup)
    await callback.answer()


@router.callback_query(F.data == "gal_cats")
async def gallery_categories(callback: CallbackQuery, state: FSMContext):
    counts = {}
    for t in themes.catalog():
        for c in t["categories"]:
            counts[c] = counts.get(c, 0) + 1
    cats = [(k, label, e, counts.get(k, 0)) for k, label, e, _ in themes.CATEGORIES if counts.get(k)]
    await _edit_markup(callback, get_gallery_categories_keyboard(cats))
    await callback.answer()


@router.callback_query(F.data.startswith("gal_l:"))
async def gallery_list(callback: CallbackQuery, state: FSMContext):
    try:
        _, category, page = callback.data.split(":")
        page = int(page)
    except ValueError:
        await _safe_answer(callback)
        return
    await _safe_answer(callback, "⏳ Yuklanmoqda…")  # covers of photo templates may take a while
    ids = _category_ids(category)
    pages = max(1, (len(ids) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    chunk = ids[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    items = []
    for tid in chunk:
        t = themes.get_theme(tid)
        items.append((tid, t["code"], t["name"]))
    if await state.get_state() is None:
        await state.set_state(PresentationForm.template_selection)
    label = next((f"{e} {lbl}" for k, lbl, e, _ in themes.CATEGORIES if k == category), "🗂 Barcha shablonlar")
    caption = (f"<b>{label}</b> — {len(ids)} ta shablon\n"
               f"Shablonni bosing: uning 10 xil rangi ko‘rinadi.")
    markup = get_gallery_list_keyboard(items, category, page, pages)
    sheet = await gallery.list_sheet_async(chunk, f"{category}_{page}")
    if sheet:
        await _show_photo(callback, sheet, caption, markup)
    else:
        await _edit_markup(callback, markup)


@router.callback_query(F.data.startswith("gal_t:"))
async def gallery_template(callback: CallbackQuery, state: FSMContext):
    tid = callback.data.split(":", 1)[1]
    if tid not in themes.list_theme_ids():
        await _safe_answer(callback, "Topilmadi", show_alert=True)
        return
    await _safe_answer(callback, "⏳ Ranglar yuklanmoqda…")
    if await state.get_state() is None:
        await state.set_state(PresentationForm.template_selection)
    t = themes.get_theme(tid)
    colors = [(c["key"], i + 1, c["name"]) for i, c in enumerate(themes.theme_colors(tid))]
    caption = (f"<b>№ {int(t['code'])}. {escape_html(t['name'])}</b>\n{escape_html(t.get('tagline', ''))}\n"
               f"<i>{escape_html(t.get('category', ''))}</i>\n\n🎨 Rangni tanlang ({len(colors)} ta variant):")
    markup = get_gallery_colors_keyboard(colors)
    sheet = await gallery.colors_sheet_async(tid)
    if sheet:
        await callback.message.answer_photo(FSInputFile(sheet), caption=caption, reply_markup=markup, parse_mode="HTML")
    else:
        await callback.message.answer(caption, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "gal_close")
async def gallery_close(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:  # noqa: BLE001
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("tpl_"))
async def process_template_selection(callback: CallbackQuery, state: FSMContext):
    tpl_code = callback.data.replace("tpl_", "")

    if tpl_code == "ai_custom":
        await state.set_state(PresentationForm.custom_design_prompt)
        await callback.message.answer("🤖 <b>AI Custom Design:</b>\n\nQanday ko'rinishdagi presentation xohlaysiz?\n\n<i>Misol: Ko'k va oq rangli, universitet uchun professional, minimalistik va zamonaviy dizayn.</i>", parse_mode="HTML")
        await callback.answer()
        return

    if tpl_code == "ocr_photo":
        await state.set_state(PresentationForm.ocr_photo_upload)
        await callback.message.answer("📸 <b>Topshiriq rasmini yuborish:</b>\n\nO'qituvchi bergan topshiriq yoki talablar yozilgan vedomost rasmini yuboring.", parse_mode="HTML")
        await callback.answer()
        return

    if not themes.is_known_theme(tpl_code.replace("--", themes.COLOR_SEP)):
        await _safe_answer(callback, "Bu shablon topilmadi", show_alert=True)
        return
    await _safe_answer(callback, "✅ Tanlandi")  # before the cover is rendered (it can take a few seconds)
    await apply_template_choice(callback.bot, callback.message.chat.id, state, tpl_code)


@router.message(F.web_app_data)
async def process_webapp_choice(message: Message, state: FSMContext):
    try:
        key = json.loads(message.web_app_data.data).get("theme", "")
    except (ValueError, AttributeError):
        key = message.web_app_data.data
    if not await apply_template_choice(message.bot, message.chat.id, state, key):
        await message.answer("⚠️ Shablon topilmadi, qaytadan tanlang.")


@router.message(PresentationForm.template_selection, F.text)
async def process_template_number_text(message: Message, state: FSMContext):
    text = message.text.strip().lstrip("#№ ").strip()
    if text.isdigit() and await apply_template_choice(message.bot, message.chat.id, state, str(int(text))):
        return
    n = len(themes.list_theme_ids())
    await message.answer(f"⚠️ Iltimos, <b>1 dan {n} gacha</b> shablon raqamini yuboring (masalan: <code>5</code>, <code>37</code>, <code>142</code>) yoki tugmalardan tanlang.", parse_mode="HTML")


@router.message(PresentationForm.custom_design_prompt, F.text)
async def process_custom_design_prompt(message: Message, state: FSMContext):
    prompt_text = _clean(message.text)
    design_spec = await ai_service.generate_custom_design_spec(prompt_text)
    await state.update_data(template_id="custom_ai", custom_design_spec=design_spec)
    await state.set_state(PresentationForm.subject)
    await message.answer(SUBJECT_PROMPT, parse_mode="HTML", reply_markup=get_subject_keyboard())


# ---------------------------------------------------------------- wizard: buttons for every common answer,
# typing works everywhere too. Order: subject → topic → slides → name → level → institution (optional)
# → class/year → teacher (optional) → date → language → extra wishes (yes/no) → confirmation
async def _limits():
    async with AsyncSessionLocal() as session:
        min_slides = int(await repository.get_setting(session, "min_slides", str(settings.MIN_SLIDES_PER_ORDER)))
        max_slides = int(await repository.get_setting(session, "max_slides", str(settings.MAX_SLIDES_PER_ORDER)))
        price = int(await repository.get_setting(session, "price_per_slide", str(settings.DEFAULT_PRICE_PER_SLIDE)))
    return min_slides, max_slides, price


def _today():
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5)))  # Tashkent time
    return now.strftime("%d.%m.%Y"), str(now.year)


@router.message(PresentationForm.subject, F.text)
async def process_subject(message: Message, state: FSMContext):
    await state.update_data(subject=_clean(message.text))
    await state.set_state(PresentationForm.topic)
    await message.answer("📌 <b>Prezentatsiya mavzusini kiriting:</b>\n\n(Masalan: <i>Fotosintez jarayoni va uning ahamiyati</i>)",
                         parse_mode="HTML", reply_markup=get_cancel_keyboard())

@router.message(PresentationForm.topic, F.text)
async def process_topic(message: Message, state: FSMContext):
    await state.update_data(topic=_clean(message.text))
    await state.set_state(PresentationForm.slide_count)
    min_slides, max_slides, price_per_slide = await _limits()
    await message.answer(
        f"📑 <b>Nechta slayd bo‘lishini xohlaysiz?</b>\n\n"
        f"Minimum: {min_slides}, maksimum: {max_slides} slayd\n"
        f"Narxi: 1 slayd = {price_per_slide} so‘m\n\n"
        f"<i>Tugmani bosing yoki sonini yozing (masalan: 10):</i>",
        parse_mode="HTML", reply_markup=get_slide_count_keyboard(min_slides, max_slides)
    )

@router.message(PresentationForm.slide_count, F.text)
async def process_slide_count(message: Message, state: FSMContext):
    m = re.fullmatch(r"\s*(\d{1,3})\s*(ta|та|slayd|slide|слайд(ов|а)?)?\s*", message.text.lower())
    if not m:
        await message.answer("⚠️ Iltimos, faqat raqam kiriting (Masalan: 10):")
        return

    slide_count = int(m.group(1))
    min_slides, max_slides, _ = await _limits()

    if slide_count < min_slides:
        await message.answer(f"⚠️ Minimum buyurtma miqdori: {min_slides} ta slayd. Qayta kiriting:")
        return

    if slide_count > max_slides:
        await message.answer(f"⚠️ Maksimum buyurtma miqdori: {max_slides} ta slayd. Qayta kiriting:")
        return

    await state.update_data(slide_count=slide_count)
    await state.set_state(PresentationForm.author_name)
    await message.answer("👤 <b>Ism va familiyangizni kiriting:</b>\n\n(Masalan: <i>Doniyorbek Normurodov</i>)",
                         parse_mode="HTML", reply_markup=get_cancel_keyboard())

@router.message(PresentationForm.author_name, F.text)
async def process_author_name(message: Message, state: FSMContext):
    await state.update_data(author_name=_clean(message.text))
    await state.set_state(PresentationForm.level)
    await message.answer("🎓 <b>Ta’lim darajangizni tanlang:</b>", reply_markup=get_level_keyboard(), parse_mode="HTML")

_INSTITUTION_EXAMPLES = {"maktab": "45-son umumta’lim maktabi", "litsey": "TDTU qoshidagi akademik litsey",
                         "kollej": "Toshkent politexnika kolleji", "universitet": "Toshkent davlat iqtisodiyot universiteti"}

@router.message(PresentationForm.level, F.text)
async def process_level(message: Message, state: FSMContext):
    level_text = _clean(message.text)
    await state.update_data(level=level_text)
    await state.set_state(PresentationForm.institution)
    example = next((v for k, v in _INSTITUTION_EXAMPLES.items() if k in level_text.lower()), "Sizning o‘quv dargohingiz")
    await message.answer(f"🏫 <b>Ta’lim muassasangiz nomi</b> (ixtiyoriy)\n\n(Masalan: <i>{escape_html(example)}</i>)\n\n"
                         "<i>Kerak bo‘lmasa «⏭ O‘tkazib yuborish» tugmasini bosing.</i>",
                         reply_markup=get_skip_keyboard(), parse_mode="HTML")

async def _prefetch(message: Message, state: FSMContext) -> None:
    """Starts (or restarts, if an answer changed) writing the text in the background."""
    try:
        if await _preview_allowed(message.from_user.id):
            prefetch.ensure(message.from_user.id, await state.get_data())
    except Exception:  # noqa: BLE001 - the deck is simply written later
        logger.exception("prefetch could not start")


async def _ask_teacher(message: Message, state: FSMContext) -> None:
    await _prefetch(message, state)
    await state.set_state(PresentationForm.teacher_name)
    await message.answer(TEACHER_PROMPT, reply_markup=get_skip_keyboard(), parse_mode="HTML")

@router.message(PresentationForm.institution, F.text)
async def process_institution(message: Message, state: FSMContext):
    await state.update_data(institution="" if message.text.strip() in SKIP_TEXTS else _clean(message.text))
    level = (await state.get_data()).get("level", "")
    if not class_options(level):
        await state.update_data(course="")
        await _ask_teacher(message, state)
        return
    await state.set_state(PresentationForm.course)
    school = "sinf" in class_options(level)[0]
    await message.answer("🎓 <b>Nechanchi sinfda o‘qiysiz?</b>" if school else "🎓 <b>Qaysi kursda o‘qiysiz?</b>",
                         reply_markup=get_course_keyboard(level), parse_mode="HTML")

@router.message(PresentationForm.course, F.text)
async def process_course(message: Message, state: FSMContext):
    await state.update_data(course="" if message.text.strip() in SKIP_TEXTS else _clean(message.text))
    await _ask_teacher(message, state)

@router.message(PresentationForm.teacher_name, F.text)
async def process_teacher_name(message: Message, state: FSMContext):
    teacher = "" if message.text.strip() in SKIP_TEXTS else _clean(message.text)
    await state.update_data(teacher_name=teacher)
    await state.set_state(PresentationForm.date)
    today, year = _today()
    await message.answer("📅 <b>Titul slaydga qaysi sana yozilsin?</b>\n\n<i>Tugmani bosing yoki sanani yozing "
                         "(masalan: 25.10.2026). Kerak bo‘lmasa «⏭ O‘tkazib yuborish».</i>",
                         reply_markup=get_date_keyboard(today, year), parse_mode="HTML")

@router.message(PresentationForm.date, F.text)
async def process_date(message: Message, state: FSMContext):
    text = message.text.strip()
    if text in SKIP_TEXTS:
        date = ""
    else:
        date = text.replace("📅", "").replace("Bugun:", "").strip()[:40]
    await state.update_data(date=date)
    await state.set_state(PresentationForm.language)
    await message.answer("🌐 <b>Prezentatsiya tilini tanlang:</b>", reply_markup=get_language_keyboard(), parse_mode="HTML")

@router.message(PresentationForm.language, F.text)
async def process_language(message: Message, state: FSMContext):
    t = message.text.lower()
    lang_code = "ru" if ("рус" in t or "rus" in t) else "en" if ("english" in t or "ingliz" in t) else "uz"
    await state.update_data(language=lang_code)
    await _prefetch(message, state)  # restarts only if the language differs from the guess
    await state.set_state(PresentationForm.notes_choice)
    await message.answer("📝 <b>Qo‘shimcha talablaringiz bormi?</b>\n\n"
                         "<i>Masalan: «Rasmlar ko‘p bo‘lsin», «Matn qisqa va lo‘nda bo‘lsin».</i>",
                         parse_mode="HTML", reply_markup=get_yes_no_keyboard())

@router.message(PresentationForm.notes_choice, F.text)
async def process_notes_choice(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == YES_TEXT or text.lower() in ("ha", "xa", "да", "yes", "bor"):
        await state.set_state(PresentationForm.additional_notes)
        await message.answer("✍️ <b>Talablaringizni yozing:</b>", parse_mode="HTML", reply_markup=get_cancel_keyboard())
        return
    if text == NO_TEXT or text in SKIP_TEXTS or text.lower() in ("yo'q", "yoq", "yo‘q", "нет", "no"):
        data = await state.get_data()
        await _finish_notes(message, state, data.get("ocr_notes", ""))
        return
    await _finish_notes(message, state, _clean(message.text))  # wishes typed straight away

@router.message(PresentationForm.additional_notes, F.text)
async def process_additional_notes(message: Message, state: FSMContext):
    notes = "" if message.text.strip() in SKIP_TEXTS else _clean(message.text)
    await _finish_notes(message, state, notes)

async def _finish_notes(message: Message, state: FSMContext, notes: str) -> None:
    data = await state.get_data()
    ocr = data.get("ocr_notes", "")
    if ocr and notes and ocr not in notes:
        notes = f"{ocr}. {notes}"
    await state.update_data(additional_notes=notes)
    await _prefetch(message, state)  # extra wishes change the text: start over with them
    data = await state.get_data()
    _, _, price_per_slide = await _limits()

    slide_count = int(data.get("slide_count", 10))
    total_price = slide_count * price_per_slide
    await state.update_data(total_price=total_price)

    rows = [("📚", "Fan", data.get("subject")), ("📌", "Mavzu", data.get("topic")),
            ("📑", "Slaydlar soni", f"{slide_count} ta"), ("👤", "Muallif", data.get("author_name")),
            ("🎓", "Daraja", " · ".join(x for x in (data.get("level"), data.get("course")) if x)),
            ("🏫", "Muassasa", data.get("institution")), ("👨‍🏫", "O‘qituvchi", data.get("teacher_name")),
            ("📅", "Sana", data.get("date")),
            ("🌐", "Til", LANG_NAMES.get(data.get("language"), data.get("language"))),
            ("📝", "Talablar", notes)]
    lines = "".join(f"{e} <b>{k}:</b> {escape_html(v)}\n" for e, k, v in rows if v)
    summary_text = (
        f"📊 <b>BUYURTMA TASDIQLASH:</b>\n\n{lines}"
        f"💰 <b>Jami narx:</b> {total_price} so‘m\n\n"
        f"Prezentatsiyani generatsiya qilishni tasdiqlaysizmi?"
    )

    await state.set_state(PresentationForm.confirmation)
    # removes the yes/no keyboard (a message cannot carry both a reply keyboard and inline buttons)
    await message.answer("👌 Ma’lumotlar qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(summary_text, reply_markup=get_confirmation_inline_keyboard("temp_order"), parse_mode="HTML")

# ---------------------------------------------------------------- limits for expensive work
_build_sem = None
_build_waiting = 0


def _sem():
    global _build_sem
    if _build_sem is None:
        import asyncio
        _build_sem = asyncio.Semaphore(max(1, int(settings.MAX_PARALLEL_BUILDS)))
    return _build_sem


class _build_slot:
    """At most MAX_PARALLEL_BUILDS presentations are built at once; the rest wait in a queue
    (the server stays responsive however many people press «create» at the same moment)."""

    def __init__(self, bar=None):
        self.bar = bar

    async def __aenter__(self):
        global _build_waiting
        sem = _sem()
        if sem.locked() and self.bar is not None:
            self.bar.note = (f"⏳ <b>Navbatdasiz</b> ({_build_waiting + 1}-o‘rin) — hozir boshqa taqdimotlar "
                             "tayyorlanmoqda, bir oz kuting…")
            try:
                await self.bar.refresh(force=True)
            except Exception:  # noqa: BLE001
                pass
        _build_waiting += 1
        try:
            await sem.acquire()
        finally:
            _build_waiting -= 1
        if self.bar is not None:
            self.bar.note = ""
        return self

    async def __aexit__(self, *exc):
        _sem().release()
        return False


async def _preview_allowed(user_id: int) -> bool:
    """Unpaid previews per user per day (each one costs AI requests). Admins are not limited."""
    if user_id in settings.admin_id_list or int(settings.MAX_PREVIEWS_PER_DAY) <= 0:
        return True
    import datetime as _dt
    since = _dt.datetime.utcnow() - _dt.timedelta(days=1)
    try:
        async with AsyncSessionLocal() as session:
            n = await repository.count_user_orders_since(session, user_id, since)
    except Exception:  # noqa: BLE001 - never block a user because of a database hiccup
        return True
    return n < int(settings.MAX_PREVIEWS_PER_DAY)


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


async def _send_outline(message: Message, outline: dict, data: dict) -> None:
    lang = data.get("language", "uz")
    plan = escape_html(ai_service.outline_to_text(outline, lang))
    text = (
        "📋 <b>TAQDIMOT REJASI</b>\n\n"
        f"<b>{escape_html(outline.get('title', ''))}</b>\n\n"
        f"{plan}\n\n"
        "Reja ma’qul bo‘lsa, tasdiqlang. Har bir slayd shu reja asosida yoziladi va chiziladi.\n"
        "<i>O‘zgartirish kerak bo‘lsa, «✏️ O‘zgartirish kiritish» tugmasini bosing va nimani o‘zgartirishni yozing.</i>"
    )
    await message.answer(text, reply_markup=get_outline_inline_keyboard(), parse_mode="HTML")


MAX_OUTLINES_PER_ORDER = 8  # plan rewrites per order (each one is an AI request)


async def _make_outline(message: Message, state: FSMContext, **kwargs) -> None:
    """Writes the plan once (the wait state ignores repeated presses) and shows it."""
    data = await state.get_data()
    n = int(data.get("outline_count", 0))
    if n >= MAX_OUTLINES_PER_ORDER and data.get("outline"):
        await state.set_state(PresentationForm.outline_review)
        await message.answer("⚠️ Reja juda ko‘p marta o‘zgartirildi. Mavjud rejani tasdiqlang yoki /start bilan qaytadan boshlang.")
        await _send_outline(message, data["outline"], data)
        return
    await state.update_data(outline_count=n + 1)
    await state.set_state(PresentationForm.outline_wait)
    data = await state.get_data()
    try:
        outline = await ai_service.generate_outline(data, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("outline failed")
        outline = ai_service.generate_mock_outline(data)
    if not await _state_is(state, PresentationForm.outline_wait):
        return  # the user cancelled or started a new order meanwhile
    await state.update_data(outline=outline)
    await state.set_state(PresentationForm.outline_review)
    await _send_outline(message, outline, data)


@router.callback_query(PresentationForm.confirmation, F.data == "show_plan")
async def confirm_and_show_outline(callback: CallbackQuery, state: FSMContext):
    """«📋 Avval rejani ko‘rish»: the plan first (instant when it was already written in the background)."""
    await _safe_answer(callback, "🧠 Reja tayyorlanmoqda...")
    try:
        await callback.message.edit_text("🧠 <b>AI taqdimot rejasini tuzmoqda...</b>", parse_mode="HTML")
    except Exception:  # noqa: BLE001
        pass
    data = await state.get_data()
    job = prefetch.get(callback.from_user.id, data)
    if job is not None:
        await state.set_state(PresentationForm.outline_wait)
        try:
            await asyncio.wait_for(job.outline_ready.wait(), timeout=120)
        except asyncio.TimeoutError:
            pass
        if job.outline and await _state_is(state, PresentationForm.outline_wait):
            await state.update_data(outline=job.outline, outline_count=1)
            await state.set_state(PresentationForm.outline_review)
            await _send_outline(callback.message, job.outline, data)
            return
    await _make_outline(callback.message, state)


@router.callback_query(PresentationForm.outline_review, F.data == "outline_regen")
async def regenerate_outline(callback: CallbackQuery, state: FSMContext):
    await _safe_answer(callback, "🔄 Yangi reja tuzilmoqda...")
    data = await state.get_data()
    await _make_outline(callback.message, state, previous=data.get("outline"))


@router.callback_query(PresentationForm.outline_review, F.data == "outline_edit")
async def ask_outline_changes(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PresentationForm.outline_edit)
    await callback.message.answer(
        "✏️ <b>Rejada nimani o‘zgartiraylik?</b>\n\n"
        "<i>Masalan: «4-slaydni olib tashla», «Kalvin sikli haqida alohida slayd qo‘sh», «tarixiy qismni qisqartir».</i>",
        parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(PresentationForm.outline_edit, F.text)
async def apply_outline_changes(message: Message, state: FSMContext):
    data = await state.get_data()
    wait = await message.answer("🧠 Reja yangilanmoqda...")
    await _make_outline(message, state, feedback=_clean(message.text), previous=data.get("outline"))
    try:
        await wait.delete()
    except Exception:
        pass


async def _build_and_send(message: Message, user_id: int, state: FSMContext, back_state) -> None:
    """Makes the deck (reusing text written in the background when the answers still match),
    shows an animated progress bar, sends the previews and the payment buttons; the PDF and PPTX
    are finished in the background."""
    await state.set_state(PresentationForm.generating)  # a second press of the button is ignored
    data = await state.get_data()
    if not await _preview_allowed(user_id):
        await state.set_state(back_state)
        await message.answer(
            f"⚠️ Bugun {settings.MAX_PREVIEWS_PER_DAY} ta taqdimot namunasini yaratdingiz — bu kunlik chegara.\n"
            "Avvalgi buyurtmalaringizni to‘lab yuklab olishingiz mumkin yoki ertaga davom eting.")
        return
    # the main menu comes back here (the wizard's reply keyboards are no longer needed); the progress
    # message is separate because messages with a reply keyboard cannot be edited later
    await message.answer("✅ Qabul qilindi! Taqdimot tayyor bo‘lishi bilan shu yerga yuboraman.",
                         reply_markup=get_main_menu_keyboard())
    status = await message.answer("🎨 <b>Taqdimotingiz tayyorlanmoqda</b>\n\n<code>▱▱▱▱▱▱▱▱▱▱▱▱</code>  <b>0%</b>",
                                  parse_mode="HTML")
    bar = ProgressMessage(status).start()

    import uuid
    storage_dir = os.path.join(_project_root(), "storage", str(uuid.uuid4()))
    tpl_id = data.get("template_id", "05_nature_organic")
    slide_count = int(data.get("slide_count", 10))
    outline = data.get("outline")

    try:
        async with _build_slot(bar):
            content = None
            job = prefetch.take(user_id, data)
            if job is not None and (outline is None or outline == job.outline):
                # written in the background while the user was answering: follow its progress
                while not job.task.done():
                    await bar.set("write", job.done, job.total or slide_count)
                    await asyncio.sleep(0.5)
                try:
                    content = job.task.result()
                except Exception:  # noqa: BLE001 - write it again below
                    logger.exception("background writing failed; writing again")
            elif job is not None:
                job.cancel()
            result = await build_presentation(data, storage_dir, outline=outline, progress=bar.set, content=content)
    except Exception:
        await bar.stop()
        logger.exception("Presentation build failed")
        if await _state_is(state, PresentationForm.generating):
            await state.set_state(back_state)  # the create button can be pressed again
        await message.answer(
            "⚠️ Taqdimotni yaratishda xatolik yuz berdi. Birozdan so‘ng «✅» tugmasini qayta bosing "
            "yoki /start bilan boshidan boshlang.")
        return
    start_files(storage_dir)  # PDF + PPTX are ready long before anyone pays
    await bar.finish()

    async with AsyncSessionLocal() as session:
        order = await repository.create_presentation_order(
            session=session,
            user_id=user_id,
            topic=data.get("topic", ""),
            subject=data.get("subject", ""),
            slide_count=slide_count,
            template_id=tpl_id if isinstance(tpl_id, str) else "custom_ai",
            total_price=data.get("total_price", 3500),
            pptx_path=result.pptx_path,
            pdf_path=result.pdf_path
        )
        order_id = order.id

    try:
        await status.delete()
    except Exception:
        pass

    media_group = []
    for idx, p_path in enumerate(result.previews):
        media_group.append(InputMediaPhoto(
            media=FSInputFile(p_path),
            caption="🔍 Namuna slaydlar (SLIDELAB • PREVIEW)" if idx == 0 else ""
        ))
    if result.overview:
        media_group.append(InputMediaPhoto(media=FSInputFile(result.overview)))
    try:
        if len(media_group) >= 2:
            await message.answer_media_group(media=media_group[:10])
        elif media_group:
            await message.answer_photo(media_group[0].media, caption=media_group[0].caption)
    except Exception:  # noqa: BLE001 - the payment message must still arrive
        logger.exception("preview images could not be sent")

    total_price = data.get("total_price", 3500)
    warning_text = (
        f"⚠️ <b>Preview haqida</b>\n\n"
        f"Yuqorida ikki namuna slayd va barcha {slide_count} ta slaydning kichik ko‘rinishi berildi. "
        f"Ularda <code>SLIDELAB • PREVIEW • @SlideLabBot</code> belgisi bor.\n\n"
        f"💳 <b>To‘lov amalga oshirilgandan so‘ng:</b>\n"
        f"• barcha {slide_count} ta slayd to‘liq sifatda ochiladi;\n"
        f"• belgilar olib tashlanadi;\n"
        f"• PowerPoint (.pptx, matnini tahrirlash mumkin) va PDF fayllar beriladi.\n\n"
        f"📊 <b>Slaydlar soni:</b> {slide_count} ta\n"
        f"💰 <b>Narxi:</b> {total_price} so'm"
    )
    payment_keyboard = (
        get_production_payment_inline_keyboard(order_id, total_price)
        if settings.PAYMENT_ENV.upper() == "PRODUCTION"
        else get_payment_inline_keyboard(order_id, total_price)
    )
    await message.answer(warning_text, reply_markup=payment_keyboard, parse_mode="HTML")
    if await _state_is(state, PresentationForm.generating):  # never wipe a new order started meanwhile
        await state.clear()


@router.callback_query(PresentationForm.confirmation, F.data.startswith("confirm_pres_"))
async def confirm_and_create(callback: CallbackQuery, state: FSMContext):
    """«✅ Tasdiqlash va yaratish»: straight to the slides, no plan review."""
    await _safe_answer(callback, "⚡️ Taqdimot tayyorlanmoqda...")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await _build_and_send(callback.message, callback.from_user.id, state, PresentationForm.confirmation)


@router.callback_query(PresentationForm.outline_review, F.data == "outline_ok")
async def generate_and_preview_presentation(callback: CallbackQuery, state: FSMContext):
    await _safe_answer(callback, "⚡️ Prezentatsiya tayyorlanmoqda...")
    await _build_and_send(callback.message, callback.from_user.id, state, PresentationForm.outline_review)


@router.callback_query(F.data == "cancel_pres")
async def cancel_presentation_creation(callback: CallbackQuery, state: FSMContext):
    await _safe_answer(callback)
    if await _state_is(state, PresentationForm.generating):
        await callback.message.answer("⏳ Taqdimot allaqachon tayyorlanmoqda, bir oz kuting.")
        return
    await state.clear()
    prefetch.drop(callback.from_user.id)
    try:
        await callback.message.edit_text("❌ Prezentatsiya yaratish bekor qilindi.", parse_mode="HTML")
    except Exception:  # noqa: BLE001
        pass
    await callback.message.answer("🏠 Asosiy menyu", reply_markup=get_main_menu_keyboard())


# ---------------------------------------------------------------- anything else (registered last)
_BUTTON_STATES = (PresentationForm.confirmation, PresentationForm.outline_review)
_WAIT_STATES = (PresentationForm.outline_wait, PresentationForm.generating)


@router.message(StateFilter(*_WAIT_STATES))
async def busy_message(message: Message, state: FSMContext):
    await message.answer("⏳ Taqdimotingiz tayyorlanmoqda, bir oz kuting…")


@router.message(StateFilter(*_BUTTON_STATES))
async def press_a_button(message: Message, state: FSMContext):
    await message.answer("👆 Iltimos, yuqoridagi xabardagi tugmalardan birini bosing.")


@router.message(StateFilter(PresentationForm))
async def text_expected(message: Message, state: FSMContext):
    """A sticker, photo, voice… where the wizard waits for text."""
    await message.answer("✍️ Iltimos, javobni <b>matn</b> ko‘rinishida yuboring.\n"
                         "<i>Bekor qilish uchun «❌ Bekor qilish» yoki /cancel.</i>", parse_mode="HTML")


@router.message(StateFilter(None), F.text)
async def unknown_text(message: Message, state: FSMContext):
    await message.answer("👇 Kerakli bo‘limni pastdagi menyudan tanlang (yoki /start).",
                         reply_markup=get_main_menu_keyboard())
