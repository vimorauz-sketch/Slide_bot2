"""Speed features: fast AI settings, background writing, progress bar, parallel photo sources."""
import asyncio
import json

import pytest

from services import ai_service, prefetch
from bot.progress import ProgressMessage, bar
from bot.handlers import create_pres
from bot.states.forms import PresentationForm
from tests.fixtures.telegram_fakes import FakeCallbackQuery, FakeUser, FakeFSMContext, FakeMessage


# ------------------------------------------------------------------ fast model
class _Completions:
    def __init__(self, fail_first=None):
        self.calls = []
        self.fail_first = fail_first

    async def create(self, **kw):
        self.calls.append(kw)
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError(self.fail_first)
        msg = type("M", (), {"content": json.dumps({"ok": 1})})
        return type("R", (), {"choices": [type("C", (), {"message": msg})]})


class _Client:
    def __init__(self, **kw):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _Completions(**kw)


async def test_slides_use_the_fast_model_with_low_effort(monkeypatch):
    monkeypatch.setattr(ai_service, "_fast_failed", False)
    monkeypatch.setattr("config.settings.OPENAI_FAST_MODEL", "gpt-5.6-luna")
    monkeypatch.setattr("config.settings.OPENAI_REASONING_EFFORT", "low")
    c = _Client()
    await ai_service._chat_json(c, "s", "u")
    assert c.chat.completions.calls[0]["model"] == "gpt-5.6-luna"
    assert c.chat.completions.calls[0]["reasoning_effort"] == "low"


async def test_rejected_fast_settings_fall_back_to_the_main_model(monkeypatch):
    monkeypatch.setattr(ai_service, "_fast_failed", False)
    monkeypatch.setattr("config.settings.OPENAI_MODEL", "main-model")
    c = _Client(fail_first="Error code: 404 - The model `gpt-5.6-luna` does not exist")
    assert await ai_service._chat_json(c, "s", "u") == {"ok": 1}
    second = c.chat.completions.calls[1]
    assert second["model"] == "main-model" and "reasoning_effort" not in second
    await ai_service._chat_json(c, "s", "u")             # remembered: no second failure
    assert c.chat.completions.calls[2]["model"] == "main-model"


async def test_other_errors_are_not_hidden(monkeypatch):
    monkeypatch.setattr(ai_service, "_fast_failed", False)
    c = _Client(fail_first="Rate limit reached (429)")
    with pytest.raises(RuntimeError):
        await ai_service._chat_json(c, "s", "u")


# ------------------------------------------------------------------ background writing
@pytest.fixture
def slow_ai(monkeypatch):
    calls = {"outline": 0, "content": 0}

    async def outline(data, **kw):
        calls["outline"] += 1
        await asyncio.sleep(0.05)
        return {"title": data["topic"], "slides": [{"layout": "text_image", "title": "a"}]}

    async def content(data, outline=None, on_progress=None):
        calls["content"] += 1
        for i in range(3):
            await asyncio.sleep(0.02)
            if on_progress:
                await on_progress(i + 1, 3)
        return {"title_slide": {"title": data["topic"]}, "slides": [], "outline": outline,
                "language": data.get("language", "uz"), "written_for": data["language"]}

    monkeypatch.setattr(ai_service, "generate_outline", outline)
    monkeypatch.setattr(ai_service, "generate_presentation_content", content)
    return calls


DATA = {"subject": "Biologiya", "topic": "Biosfera", "slide_count": 8, "level": "Maktab", "course": "9-sinf"}


async def test_same_answers_reuse_the_running_job(slow_ai):
    j1 = prefetch.ensure(1, DATA)
    j2 = prefetch.ensure(1, {**DATA, "author_name": "Ali", "date": "20.10.2026", "language": "uz"})
    assert j1 is j2                                   # name/date/uz do not change the text
    content = await j1.task
    assert content["written_for"] == "uz" and slow_ai["content"] == 1


async def test_another_language_restarts_the_job(slow_ai):
    j1 = prefetch.ensure(2, DATA)
    j2 = prefetch.ensure(2, {**DATA, "language": "ru"})
    assert j1 is not j2
    await asyncio.sleep(0)
    assert j1.task.cancelled() or j1.task.cancelling()
    assert (await j2.task)["written_for"] == "ru"
    assert prefetch.take(2, {**DATA, "language": "en"}) is None   # answers changed again: not used
    assert prefetch.take(2, {**DATA, "language": "ru"}) is j2


