"""
Design step after a template is chosen: the title font, the body text font (from a library of
160 fonts) and the text colour. Every change shows the cover of the presentation in the new style.

    template chosen -> [style menu] -> fonts / colour pickers -> «➡️ Davom etish» -> subject question

The choices are kept in the wizard data (font_title, font_body, text_color); see
services/presentation.theme_key_from_data and services/deck/themes.apply_style.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from PIL import Image

from bot.states.forms import PresentationForm
from bot.utils import escape_html
from services import font_gallery, gallery
from services.deck import fonts, themes

logger = logging.getLogger(__name__)
router = Router()

ROLES = {"t": ("title", "Sarlavha shrifti"), "b": ("body", "Matn shrifti")}
CAT_ICONS = {"modern": "✨", "classic": "📜", "display": "💥", "hand": "✍️", "tech": "💻"}
COLORS = [  # (emoji, name, hex)
    ("⬛", "Qora", "#111827"), ("🌑", "To‘q kulrang", "#374151"), ("⬜", "Oq", "#FFFFFF"), ("🤍", "Krem", "#FDF6E3"),
    ("🟦", "To‘q ko‘k", "#1E3A8A"), ("🔵", "Ko‘k", "#2563EB"), ("🩵", "Och ko‘k", "#BAE6FD"), ("🌊", "Moviy", "#0E7490"),
    ("🟩", "Yashil", "#15803D"), ("🌿", "Zumrad", "#047857"), ("🍏", "Yalpiz", "#A7F3D0"), ("🟥", "Qizil", "#DC2626"),
    ("🍷", "Bordo", "#881337"), ("🟧", "To‘q sariq", "#EA580C"), ("🟨", "Sariq", "#FACC15"), ("🏅", "Oltin", "#B45309"),
    ("🟪", "Binafsha", "#7C3AED"), ("💜", "Lavanda", "#DDD6FE"), ("🌸", "Pushti", "#DB2777"), ("🟫", "Jigarrang", "#78350F"),
]
STYLE_VERSION = "1"  # bump when apply_style changes so cached covers are drawn again
PREVIEW_DIR = os.path.join(gallery.ROOT, "storage", "preview_cache", "styled")
_render_sem: Optional[asyncio.Semaphore] = None
WIZARD_DONE_STATES = (PresentationForm.generating.state,)


# ---------------------------------------------------------------------- helpers
def _font_name(fid: Optional[str]) -> str:
    return fonts.family_name(fid) if fid else "shablondagi"


def _color_name(hex_: Optional[str]) -> str:
    return next((f"{e} {n}" for e, n, h in COLORS if h == hex_), hex_) if hex_ else "shablondagi"


def _base_key(data: dict):
    tpl = data.get("template_id", themes.DEFAULT_THEME)
    if tpl == "custom_ai" and data.get("custom_design_spec"):
        return data["custom_design_spec"]
    return tpl


def _has_style(data: dict) -> bool:
    return bool(data.get("font_title") or data.get("font_body") or data.get("text_color"))


def clean_style(raw: Optional[dict], template_key=None) -> dict:
    """Fonts and text colour sent by the Mini App, keeping only known fonts and offered colours."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for role in ("title", "body"):
        fid = str(raw.get(f"font_{role}") or "")
        if fid and fonts.is_library_font(fid):
            out[f"font_{role}"] = fid
    color = str(raw.get("text_color") or "").upper()
    if color:
        allowed = {c[3].upper() for c in allowed_colors({"template_id": template_key})} if template_key else \
            {h.upper() for _, _, h in COLORS}
        if color in allowed:
            out["text_color"] = next(h for _, _, h in COLORS if h.upper() == color)
    return out


def allowed_colors(data: dict) -> list:
    """Only colours that stay readable on this template's background and cards."""
    t = themes.get_theme(_base_key(data))
    p = t.get("palette", {})
    bgs = [c for c in (p.get("bg"), p.get("surface")) if c and len(c) == 7]
    out = []
    for i, (emoji, name, hex_) in enumerate(COLORS):
        if all(themes.contrast(hex_, bg) >= 3.2 for bg in bgs or ["#FFFFFF"]):
            out.append((i, emoji, name, hex_))
    return out


def _label(data: dict) -> str:
    tpl = data.get("template_id")
    if tpl == "custom_ai":
        return "AI dizayn"
    t = themes.get_theme(tpl)
    return f"№ {int(t.get('code') or 0)} · {escape_html(t.get('name', ''))} · {escape_html(t.get('color_name', ''))}"


def menu_caption(data: dict, note: str = "") -> str:
    head = f"{note}\n\n" if note else ""
    return (f"{head}🎨 <b>Dizaynni sozlang</b> — {_label(data)}\n\n"
            f"🔤 Sarlavha shrifti: <b>{escape_html(_font_name(data.get('font_title')))}</b>\n"
            f"🔤 Matn shrifti: <b>{escape_html(_font_name(data.get('font_body')))}</b>\n"
            f"🎨 Yozuv rangi: <b>{escape_html(_color_name(data.get('text_color')))}</b>\n\n"
            f"<i>{len(fonts.library_fonts())} ta shrift va {len(COLORS)} xil rang bor. Rasmda — muqovangiz shu ko‘rinishda "
            "bo‘ladi.</i>\n👉 Tayyor bo‘lsa <b>«➡️ Davom etish»</b>ni bosing.")


def menu_keyboard(data: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔤 Sarlavha shrifti", callback_data="st_f:t"),
         InlineKeyboardButton(text="🔤 Matn shrifti", callback_data="st_f:b")],
        [InlineKeyboardButton(text="🎨 Yozuv rangi", callback_data="st_col")],
    ]
    if _has_style(data):
        rows.append([InlineKeyboardButton(text="♻️ Shablondagi holiga qaytarish", callback_data="st_reset")])
    rows.append([InlineKeyboardButton(text="➡️ Davom etish", callback_data="st_go")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def preview_path(data: dict) -> Optional[str]:
    """Cover of the template in the chosen style (cached by style)."""
    base = _base_key(data)
    if not _has_style(data):
        if isinstance(base, str):
            try:
                return await gallery.cover_path(base)
            except Exception:  # noqa: BLE001
                return None
    from services.presentation import theme_key_from_data
    key = theme_key_from_data({k: v for k, v in data.items() if k != "language"})
    digest = hashlib.sha1((STYLE_VERSION + json.dumps(key, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()[:20]
    dst = os.path.join(PREVIEW_DIR, f"{digest}.jpg")
    if os.path.exists(dst):
        return dst
    global _render_sem
    if _render_sem is None:
        _render_sem = asyncio.Semaphore(2)
    from services.deck import render_deck
    tmp = tempfile.mkdtemp(prefix="style_")
    try:
        async with _render_sem:
            live = isinstance(base, str) and gallery.is_live(base)
            res = await render_deck(gallery.sample_content(True, base if live else ""), key, tmp, want_pdf=False,
                                    want_pptx=False, png_scale=0.5, fetch_images=live)
        if not res.slide_pngs:
            return None
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        Image.open(res.slide_pngs[0]).convert("RGB").save(dst, quality=86)
        return dst
    except Exception:  # noqa: BLE001 - the menu works without a picture
        logger.exception("styled cover preview failed")
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def _replace(callback: Optional[CallbackQuery], bot, chat_id: int, photo: Optional[str], caption: str,
                   markup: InlineKeyboardMarkup) -> None:
    """Edits the menu message in place when possible (keeps the chat tidy), else sends a new one."""
    if callback is not None and callback.message is not None:
        try:
            if photo and getattr(callback.message, "photo", None):
                await callback.message.edit_media(InputMediaPhoto(media=FSInputFile(photo), caption=caption,
                                                                  parse_mode="HTML"), reply_markup=markup)
                return
            if not photo and getattr(callback.message, "photo", None):
                await callback.message.edit_caption(caption=caption, parse_mode="HTML", reply_markup=markup)
                return
            if not photo:
                await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=markup)
                return
        except Exception:  # noqa: BLE001 - too old / not editable: send a new message
            pass
    if photo:
        try:
            await bot.send_photo(chat_id, FSInputFile(photo), caption=caption, parse_mode="HTML", reply_markup=markup)
            return
        except Exception:  # noqa: BLE001
            logger.exception("style menu photo not sent")
    await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=markup)


async def show_menu(bot, chat_id: int, state: FSMContext, note: str = "",
                    callback: Optional[CallbackQuery] = None) -> None:
    data = await state.get_data()
    photo = await preview_path(data)
    await _replace(callback, bot, chat_id, photo, menu_caption(data, note), menu_keyboard(data))


async def _in_wizard(callback: CallbackQuery, state: FSMContext) -> bool:
    cur = await state.get_state()
    cur = getattr(cur, "state", cur)
    if cur is None or not str(cur).startswith("PresentationForm:") or cur in WIZARD_DONE_STATES:
        try:
            await callback.answer("Bu menyu eskirgan — yangi taqdimotni «🎨 Presentation yaratish» orqali boshlang.",
                                  show_alert=True)
        except Exception:  # noqa: BLE001
            pass
        return False
    return True


async def _ack(callback: CallbackQuery, text: str = "") -> None:
    try:
        await callback.answer(text)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------- menu
@router.callback_query(F.data == "st_menu")
async def style_menu(callback: CallbackQuery, state: FSMContext):
    if not await _in_wizard(callback, state):
        return
    await _ack(callback)
    await show_menu(callback.bot, callback.message.chat.id, state, callback=callback)


@router.callback_query(F.data == "st_reset")
async def style_reset(callback: CallbackQuery, state: FSMContext):
    if not await _in_wizard(callback, state):
        return
    await _ack(callback, "♻️ Shablondagi holiga qaytdi")
    await state.update_data(font_title=None, font_body=None, text_color=None)
    await show_menu(callback.bot, callback.message.chat.id, state, callback=callback)


@router.callback_query(F.data == "st_go")
async def style_continue(callback: CallbackQuery, state: FSMContext):
    from bot.handlers.create_pres import SUBJECT_PROMPT
    from bot.keyboards.reply import get_subject_keyboard
    cur = await state.get_state()
    if getattr(cur, "state", cur) != PresentationForm.style.state:
        if await _in_wizard(callback, state):
            await _ack(callback, "✅ Saqlandi")
        return
    await _ack(callback, "✅ Dizayn saqlandi")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await state.set_state(PresentationForm.subject)
    await callback.message.answer(SUBJECT_PROMPT, parse_mode="HTML", reply_markup=get_subject_keyboard())


# ---------------------------------------------------------------------- fonts
def categories_keyboard(role: str) -> InlineKeyboardMarkup:
    cats = fonts.library_categories()
    counts = {}
    for e in fonts.library_fonts():
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    rows, row = [], []
    for key, label in cats.items():
        if not counts.get(key):
            continue
        row.append(InlineKeyboardButton(text=f"{CAT_ICONS.get(key, '🔤')} {label} ({counts[key]})",
                                        callback_data=f"st_c:{role}:{key}:0"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"🗂 Hammasi ({len(fonts.library_fonts())})", callback_data=f"st_c:{role}:all:0")])
    rows.append([InlineKeyboardButton(text="♻️ Shablondagi shrift", callback_data=f"st_d:{role}"),
                 InlineKeyboardButton(text="⬅️ Orqaga", callback_data="st_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("st_f:"))
async def font_categories(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":", 1)[1]
    if role not in ROLES or not await _in_wizard(callback, state):
        return
    await _ack(callback)
    data = await state.get_data()
    _, title = ROLES[role]
    caption = (f"🔤 <b>{title}</b> — hozir: <b>{escape_html(_font_name(data.get('font_' + ROLES[role][0])))}</b>\n\n"
               f"{len(fonts.library_fonts())} ta shrift. Turini tanlang 👇")
    await _replace(callback, callback.bot, callback.message.chat.id, None, caption, categories_keyboard(role))


def list_keyboard(role: str, category: str, page: int, pages: int, items: list) -> InlineKeyboardMarkup:
    rows, row = [], []
    for k, e in enumerate(items):
        n = page * font_gallery.PAGE + k + 1
        row.append(InlineKeyboardButton(text=f"{n}. {e['name']}", callback_data=f"st_s:{role}:{e['index']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if pages > 1:
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"st_c:{role}:{category}:{(page - 1) % pages}"),
            InlineKeyboardButton(text=f"{page + 1} / {pages}", callback_data="gal_noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"st_c:{role}:{category}:{(page + 1) % pages}"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Turlar", callback_data=f"st_f:{role}"),
                 InlineKeyboardButton(text="🏠 Menyu", callback_data="st_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("st_c:"))
async def font_list(callback: CallbackQuery, state: FSMContext):
    try:
        _, role, category, page = callback.data.split(":")
        page = int(page)
    except ValueError:
        await _ack(callback)
        return
    if role not in ROLES or not await _in_wizard(callback, state):
        return
    if category != "all" and category not in fonts.library_categories():
        await _ack(callback)
        return
    await _ack(callback, "⏳")
    pages = font_gallery.pages(category)
    page = min(max(page, 0), pages - 1)
    items = font_gallery.page_fonts(category, page)
    role_name, title = ROLES[role]
    photo = await asyncio.to_thread(font_gallery.sheet, category, page, role_name)
    label = "Hammasi" if category == "all" else fonts.library_categories()[category]
    caption = (f"🔤 <b>{title}</b> · {CAT_ICONS.get(category, '🗂')} {label} ({page + 1}/{pages})\n\n"
               "Yoqqan shriftni bosing 👇\n<i>RU — rus tilini ham yozadi.</i>")
    await _replace(callback, callback.bot, callback.message.chat.id, photo, caption,
                   list_keyboard(role, category, page, pages, items))


@router.callback_query(F.data.startswith("st_s:"))
async def font_selected(callback: CallbackQuery, state: FSMContext):
    try:
        _, role, idx = callback.data.split(":")
        entry = fonts.library_fonts()[int(idx)]
    except (ValueError, IndexError):
        await _ack(callback)
        return
    if role not in ROLES or not await _in_wizard(callback, state):
        return
    role_name, title = ROLES[role]
    await _ack(callback, f"✅ {entry['name']} — ko‘rinish tayyorlanmoqda…")
    await state.update_data(**{f"font_{role_name}": entry["key"]})
    note = f"✅ {title}: <b>{escape_html(entry['name'])}</b>"
    if not entry.get("cyrillic"):
        note += "\n<i>Bu shrift rus tilini yozmaydi: ruscha taqdimotda o‘xshash shrift qo‘yiladi.</i>"
    await show_menu(callback.bot, callback.message.chat.id, state, note=note, callback=callback)


@router.callback_query(F.data.startswith("st_d:"))
async def font_default(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":", 1)[1]
    if role not in ROLES or not await _in_wizard(callback, state):
        return
    await _ack(callback, "♻️ Shablondagi shrift")
    await state.update_data(**{f"font_{ROLES[role][0]}": None})
    await show_menu(callback.bot, callback.message.chat.id, state, callback=callback)


# ---------------------------------------------------------------------- text colour
@router.callback_query(F.data == "st_col")
async def color_menu(callback: CallbackQuery, state: FSMContext):
    if not await _in_wizard(callback, state):
        return
    await _ack(callback)
    data = await state.get_data()
    options = allowed_colors(data)
    rows, row = [], []
    for i, emoji, name, _ in options:
        row.append(InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"st_k:{i}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="♻️ Shablondagi rang", callback_data="st_k:-1"),
                 InlineKeyboardButton(text="⬅️ Orqaga", callback_data="st_menu")])
    hidden = len(COLORS) - len(options)
    caption = (f"🎨 <b>Yozuv rangi</b> — hozir: <b>{escape_html(_color_name(data.get('text_color')))}</b>\n\n"
               "Sarlavhalar va matn shu rangda bo‘ladi.")
    if hidden:
        caption += f"\n<i>Bu shablon fonida o‘qilmaydigan {hidden} ta rang ko‘rsatilmadi.</i>"
    await _replace(callback, callback.bot, callback.message.chat.id, None, caption,
                   InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("st_k:"))
async def color_selected(callback: CallbackQuery, state: FSMContext):
    try:
        i = int(callback.data.split(":", 1)[1])
    except ValueError:
        await _ack(callback)
        return
    if not await _in_wizard(callback, state):
        return
    if i < 0:
        await _ack(callback, "♻️ Shablondagi rang")
        await state.update_data(text_color=None)
        await show_menu(callback.bot, callback.message.chat.id, state, callback=callback)
        return
    if i >= len(COLORS):
        await _ack(callback)
        return
    emoji, name, hex_ = COLORS[i]
    await _ack(callback, f"✅ {name} — ko‘rinish tayyorlanmoqda…")
    await state.update_data(text_color=hex_)
    await show_menu(callback.bot, callback.message.chat.id, state, note=f"✅ Yozuv rangi: <b>{emoji} {name}</b>",
                    callback=callback)
