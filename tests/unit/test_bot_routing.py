"""Routes real Telegram updates through a Dispatcher wired like main.py, so the order of routers
and filters is tested (which handler a button press or a sticker actually reaches)."""
import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import Update, Message, Chat, User, PhotoSize, CallbackQuery

from bot.handlers import start, create_pres, ocr_task, payment, admin
from bot.states.forms import PresentationForm

TOKEN = "123456:" + "A" * 35


class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        return None

    async def stream_content(self, *a, **k):  # pragma: no cover
        yield b""

    async def close(self):
        pass

    def texts(self):
        return [getattr(m, "text", None) or getattr(m, "caption", None) or "" for m in self.calls]


_DP = None


def _dispatcher() -> Dispatcher:
    global _DP
    if _DP is None:
        dp = Dispatcher()
        for r in (start.router, admin.router, ocr_task.router, create_pres.router, payment.router):
            dp.include_router(r)
        _DP = dp
    return _DP


@pytest.fixture
async def env(patched_handlers_db):
    session = RecordingSession()
    bot = Bot(TOKEN, session=session)
    dp = _dispatcher()
    ctx = dp.fsm.get_context(bot=bot, chat_id=7, user_id=7)
    await ctx.clear()  # the dispatcher (and its memory storage) is shared between tests
    return bot, dp, session, ctx


_n = 0


def _msg(text=None, photo=None):
    global _n
    _n += 1
    return Update(update_id=_n, message=Message(
        message_id=_n, date=datetime.datetime.now(), chat=Chat(id=7, type="private"),
        from_user=User(id=7, is_bot=False, first_name="Ali"), text=text, photo=photo))


def _cb(data):
    global _n
    _n += 1
    m = Message(message_id=1, date=datetime.datetime.now(), chat=Chat(id=7, type="private"), text="x")
    return Update(update_id=_n, callback_query=CallbackQuery(
        id=str(_n), from_user=User(id=7, is_bot=False, first_name="Ali"), chat_instance="c", data=data, message=m))


async def _feed(env, update):
    bot, dp, session, ctx = env
    await dp.feed_update(bot, update)
    return session.texts()


@pytest.mark.asyncio
async def test_cancel_button_leaves_the_wizard_instead_of_becoming_the_subject(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.subject)
    texts = await _feed(env, _msg("❌ Bekor qilish"))
    assert await ctx.get_state() is None
    assert any("Bekor qilindi" in t for t in texts)
    assert "subject" not in await ctx.get_data()


@pytest.mark.asyncio
async def test_cancel_command_works_too(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.topic)
    await _feed(env, _msg("/cancel"))
    assert await ctx.get_state() is None


@pytest.mark.asyncio
async def test_a_photo_where_text_is_expected_gets_a_hint_not_a_crash(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.slide_count)
    texts = await _feed(env, _msg(photo=[PhotoSize(file_id="f", file_unique_id="u", width=10, height=10)]))
    assert await ctx.get_state() == PresentationForm.slide_count.state
    assert any("matn" in t for t in texts)


@pytest.mark.asyncio
@pytest.mark.parametrize("typed", ["12", " 12 ", "12 ta", "12 slayd"])
async def test_slide_count_accepts_natural_answers(env, typed):
    *_, ctx = env
    await ctx.set_state(PresentationForm.slide_count)
    await _feed(env, _msg(typed))
    assert await ctx.get_state() == PresentationForm.author_name.state
    assert (await ctx.get_data())["slide_count"] == 12


@pytest.mark.asyncio
async def test_skip_button_skips_the_teacher(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.teacher_name)
    await _feed(env, _msg("⏭ O‘tkazib yuborish"))
    assert (await ctx.get_data())["teacher_name"] == ""
    assert await ctx.get_state() == PresentationForm.date.state


@pytest.mark.asyncio
async def test_messages_while_generating_get_a_wait_notice(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.generating)
    texts = await _feed(env, _msg("salom"))
    assert any("tayyorlanmoqda" in t for t in texts)
    texts = await _feed(env, _msg("❌ Bekor qilish"))  # cannot cancel a running build
    assert await ctx.get_state() == PresentationForm.generating.state


