"""Telegram Premium custom emoji (services/custom_emoji.py): text, buttons, safe fallback."""
import json

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, SendMessage, SendPhoto
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from services import custom_emoji as ce

FIRE, OK, ONE = "5404674261681232568", "5427009714745517609", "5361837567463399422"


@pytest.fixture(autouse=True)
def ids(monkeypatch):
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_ENABLED", True)
    ce.set_ids({"🔥": FIRE, "✅": OK, "1️⃣": ONE, "🇺🇿": "5222161185138292290", "bad": "x", "⚠️": "not-an-id"})
    ce.state.update(enabled=True, buttons=True, reason="")
    yield
    ce.set_ids({})
    ce.state.update(enabled=True, buttons=True, reason="")


def test_only_valid_ids_are_used():
    assert ce.emoji_id("🔥") == FIRE and ce.emoji_id("⚠️") is None and ce.emoji_id("bad") is None


def test_plain_text_is_escaped_and_gets_premium_emoji():
    out = ce.to_html("🔥 1 < 2 & ✅", None)
    assert out == f'<tg-emoji emoji-id="{FIRE}">🔥</tg-emoji> 1 &lt; 2 &amp; <tg-emoji emoji-id="{OK}">✅</tg-emoji>'


def test_variation_selectors_keycaps_and_flags():
    assert f'emoji-id="{OK}">✅️<' in ce.to_html("✅️ ok", None)
    assert f'emoji-id="{ONE}">1️⃣<' in ce.to_html("1️⃣ birinchi", None)
    assert 'emoji-id="5222161185138292290">🇺🇿<' in ce.to_html("🇺🇿 O‘zbekcha", None)


def test_html_keeps_tags_and_skips_code_links_and_existing_custom_emoji():
    text = '<b>🔥 Tayyor</b> <code>🔥</code> <a href="https://x.uz/🔥">🔥</a> <tg-emoji emoji-id="1">✅</tg-emoji> ✅'
    out = ce.to_html(text, "HTML")
    assert out.startswith(f'<b><tg-emoji emoji-id="{FIRE}">🔥</tg-emoji> Tayyor</b> <code>🔥</code> '
                          '<a href="https://x.uz/🔥">🔥</a> <tg-emoji emoji-id="1">✅</tg-emoji> ')
    assert out.endswith(f'<tg-emoji emoji-id="{OK}">✅</tg-emoji>')


def test_markdown_and_texts_without_known_emoji_are_left_alone():
    assert ce.to_html("🔥 *qalin*", "MarkdownV2") is None
    assert ce.to_html("📚 Salom", None) is None
    assert ce.to_html("", None) is None


def test_inline_buttons_get_icons_but_reply_keyboards_do_not():
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ To‘ladim", callback_data="x"),
                                                InlineKeyboardButton(text="🔥", callback_data="y"),
                                                InlineKeyboardButton(text="Oddiy", callback_data="z")]])
    new = ce.decorate_markup(kb)
    a, b, c = new.inline_keyboard[0]
    assert (a.text, a.icon_custom_emoji_id) == ("To‘ladim", OK)
    assert b.text == "🔥" and b.icon_custom_emoji_id is None      # nothing would be left of the text
    assert c.icon_custom_emoji_id is None
    assert kb.inline_keyboard[0][0].text == "✅ To‘ladim"           # the original is not changed
    reply = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔥 Presentation yaratish")]])
    assert ce.decorate_markup(reply) is reply                       # handlers match the reply text


def test_transform_methods():
    m = ce.transform(SendMessage(chat_id=1, text="🔥 Tayyor"))
    assert m.parse_mode == "HTML" and "tg-emoji" in m.text
    assert ce.transform(SendMessage(chat_id=1, text="📚 Salom")) is None
    p = ce.transform(SendPhoto(chat_id=1, photo="file", caption="<b>✅</b>", parse_mode="HTML"))
    assert "tg-emoji" in p.caption
    e = ce.transform(EditMessageText(chat_id=1, message_id=2, text="Salom",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                         InlineKeyboardButton(text="🔥 Ochish", callback_data="o")]])))
    assert e.text == "Salom" and e.reply_markup.inline_keyboard[0][0].icon_custom_emoji_id == FIRE


def test_switched_off_means_untouched(monkeypatch):
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_ENABLED", False)
    assert ce.transform(SendMessage(chat_id=1, text="🔥")) is None


async def test_rejected_custom_emoji_are_switched_off_and_the_message_still_goes():
    sent = []

    async def make_request(bot, method):
        sent.append(method)
        if "tg-emoji" in (method.text or ""):
            raise TelegramBadRequest(method=method, message="Bad Request: custom emoji can't be used")
        return "ok"
    mw = ce.CustomEmojiMiddleware()
    assert await mw(make_request, None, SendMessage(chat_id=1, text="🔥 Tayyor")) == "ok"
    assert sent[-1].text == "🔥 Tayyor" and not ce.state["enabled"]
    await mw(make_request, None, SendMessage(chat_id=1, text="✅ Keyingisi"))
    assert sent[-1].text == "✅ Keyingisi" and len(sent) == 3   # sent once, without trying again


async def test_rejected_button_icons_switch_off_only_icons():
    sent = []

    async def make_request(bot, method):
        sent.append(method)
        kb = method.reply_markup
        if kb and kb.inline_keyboard[0][0].icon_custom_emoji_id:
            raise TelegramBadRequest(method=method, message="Bad Request: BUTTON_ICON_INVALID")
        return "ok"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ha", callback_data="h")]])
    await ce.CustomEmojiMiddleware()(make_request, None, SendMessage(chat_id=1, text="Salom", reply_markup=kb))
    assert sent[-1].reply_markup.inline_keyboard[0][0].text == "✅ Ha"
    assert ce.state["enabled"] and not ce.state["buttons"]


async def test_other_errors_are_not_hidden():
    async def make_request(bot, method):
        raise TelegramBadRequest(method=method, message="Bad Request: chat not found")
    with pytest.raises(TelegramBadRequest):
        await ce.CustomEmojiMiddleware()(make_request, None, SendMessage(chat_id=1, text="🔥"))


async def test_load_reads_the_file_and_packs(tmp_path, monkeypatch):
    path = tmp_path / "custom_emoji.json"
    path.write_text(json.dumps({"_help": "x", "🔥": FIRE, "✅": ""}), encoding="utf-8")
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_FILE", str(path))
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_PACKS", "https://t.me/addemoji/MyPack, missing")

    class Sticker:
        def __init__(self, emoji, cid):
            self.emoji, self.custom_emoji_id = emoji, cid

    class Bot:
        async def get_sticker_set(self, name):
            if name != "MyPack":
                raise RuntimeError("STICKERSET_INVALID")
            return type("Set", (), {"stickers": [Sticker("✅", OK), Sticker("🔥", "1111111111"), Sticker("✅", "2")]})()
    assert await ce.load(Bot()) == 2
    assert ce.emoji_id("✅") == OK and ce.emoji_id("🔥") == FIRE   # the file wins over the pack


async def test_tg_emoji_hub_export_list_is_accepted(tmp_path, monkeypatch):
    path = tmp_path / "e.json"
    path.write_text(json.dumps([{"emoji": "🔥", "custom_emoji_id": FIRE}]), encoding="utf-8")
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_FILE", str(path))
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_PACKS", "")
    assert await ce.load(None) == 1


def test_shipped_file_is_valid_json():
    with open(ce.file_path(), encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict) and all(v == "" or ce.ID_RE.match(v) for k, v in data.items() if k[0] != "_")


async def test_ids_telegram_does_not_know_are_dropped_at_startup(tmp_path, monkeypatch):
    path = tmp_path / "e.json"
    path.write_text(json.dumps({"🔥": FIRE, "✅": "1234567"}), encoding="utf-8")
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_FILE", str(path))
    monkeypatch.setattr("config.settings.CUSTOM_EMOJI_PACKS", "")
    asked = []

    class Bot:
        async def get_custom_emoji_stickers(self, custom_emoji_ids):
            asked.append(sorted(custom_emoji_ids))
            return [type("S", (), {"custom_emoji_id": i})() for i in custom_emoji_ids if i == FIRE]
    assert await ce.load(Bot()) == 1
    assert ce.emoji_id("🔥") == FIRE and ce.emoji_id("✅") is None
    assert asked == [sorted([FIRE, "1234567"])]
