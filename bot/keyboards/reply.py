from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

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
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_level_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="Maktab"), KeyboardButton(text="Litsey")],
        [KeyboardButton(text="Universitet"), KeyboardButton(text="Kollej / Texnikum")],
        [KeyboardButton(text="Boshqa")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_course_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="1-kurs"), KeyboardButton(text="2-kurs")],
        [KeyboardButton(text="3-kurs"), KeyboardButton(text="4-kurs")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_language_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🇺🇿 O'zbekcha"), KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


def get_webapp_keyboard(webapp_url: str) -> ReplyKeyboardMarkup:
    """Reply keyboard that opens the template gallery Mini App (its choice comes back as web_app_data)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎨 Dizaynni tanlash", web_app=WebAppInfo(url=webapp_url))],
                  [KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )
