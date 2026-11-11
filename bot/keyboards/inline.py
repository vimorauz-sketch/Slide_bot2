from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

def get_template_selection_inline_keyboard(webapp_url: str = "") -> InlineKeyboardMarkup:
    """The design step: one quick choice, then the ways to browse, then AI."""
    kb = [[InlineKeyboardButton(text="⚡ Tezkor — tavsiya etilgan dizayn", callback_data="tpl_auto")]]
    if webapp_url:
        kb.append([InlineKeyboardButton(text="🎨 Galereya", web_app=WebAppInfo(url=webapp_url)),
                   InlineKeyboardButton(text="📂 Bo‘limlar", callback_data="gal_cats")])
    else:
        kb.append([InlineKeyboardButton(text="🗂 Hammasini ko‘rish", callback_data="gal_l:all:0"),
                   InlineKeyboardButton(text="📂 Bo‘limlar", callback_data="gal_cats")])
    kb.append([InlineKeyboardButton(text="🤖 AI o‘zi dizayn chizsin", callback_data="tpl_ai_custom")])
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
    kb.append([InlineKeyboardButton(text="📂 Bo‘limlar", callback_data="gal_cats"),
               InlineKeyboardButton(text="🏠 Boshiga", callback_data="gal_home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_gallery_colors_keyboard(colors) -> InlineKeyboardMarkup:
    """colors: [(theme_key, number, colour_name)] — one template's colour sets."""
    btns = [InlineKeyboardButton(text=f"{n}. {name}", callback_data=f"tpl_{key}") for key, n, name in colors]
    kb = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    kb.append([InlineKeyboardButton(text="⬅️ Boshqa shablonlar", callback_data="gal_close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_confirmation_inline_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """The order summary: create now, or (optionally) add details, change the design, see the plan."""
    kb = [
        [InlineKeyboardButton(text="✅ Yaratish", callback_data=f"confirm_pres_{order_id}")],
        [InlineKeyboardButton(text="⚙️ Qo‘shimcha sozlamalar", callback_data="px_more")],
        [InlineKeyboardButton(text="🖼 Shablon", callback_data="px_tpl"),
         InlineKeyboardButton(text="🔤 Shrift va rang", callback_data="st_menu")],
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


# ---------------------------------------------------------------- free presentation and referrals
def create_now_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Taqdimot yaratish", callback_data="new_pres")],
    ])


def after_free_keyboard(has_credits: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🎨 Yangi taqdimot yaratish", callback_data="new_pres")]]
    if not has_credits:
        rows.insert(0, [InlineKeyboardButton(text="🎁 Do‘stlarni taklif qilish — bepul taqdimot", callback_data="ref_open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_keyboard(link: str, share_text: str, has_credits: bool) -> InlineKeyboardMarkup:
    from urllib.parse import quote
    rows = [[InlineKeyboardButton(text="📤 Do‘stlarga yuborish",
                                  url=f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(share_text, safe='')}")]]
    if has_credits:
        rows.append([InlineKeyboardButton(text="✨ Bepul taqdimot yaratish", callback_data="new_pres")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
