"""
The «Menu» list of commands Telegram shows next to the message field.

Every command here has a handler in bot/handlers/start.py (the first router), so it works from any
step of a wizard. The list is written at startup for every private chat (Uzbek by default, Russian
and English for users with those app languages); admins get /admin on top of it.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat, MenuButtonCommands

logger = logging.getLogger(__name__)

# command -> description per language (descriptions: at most 256 characters)
COMMANDS: List[Tuple[str, Dict[str, str]]] = [
    ("start", {"uz": "🏠 Bosh menyu", "ru": "🏠 Главное меню", "en": "🏠 Main menu"}),
    ("new", {"uz": "🎨 Yangi taqdimot yaratish", "ru": "🎨 Создать презентацию", "en": "🎨 Create a presentation"}),
    ("referat", {"uz": "📄 Referat yaratish (Word + PDF)", "ru": "📄 Создать реферат (Word + PDF)",
                 "en": "📄 Create a paper (Word + PDF)"}),
    ("templates", {"uz": "🖼 Shablonlarni ko‘rish", "ru": "🖼 Шаблоны", "en": "🖼 Browse templates"}),
    ("profile", {"uz": "👤 Profilim va bepul taqdimotlar", "ru": "👤 Мой профиль", "en": "👤 My profile"}),
    ("invite", {"uz": "🎁 Do‘st taklif qilib bepul taqdimot olish", "ru": "🎁 Пригласить друга",
                "en": "🎁 Invite a friend"}),
    ("prices", {"uz": "💰 Narxlar", "ru": "💰 Цены", "en": "💰 Pricing"}),
    ("help", {"uz": "❓ Yordam va qo‘llab-quvvatlash", "ru": "❓ Помощь", "en": "❓ Help"}),
    ("cancel", {"uz": "❌ Joriy amalni bekor qilish", "ru": "❌ Отменить", "en": "❌ Cancel"}),
]
ADMIN_COMMANDS: List[Tuple[str, str]] = [("admin", "🛠 Admin panel (bir martalik kirish havolasi)")]


def commands_for(lang: str = "uz", admin: bool = False) -> List[BotCommand]:
    out = [BotCommand(command=c, description=d.get(lang) or d["uz"]) for c, d in COMMANDS]
    if admin:
        out += [BotCommand(command=c, description=d) for c, d in ADMIN_COMMANDS]
    return out


async def setup_commands(bot, admin_ids=()) -> None:
    """Writes the command lists; a failure only means Telegram keeps the old list."""
    try:
        scope = BotCommandScopeAllPrivateChats()
        await bot.set_my_commands(commands_for("uz"), scope=scope)
        for lang in ("ru", "en"):
            await bot.set_my_commands(commands_for(lang), scope=scope, language_code=lang)
        for uid in admin_ids:
            try:
                await bot.set_my_commands(commands_for("uz", admin=True), scope=BotCommandScopeChat(chat_id=int(uid)))
            except Exception:  # noqa: BLE001 - the admin has not started the bot yet
                logger.info("admin commands not set for %s", uid)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("bot commands updated (%d)", len(COMMANDS))
    except Exception:  # noqa: BLE001
        logger.exception("bot commands were not updated")
