from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

def get_template_selection_inline_keyboard(webapp_url: str = "") -> InlineKeyboardMarkup:
    kb = []
    if webapp_url:
        from services.deck import themes
        n = len(themes.list_theme_ids())
        kb.append([InlineKeyboardButton(text=f"🎨 Dizayn laboratoriyasi — {n} shablon", web_app=WebAppInfo(url=webapp_url))])
    kb += [
        [InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="gal_cats"),
         InlineKeyboardButton(text="🗂 Barcha shablonlar", callback_data="gal_l:all:0")],
        [InlineKeyboardButton(text="🤖 AI orqali maxsus dizayn yaratish", callback_data="tpl_ai_custom")],
        [InlineKeyboardButton(text="📸 Topshiriq rasmini yuborish", callback_data="tpl_ocr_photo")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_gallery_categories_keyboard(categories) -> InlineKeyboardMarkup:
    """categories: [(key, label, emoji, count)]"""
    btns = [InlineKeyboardButton(text=f"{e} {label} ({n})", callback_data=f"gal_l:{key}:0") for key, label, e, n in categories]
    kb = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="gal_home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_gallery_list_keyboard(items, category: str, page: int, pages: int) -> InlineKeyboardMarkup:
    """items: [(template_id, code, name)] for one page of a category."""
    btns = [InlineKeyboardButton(text=f"{int(code)}. {name}", callback_data=f"gal_t:{tid}") for tid, code, name in items]
    kb = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"gal_l:{category}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1} / {pages}", callback_data="gal_noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"gal_l:{category}:{page + 1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="gal_cats"),
               InlineKeyboardButton(text="🏠 Boshiga", callback_data="gal_home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_gallery_colors_keyboard(colors) -> InlineKeyboardMarkup:
    """colors: [(theme_key, number, colour_name)] — one template's colour sets."""
    btns = [InlineKeyboardButton(text=f"{n}. {name}", callback_data=f"tpl_{key}") for key, n, name in colors]
    kb = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    kb.append([InlineKeyboardButton(text="⬅️ Boshqa shablonlar", callback_data="gal_close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_confirmation_inline_keyboard(order_id: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Tasdiqlash va yaratish", callback_data=f"confirm_pres_{order_id}")],
        [InlineKeyboardButton(text="📋 Avval rejani ko‘rish", callback_data="show_plan")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_pres")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_outline_inline_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Rejani tasdiqlash va slaydlarni yaratish", callback_data="outline_ok")],
        [InlineKeyboardButton(text="✏️ O‘zgartirish kiritish", callback_data="outline_edit"),
         InlineKeyboardButton(text="🔄 Boshqa variant", callback_data="outline_regen")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_pres")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_payment_inline_keyboard(order_id: str, amount: int) -> InlineKeyboardMarkup:
    formatted_amount = f"{amount:,}".replace(",", " ")
    kb = [
        [InlineKeyboardButton(text=f"💳 To'lov qilish ({formatted_amount} UZS)", callback_data=f"pay_checkout_{order_id}")],
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"check_pay_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_payment_link_inline_keyboard(order_id: str, checkout_url: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🔗 To'lov sahifasiga o'tish", url=checkout_url)],
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"check_pay_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_production_payment_inline_keyboard(order_id: str, amount: int) -> InlineKeyboardMarkup:
    """Used when PAYMENT_ENV=PRODUCTION: lets the user pick Click or Payme,
    each generating its own real checkout link (see bot/handlers/payment.py)."""
    formatted_amount = f"{amount:,}".replace(",", " ")
    kb = [
        [InlineKeyboardButton(text=f"💳 Click orqali to'lash ({formatted_amount} UZS)", callback_data=f"pay_click_{order_id}")],
        [InlineKeyboardButton(text=f"💳 Payme orqali to'lash ({formatted_amount} UZS)", callback_data=f"pay_payme_{order_id}")],
        [InlineKeyboardButton(text="✅ To'lovni tasdiqlash", callback_data=f"check_pay_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_download_format_inline_keyboard(order_id: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📊 PowerPoint (.pptx)", callback_data=f"dl_pptx_{order_id}")],
        [InlineKeyboardButton(text="📄 PDF", callback_data=f"dl_pdf_{order_id}")],
        [InlineKeyboardButton(text="📦 Ikkalasi ham", callback_data=f"dl_both_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_tezcheck_pay_keyboard(order_id: str, amount: int) -> InlineKeyboardMarkup:
    """TezCheck: one button; the bill is created when it is pressed."""
    formatted_amount = f"{amount:,}".replace(",", " ")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 To‘lash — {formatted_amount} so‘m (Click · Payme)", callback_data=f"tc_pay_{order_id}")],
    ])


def get_tezcheck_link_keyboard(order_id: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To‘lov sahifasini ochish", url=url)],
        [InlineKeyboardButton(text="✅ To‘ladim — tekshirish", callback_data=f"tc_chk_{order_id}")],
    ])