@pytest.mark.asyncio
async def test_second_press_of_create_is_ignored_while_generating(env, monkeypatch):
    *_, ctx = env
    calls = []

    async def fake_build(*a, **k):  # pragma: no cover - must not run
        calls.append(1)
        raise RuntimeError

    monkeypatch.setattr(create_pres, "build_presentation", fake_build)
    await ctx.set_state(PresentationForm.generating)
    await _feed(env, _cb("outline_ok"))
    assert calls == []


@pytest.mark.asyncio
async def test_ocr_state_asks_for_a_photo_when_text_is_sent(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.ocr_photo_upload)
    texts = await _feed(env, _msg("salom"))
    assert any("rasm" in t for t in texts)
    assert await ctx.get_state() == PresentationForm.ocr_photo_upload.state


@pytest.mark.asyncio
async def test_referat_button_does_not_open_the_presentation_wizard(env):
    *_, ctx = env
    texts = await _feed(env, _msg("📄 Referat yaratish"))
    assert await ctx.get_state() is None
    assert any("Referat" in t for t in texts)


@pytest.mark.asyncio
async def test_menu_button_mid_wizard_restarts_cleanly(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.institution)
    await ctx.update_data(subject="old")
    await _feed(env, _msg("🎨 Presentation yaratish"))
    assert await ctx.get_state() == PresentationForm.template_selection.state
    assert await ctx.get_data() == {}


@pytest.mark.asyncio
async def test_start_flood_is_throttled_by_the_middleware(patched_handlers_db):
    from bot.middlewares.throttling import ThrottlingMiddleware
    dp = Dispatcher()
    dp.update.outer_middleware(ThrottlingMiddleware(rate=1, burst=12))
    handled = []

    @dp.message()
    async def any_message(message):
        handled.append(message.text)

    session = RecordingSession()
    bot = Bot(TOKEN, session=session)
    for _ in range(500):
        await dp.feed_update(bot, _msg("/start"))
    assert len(handled) == 4
    notices = [t for t in session.texts() if "Juda" in t or "⛔" in t]
    assert 1 <= len(notices) <= 3


@pytest.mark.asyncio
async def test_whole_wizard_with_buttons(env):
    *_, ctx = env
    await ctx.set_state(PresentationForm.subject)
    for text in ["Biologiya", "Biosfera modeli", "10", "Ali Valiyev", "Maktab", "45-maktab", "9-sinf",
                 "⏭ O‘tkazib yuborish", "📅 Bugun: 20.10.2026", "🇺🇿 O'zbekcha", "🚫 Yo‘q"]:
        await _feed(env, _msg(text))
    data = await ctx.get_data()
    assert await ctx.get_state() == PresentationForm.confirmation.state
    assert (data["subject"], data["slide_count"], data["level"], data["institution"], data["course"],
            data["teacher_name"], data["date"], data["additional_notes"]) == \
        ("Biologiya", 10, "Maktab", "45-maktab", "9-sinf", "", "20.10.2026", "")


@pytest.mark.asyncio
async def test_daily_preview_limit(env, monkeypatch):
    *_, ctx = env
    monkeypatch.setattr("config.settings.MAX_PREVIEWS_PER_DAY", 1)

    async def many(*a, **k):
        return 1
    monkeypatch.setattr(create_pres.repository, "count_user_orders_since", many)
    built = []

    async def fake_build(*a, **k):
        built.append(1)
    monkeypatch.setattr(create_pres, "build_presentation", fake_build)
    await ctx.set_state(PresentationForm.outline_review)
    texts = await _feed(env, _cb("outline_ok"))
    assert built == [] and any("chegara" in t for t in texts)
    assert await ctx.get_state() == PresentationForm.outline_review.state


@pytest.mark.asyncio
async def test_builds_wait_in_a_queue(monkeypatch):
    import asyncio
    monkeypatch.setattr("config.settings.MAX_PARALLEL_BUILDS", 2)
    monkeypatch.setattr(create_pres, "_build_sem", None)
    running, peak = 0, 0

    async def job():
        nonlocal running, peak
        async with create_pres._build_slot():
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

    await asyncio.gather(*(job() for _ in range(10)))
    assert peak == 2
