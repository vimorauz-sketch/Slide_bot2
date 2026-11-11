from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

CANCEL_TEXT = "❌ Bekor qilish"
SKIP_TEXT = "⏭ O‘tkazib yuborish"
CANCEL_TEXTS = {CANCEL_TEXT, "❌ Отмена", "❌ Cancel"}
SKIP_TEXTS = {SKIP_TEXT, "-", "—", "–"}

HOME_BUTTON = {"uz": "🚀 Nima tayyorlaymiz?", "ru": "🚀 Что подготовим?", "en": "🚀 What shall we make?"}


def _home_row(lang: str):
    """The Mini App home («Nima tayyorlaymiz?») on top of the menu, when the bot has a public https address."""
    try:
        from bot.handlers.create_pres import home_url
        url = home_url()
    except Exception:  # noqa: BLE001 - the menu works without it
        url = ""
    return [[KeyboardButton(text=HOME_BUTTON.get(lang, HOME_BUTTON["uz"]), web_app=WebAppInfo(url=url))]] if url else []


def get_main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    if lang == "ru":
        kb = [
            [KeyboardButton(text="🎨 Создать презентацию"), KeyboardButton(text="📄 Создать реферат")],
            [KeyboardButton(text="🖼 Шаблоны"), KeyboardButton(text="🎁 Рефералы")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Цены"), KeyboardButton(text="❓ Помощь")]
        ]
    elif lang == "en":
        kb = [
            [KeyboardButton(text="🎨 Create Presentation"), KeyboardButton(text="📄 Create Paper")],
            [KeyboardButton(text="🖼 Templates"), KeyboardButton(text="🎁 Referral")],
            [KeyboardButton(text="👤 Profile"), KeyboardButton(text="💰 Pricing"), KeyboardButton(text="❓ Help")]
        ]
    else:
        kb = [
            [KeyboardButton(text="🎨 Presentation yaratish"), KeyboardButton(text="📄 Referat yaratish")],
            [KeyboardButton(text="🖼 Shablonlar"), KeyboardButton(text="🎁 Referal")],
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="💰 Narxlar"), KeyboardButton(text="❓ Yordam")]
        ]
    return ReplyKeyboardMarkup(keyboard=_home_row(lang) + kb, resize_keyboard=True)

SUBJECTS = ["Biologiya", "Kimyo", "Fizika", "Matematika", "Tarix", "Geografiya", "Informatika",
            "Ona tili va adabiyot", "Ingliz tili", "Rus tili", "Iqtisodiyot", "Huquq", "Pedagogika",
            "Psixologiya", "Tibbiyot", "Menejment"]
LEVELS = ["Maktab", "Akademik litsey", "Kollej / Texnikum", "Universitet", "Boshqa"]
YES_TEXT = "✅ Ha, bor"
NO_TEXT = "🚫 Yo‘q"


def _rows(texts, per_row: int):
    return [[KeyboardButton(text=t) for t in texts[i:i + per_row]] for i in range(0, len(texts), per_row)]


def _kb(rows, placeholder: str = "") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True,
                               input_field_placeholder=placeholder[:64] or None)


def _cancel_row(cancel: bool):
    """The «❌ Bekor qilish» row. The presentation wizard leaves it out (cancelling is on the summary card
    and /cancel); the referat wizard keeps it."""
    return [[KeyboardButton(text=CANCEL_TEXT)]] if cancel else []


def get_subject_keyboard(cancel: bool = True) -> ReplyKeyboardMarkup:
    """Popular subjects as buttons; any other subject can simply be typed."""
    return _kb(_rows(SUBJECTS, 3) + _cancel_row(cancel), "Yoki fan nomini yozing…")


def get_slide_count_keyboard(min_slides: int = 5, max_slides: int = 30, cancel: bool = True) -> ReplyKeyboardMarkup:
    counts = [n for n in (5, 7, 8, 10, 12, 15, 20, 25, 30) if min_slides <= n <= max_slides]
    if not counts:
        counts = [min_slides]
    return _kb(_rows([str(n) for n in counts], 4) + _cancel_row(cancel), "Yoki sonini yozing…")


def get_level_keyboard(cancel: bool = True) -> ReplyKeyboardMarkup:
    return _kb(_rows(LEVELS[:4], 2) + [[KeyboardButton(text=LEVELS[4])]] + _cancel_row(cancel))


def class_options(level: str):
    """Class / year buttons for an education level ([] = the step is skipped)."""
    lv = (level or "").lower()
    if "maktab" in lv or "school" in lv or "школ" in lv:
        return [f"{i}-sinf" for i in range(1, 12)]
    if "universitet" in lv or "university" in lv or "вуз" in lv or "институт" in lv:
        return [f"{i}-kurs" for i in range(1, 5)] + ["Magistratura"]
    if "litsey" in lv or "kollej" in lv or "texnikum" in lv or "лицей" in lv or "колледж" in lv:
        return [f"{i}-kurs" for i in range(1, 4)]
    return []


def get_course_keyboard(level: str = "Universitet", cancel: bool = True) -> ReplyKeyboardMarkup:
    opts = class_options(level) or [f"{i}-kurs" for i in range(1, 5)]
    return _kb(_rows(opts, 4) + [[KeyboardButton(text=SKIP_TEXT)]] + _cancel_row(cancel))


def get_date_keyboard(today: str, year: str, cancel: bool = True) -> ReplyKeyboardMarkup:
    return _kb([[KeyboardButton(text=f"📅 Bugun: {today}"), KeyboardButton(text=f"📅 {year}-yil")],
                [KeyboardButton(text=SKIP_TEXT)]] + _cancel_row(cancel), "Yoki sanani yozing…")


def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    return _kb([[KeyboardButton(text=YES_TEXT), KeyboardButton(text=NO_TEXT)], [KeyboardButton(text=CANCEL_TEXT)]])


def get_language_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🇺🇿 O'zbekcha"), KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")],
        [KeyboardButton(text=CANCEL_TEXT)]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True
    )


def get_skip_keyboard(cancel: bool = True) -> ReplyKeyboardMarkup:
    """For optional answers (institution, teacher name)."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=SKIP_TEXT)]] + _cancel_row(cancel), resize_keyboard=True)


def get_webapp_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Reply keyboard that opens the template gallery Mini App (its choice comes back as web_app_data)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎨 Dizaynni tanlash", web_app=WebAppInfo(url=webapp_url))],
                  [KeyboardButton(text=CANCEL_TEXT)]],
        resize_keyboard=True
    )


def get_gallery_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """The design step: the bottom button opens the gallery Mini App (its choice comes back as web_app_data)."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎨 Galereya", web_app=WebAppInfo(url=webapp_url))]],
                               resize_keyboard=True)