async def test_create_uses_the_text_written_in_the_background(slow_ai, monkeypatch, patched_handlers_db, tmp_path):
    monkeypatch.setattr(create_pres, "__file__", str(tmp_path / "bot" / "handlers" / "create_pres.py"))
    used = {}

    async def fake_build(data, storage_dir, outline=None, progress=None, content=None, **kw):
        used["content"] = content
        await progress("photos")
        raise RuntimeError("stop here")               # the rest is covered by the integration tests

    monkeypatch.setattr(create_pres, "build_presentation", fake_build)
    state = FakeFSMContext()
    data = {**DATA, "language": "uz", "author_name": "Ali", "total_price": 2800}
    await state.update_data(**data)
    await state.set_state(PresentationForm.confirmation)
    job = prefetch.ensure(5, data)
    cb = FakeCallbackQuery(data="confirm_pres_temp_order", from_user=FakeUser(id=5))
    await create_pres.confirm_and_create(cb, state)
    assert used["content"] is not None and used["content"]["written_for"] == "uz"
    assert slow_ai["content"] == 1                    # nothing was written twice
    assert await state.get_state() == PresentationForm.confirmation   # failure: «create» can be pressed again
    assert job.task.done()


async def test_plan_button_shows_the_background_plan_instantly(slow_ai):
    state = FakeFSMContext()
    data = {**DATA, "language": "uz"}
    await state.update_data(**data)
    await state.set_state(PresentationForm.confirmation)
    prefetch.ensure(6, data)
    cb = FakeCallbackQuery(data="show_plan", from_user=FakeUser(id=6))
    await create_pres.confirm_and_show_outline(cb, state)
    assert await state.get_state() == PresentationForm.outline_review
    assert slow_ai["outline"] == 1                    # the background plan, not a new one
    assert "TAQDIMOT REJASI" in cb.message.calls_for("answer")[-1]["text"]


# ------------------------------------------------------------------ progress bar
async def test_progress_bar_moves_forward_and_ends_at_100():
    msg = FakeMessage()
    p = ProgressMessage(msg)
    await p.set("write", 0, 10)
    first = p.shown
    await p.set("write", 5, 10)
    assert p.shown > first
    await p.set("photos")
    await p.set("render")
    assert 78 <= p.shown < 100
    await p.finish()
    text = msg.calls_for("edit_text")[-1]["text"]
    assert "100%" in text and bar(100) in text and text.count("✅") == 4


def test_bar_drawing():
    assert bar(0) == "▱" * 12 and bar(50) == "▰" * 6 + "▱" * 6 and bar(100) == "▰" * 12


async def test_progress_edits_are_rate_limited():
    msg = FakeMessage()
    p = ProgressMessage(msg)
    for i in range(50):
        await p.set("write", i, 50)
    assert len(msg.calls_for("edit_text")) <= 2


# ------------------------------------------------------------------ photos
async def test_two_photo_sources_are_asked_at_once_and_the_preferred_one_wins(monkeypatch, tmp_path):
    from services.deck import images
    monkeypatch.setattr("config.settings.PIXABAY_API_KEY", "k")
    monkeypatch.setattr("config.settings.OPENVERSE_ENABLED", True)
    monkeypatch.setattr("config.settings.IMAGE_PROVIDERS", "pixabay,openverse")
    started = []

    async def provider(name, delay):
        started.append(name)
        await asyncio.sleep(delay)
        return [{"id": f"{name}:1", "url": f"https://x/{name}.jpg"}]

    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1600, 1000), (1, 2, 3)).save(buf, "JPEG")

    async def get_bytes(session, url, headers=None):
        return buf.getvalue()

    monkeypatch.setattr(images, "_pixabay", lambda s, q, o: provider("pixabay", 0.2))
    monkeypatch.setattr(images, "_openverse", lambda s, q, o: provider("openverse", 0.0))
    monkeypatch.setattr(images, "_get_bytes", get_bytes)
    r = images.ImageResolver({}, cache_dir=tmp_path)
    t = asyncio.get_running_loop().time()
    got = await r.resolve(None, "forest", "", "photo", "text_image")
    assert set(started) == {"pixabay", "openverse"}  # both at the same time
    assert got["provider"] == "pixabay"               # the preferred source wins
    assert asyncio.get_running_loop().time() - t < 0.4
    again = images.ImageResolver({}, cache_dir=tmp_path)
    started.clear()
    assert (await again.resolve(None, "forest", "", "photo", "text_image"))["provider"] == "pixabay"
    assert started == []                              # cached: no network at all
