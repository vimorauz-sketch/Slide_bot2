import pytest
from bot.handlers import ocr_task
from bot.states.forms import PresentationForm
from tests.fixtures.telegram_fakes import FakeMessage, FakeUser, FakePhotoSize, FakeFSMContext


def _photo_message():
    return FakeMessage(from_user=FakeUser(id=111), photo=[FakePhotoSize()])


async def _run(monkeypatch, ocr_result, patched_handlers_db):
    async def fake_parse(image_bytes):
        return ocr_result

    monkeypatch.setattr(ocr_task.ai_service, "parse_task_image", fake_parse)
    state = FakeFSMContext()
    message = _photo_message()
    await ocr_task.handle_ocr_task_photo(message, state)
    return message, state


@pytest.mark.asyncio
async def test_ocr_clamps_slide_count_above_maximum(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "slide_count": 500,
        "language": "uz", "requirements": ""
    }, patched_handlers_db)

    data = await state.get_data()
    assert data["slide_count"] == 30  # default MAX_SLIDES_PER_ORDER


@pytest.mark.asyncio
async def test_ocr_clamps_slide_count_below_minimum(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "slide_count": 1,
        "language": "uz", "requirements": ""
    }, patched_handlers_db)

    data = await state.get_data()
    assert data["slide_count"] == 5  # default MIN_SLIDES_PER_ORDER


@pytest.mark.asyncio
async def test_ocr_falls_back_to_ten_when_slide_count_is_not_numeric(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "slide_count": "not-a-number",
        "language": "uz", "requirements": ""
    }, patched_handlers_db)

    data = await state.get_data()
    assert data["slide_count"] == 10


@pytest.mark.asyncio
async def test_ocr_falls_back_to_ten_when_slide_count_missing(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "language": "uz", "requirements": ""
    }, patched_handlers_db)

    data = await state.get_data()
    assert data["slide_count"] == 10


@pytest.mark.asyncio
async def test_ocr_escapes_dangerous_text_from_vision_model(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "<script>alert(1)</script>", "topic": "5 < 3", "slide_count": 10,
        "language": "uz", "requirements": "A & B"
    }, patched_handlers_db)

    sent_text = message.calls_for("answer")[1]["text"]  # [0] is the "analyzing..." message
    assert "<script>" not in sent_text
    assert "&lt;script&gt;" in sent_text


@pytest.mark.asyncio
async def test_ocr_uses_a_valid_registered_template_id(monkeypatch, patched_handlers_db):
    # Regression guard: must not fall back to the dead "01_minimal_blue" key.
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "slide_count": 10,
        "language": "uz", "requirements": ""
    }, patched_handlers_db)

    from services.template_service import template_manager
    data = await state.get_data()
    ds = template_manager.get_template_design_system(data["template_id"])
    assert ds["id"] == data["template_id"]  # resolves to itself, not a silent fallback


@pytest.mark.asyncio
async def test_ocr_advances_state_and_deletes_the_waiting_message(monkeypatch, patched_handlers_db):
    message, state = await _run(monkeypatch, {
        "subject": "Fizika", "topic": "Kvant", "slide_count": 10,
        "language": "uz", "requirements": ""
    }, patched_handlers_db)

    assert await state.get_state() == PresentationForm.author_name
    waiting_message = message.calls_for("answer")[0]["returned"]
    assert waiting_message.deleted is True
