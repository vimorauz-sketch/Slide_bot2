"""
Telegram Premium custom emoji in every message the bot sends.

Each ordinary emoji in a message ("🔥") is sent as its animated Premium version
(<tg-emoji emoji-id="5404674261681232568">🔥</tg-emoji>); inline buttons get the emoji as their icon
(icon_custom_emoji_id). The ids come from:
  1. custom_emoji.json (CUSTOM_EMOJI_FILE): {"🔥": "5404674261681232568", ...} — copy the ids from
     tg-emoji-hub (https://github.com/TGlimmer/tg-emoji-hub) or any custom emoji id bot;
  2. custom emoji packs (CUSTOM_EMOJI_PACKS="pack1,pack2", the <name> of t.me/addemoji/<name>):
     the bot reads every emoji of the pack with getStickerSet at startup. The file wins over packs.

Telegram lets a bot use custom emoji only when its owner has Telegram Premium (or the bot has a
username bought on Fragment). If Telegram rejects a message because of them, the very same message
is sent again with ordinary emoji, and custom emoji are switched off until the next restart — a
customer never misses a message because of this.

Nothing is changed in messages with entities or a Markdown parse mode, inside <code>/<pre>/<a>,
in reply keyboards (handlers match their text), alerts or media groups.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from typing import Any, Dict, Iterable, Optional

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (CopyMessage, EditMessageCaption, EditMessageReplyMarkup, EditMessageText, SendAnimation,
                             SendDocument, SendMessage, SendPhoto, SendVideo)
from aiogram.types import InlineKeyboardMarkup

from config import settings

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VS16 = "️"
ID_RE = re.compile(r"^\d{5,25}$")

_ids: Dict[str, str] = {}          # emoji (without U+FE0F) -> custom_emoji_id
_pattern: Optional[re.Pattern] = None
state = {"enabled": True, "buttons": True, "reason": ""}

# text parts where custom emoji must not go
_SKIP_OPEN = re.compile(r"<(code|pre|a|tg-emoji)\b", re.I)
_TAG = re.compile(r"(<[^>]*>)")


def _key(emoji: str) -> str:
    return (emoji or "").replace(VS16, "").strip()


def set_ids(mapping: Dict[str, Any]) -> int:
    """Replaces the emoji -> id table (invalid entries are skipped). Returns how many are usable."""
    global _pattern
    _ids.clear()
    for emoji, cid in (mapping or {}).items():
        k, cid = _key(str(emoji)), str(cid or "").strip()
        if k and ID_RE.match(cid) and len(k) <= 16:
            _ids[k] = cid
    if _ids:
        # longest first, so "👨‍💻" wins over "👨"; U+FE0F may follow any character ("1️⃣", "⚠️")
        alts = sorted(_ids, key=len, reverse=True)
        _pattern = re.compile("(?:" + "|".join("".join(re.escape(c) + VS16 + "?" for c in a) for a in alts) + ")")
    else:
        _pattern = None
    return len(_ids)


def active() -> bool:
    return bool(settings.CUSTOM_EMOJI_ENABLED and state["enabled"] and _ids)


def emoji_id(emoji: str) -> Optional[str]:
    return _ids.get(_key(emoji))


def _replace_plain(segment: str) -> str:
    """One piece of HTML text outside tags: every known emoji -> <tg-emoji>."""
    if _pattern is None:
        return segment
    return _pattern.sub(lambda m: f'<tg-emoji emoji-id="{_ids[_key(m.group(0))]}">{m.group(0)}</tg-emoji>', segment)


def to_html(text: str, parse_mode: Optional[str]) -> Optional[str]:
    """The text with custom emoji as HTML, or None when it stays as it is."""
    if not text or _pattern is None or not _pattern.search(text):
        return None
    mode = (parse_mode or "").upper()
    if mode in ("MARKDOWN", "MARKDOWNV2"):
        return None
    if mode != "HTML":
        text = html.escape(text, quote=False)
    out, depth = [], 0
    for part in _TAG.split(text):
        if part.startswith("<") and part.endswith(">"):
            if _SKIP_OPEN.match(part):
                depth += 1
            elif re.match(r"</(code|pre|a|tg-emoji)\s*>", part, re.I):
                depth = max(0, depth - 1)
            out.append(part)
        else:
            out.append(part if depth else _replace_plain(part))
    result = "".join(out)
    return result if result != text or mode != "HTML" else None


def _leading_emoji(text: str):
    """(emoji, rest) when the button text starts with a known emoji."""
    if _pattern is None:
        return None
    m = _pattern.match(text or "")
    if not m:
        return None
    rest = text[m.end():].lstrip()
    return (_key(m.group(0)), rest) if rest else None


def decorate_markup(markup: Any) -> Any:
    """Inline buttons that start with a known emoji get it as a Premium icon instead (a copy)."""
    if not isinstance(markup, InlineKeyboardMarkup) or not state["buttons"]:
        return markup
    changed = False
    rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            lead = None if getattr(btn, "icon_custom_emoji_id", None) else _leading_emoji(btn.text)
            if lead:
                btn = btn.model_copy(update={"text": lead[1], "icon_custom_emoji_id": _ids[lead[0]]})
                changed = True
            new_row.append(btn)
        rows.append(new_row)
    return markup.model_copy(update={"inline_keyboard": rows}) if changed else markup


_TEXT_METHODS = (SendMessage, EditMessageText)
_CAPTION_METHODS = (SendPhoto, SendDocument, SendVideo, SendAnimation, EditMessageCaption, CopyMessage)
_MARKUP_METHODS = _TEXT_METHODS + _CAPTION_METHODS + (EditMessageReplyMarkup,)


def transform(method: Any) -> Optional[Any]:
    """A copy of an outgoing Bot API call with custom emoji, or None when nothing changes."""
    if not active():
        return None
    update: Dict[str, Any] = {}
    if isinstance(method, _TEXT_METHODS) and not getattr(method, "entities", None):
        new = to_html(method.text, _mode(method))
        if new is not None:
            update.update(text=new, parse_mode="HTML")
    elif isinstance(method, _CAPTION_METHODS) and getattr(method, "caption", None) \
            and not getattr(method, "caption_entities", None):
        new = to_html(method.caption, _mode(method))
        if new is not None:
            update.update(caption=new, parse_mode="HTML")
    if isinstance(method, _MARKUP_METHODS):
        markup = getattr(method, "reply_markup", None)
        new_markup = decorate_markup(markup)
        if new_markup is not markup:
            update["reply_markup"] = new_markup
    return method.model_copy(update=update) if update else None


def _mode(method: Any) -> Optional[str]:
    mode = getattr(method, "parse_mode", None)
    return mode if isinstance(mode, str) else None  # aiogram's "use the bot default" marker -> plain


def _rejected_for_emoji(error: Exception) -> bool:
    """Telegram refused the custom emoji themselves (no Premium owner, unknown id, button icons)."""
    msg = str(error).lower()
    return any(k in msg for k in ("emoji", "document_invalid", "button_", "icon"))


class CustomEmojiMiddleware(BaseRequestMiddleware):
    """Bot session middleware: bot.session.middleware(CustomEmojiMiddleware())."""

    async def __call__(self, make_request, bot, method):
        try:
            changed = transform(method)
        except Exception:  # noqa: BLE001 - never break a message because of decoration
            logger.exception("custom emoji: message left unchanged")
            changed = None
        if changed is None:
            return await make_request(bot, method)
        try:
            return await make_request(bot, changed)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                raise
            if not _rejected_for_emoji(e):  # e.g. our HTML of this one message: send it as it was
                logger.warning("custom emoji: message sent unchanged after %s", e)
                return await make_request(bot, method)
            buttons_only = to_html(getattr(method, "text", None) or getattr(method, "caption", None) or "",
                                   _mode(method)) is None
            if buttons_only:
                state["buttons"] = False
                state["reason"] = f"button icons rejected: {e}"
            else:
                state["enabled"] = False
                state["reason"] = f"custom emoji rejected: {e}"
            logger.warning("custom emoji switched off (%s); the message is sent with ordinary emoji", state["reason"])
            return await make_request(bot, method)


# ---------------------------------------------------------------------- loading
def _read_file(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.error("custom emoji: %s could not be read: %s", path, e)
        return {}
    if isinstance(data, list):  # tg-emoji-hub JSON export: [{"emoji": "🔥", "custom_emoji_id": "..."}]
        return {str(x.get("emoji", "")): x.get("custom_emoji_id") or x.get("id") for x in data if isinstance(x, dict)}
    return {k: v for k, v in data.items() if not str(k).startswith("_")} if isinstance(data, dict) else {}


async def _read_packs(bot, names: Iterable[str]) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for name in names:
        try:
            pack = await bot.get_sticker_set(name)
        except Exception as e:  # noqa: BLE001
            logger.error("custom emoji pack %r could not be loaded: %s", name, e)
            continue
        n = 0
        for st in pack.stickers:
            if st.custom_emoji_id and st.emoji and _key(st.emoji) not in found:
                found[_key(st.emoji)] = st.custom_emoji_id
                n += 1
        logger.info("custom emoji pack %s: %d emoji", name, n)
    return found


async def _only_existing(bot, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Drops ids Telegram does not know (a wrong id in the file would make it refuse messages).
    If Telegram cannot be asked now, the table is kept: the middleware still falls back safely."""
    ids = list({str(v).strip() for v in mapping.values() if ID_RE.match(str(v).strip())})
    known = set()
    try:
        for i in range(0, len(ids), 200):  # Bot API limit per call
            for st in await bot.get_custom_emoji_stickers(custom_emoji_ids=ids[i:i + 200]):
                if st.custom_emoji_id:
                    known.add(st.custom_emoji_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("custom emoji ids could not be checked: %s", e)
        return mapping
    dropped = [k for k, v in mapping.items() if str(v).strip() not in known]
    if dropped:
        logger.warning("custom emoji: %d unknown id(s) skipped: %s", len(dropped), " ".join(dropped[:30]))
    return {k: v for k, v in mapping.items() if str(v).strip() in known}


def file_path() -> str:
    path = settings.CUSTOM_EMOJI_FILE or "custom_emoji.json"
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


async def load(bot=None) -> int:
    """Builds the table from the packs and the file. Returns the number of emoji with an id."""
    if not settings.CUSTOM_EMOJI_ENABLED:
        set_ids({})
        return 0
    mapping: Dict[str, Any] = {}
    packs = [p.strip().split("/")[-1] for p in (settings.CUSTOM_EMOJI_PACKS or "").split(",") if p.strip()]
    if bot is not None and packs:
        mapping.update(await _read_packs(bot, packs))
    mapping.update({_key(k): v for k, v in _read_file(file_path()).items() if v})
    if bot is not None and mapping:
        mapping = await _only_existing(bot, mapping)
    n = set_ids(mapping)
    state.update(enabled=True, buttons=True, reason="")
    if n:
        logger.info("custom emoji: %d Premium emoji in use", n)
    return n
