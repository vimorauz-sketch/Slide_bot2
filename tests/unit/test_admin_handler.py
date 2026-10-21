import pytest
from bot.handlers import admin as admin_module
from tests.fixtures.telegram_fakes import FakeMessage, FakeUser


# ---------------------------------------------------------------------------
# is_admin() -- pure authorization check
# ---------------------------------------------------------------------------

def test_is_admin_true_for_configured_admin_id(monkeypatch):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    assert admin_module.is_admin(8371155553) is True


def test_is_admin_false_for_random_user(monkeypatch):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    assert admin_module.is_admin(123456) is False


def test_is_admin_false_when_admin_ids_unconfigured(monkeypatch):
    # Regression guard: an empty/misconfigured ADMIN_IDS must deny everyone,
    # not silently grant admin to every user (the original bug).
    monkeypatch.setattr("config.settings.ADMIN_IDS", "")
    assert admin_module.is_admin(123456) is False
    assert admin_module.is_admin(8371155553) is False


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_admin_cannot_use_admin_panel(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/admin", from_user=FakeUser(id=999))

    await admin_module.cmd_admin_panel(message)

    assert message.calls == []  # handler returns early, nothing sent


@pytest.mark.asyncio
async def test_admin_can_open_admin_panel(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/admin", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_admin_panel(message)

    assert len(message.calls_for("answer")) == 1
    assert "Admin Paneli" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_change_price(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setprice 999", from_user=FakeUser(id=999))

    await admin_module.cmd_set_price(message)

    assert message.calls == []


@pytest.mark.asyncio
async def test_admin_set_price_with_valid_argument(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setprice 777", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_price(message)

    answer = message.calls_for("answer")[0]["text"]
    assert "777" in answer


@pytest.mark.asyncio
async def test_admin_set_price_rejects_non_numeric_argument(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setprice not-a-number", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_price(message)

    answer = message.calls_for("answer")[0]["text"]
    assert "Ishlatish" in answer  # usage/error message, price was not changed


@pytest.mark.asyncio
async def test_admin_set_price_rejects_missing_argument(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setprice", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_price(message)

    answer = message.calls_for("answer")[0]["text"]
    assert "Ishlatish" in answer


@pytest.mark.asyncio
async def test_admin_set_max_slides_persists_new_value(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setmaxslides 40", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_max_slides(message)

    answer = message.calls_for("answer")[0]["text"]
    assert "40" in answer

    from database import repository
    async with patched_handlers_db() as session:
        value = await repository.get_setting(session, "max_slides", "0")
    assert value == "40"


@pytest.mark.asyncio
async def test_admin_set_max_slides_rejects_non_numeric_argument(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setmaxslides many", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_max_slides(message)

    assert "Ishlatish" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_change_max_slides(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setmaxslides 40", from_user=FakeUser(id=999))

    await admin_module.cmd_set_max_slides(message)

    assert message.calls == []


@pytest.mark.asyncio
async def test_admin_set_min_slides_persists_new_value(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setminslides 8", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_min_slides(message)

    answer = message.calls_for("answer")[0]["text"]
    assert "8" in answer

    from database import repository
    async with patched_handlers_db() as session:
        value = await repository.get_setting(session, "min_slides", "0")
    assert value == "8"


@pytest.mark.asyncio
async def test_admin_set_min_slides_rejects_non_numeric_argument(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setminslides few", from_user=FakeUser(id=8371155553))

    await admin_module.cmd_set_min_slides(message)

    assert "Ishlatish" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_non_admin_cannot_change_min_slides(monkeypatch, patched_handlers_db):
    monkeypatch.setattr("config.settings.ADMIN_IDS", "8371155553")
    message = FakeMessage(text="/setminslides 8", from_user=FakeUser(id=999))

    await admin_module.cmd_set_min_slides(message)

    assert message.calls == []
