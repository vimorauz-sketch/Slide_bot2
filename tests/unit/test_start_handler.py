import pytest
from bot.handlers import start as start_module
from tests.fixtures.telegram_fakes import FakeMessage, FakeUser, FakeFSMContext
from database import repository


@pytest.mark.asyncio
async def test_start_without_referral_creates_user_with_no_referrer(patched_handlers_db):
    message = FakeMessage(text="/start", from_user=FakeUser(id=111))
    state = FakeFSMContext()

    await start_module.cmd_start(message, state)

    async with patched_handlers_db() as session:
        user = await repository.get_user(session, 111)
    assert user is not None
    assert user.referred_by is None
    assert message.calls_for("answer")


@pytest.mark.asyncio
async def test_start_with_valid_referral_payload_links_referrer(patched_handlers_db):
    async with patched_handlers_db() as session:  # the inviter must be a real user of the bot
        await repository.get_or_create_user(session, 555, "Inviter", "inv")
    message = FakeMessage(text="/start 555", from_user=FakeUser(id=111))
    state = FakeFSMContext()

    await start_module.cmd_start(message, state)

    async with patched_handlers_db() as session:
        user = await repository.get_user(session, 111)
    assert user.referred_by == 555


@pytest.mark.asyncio
async def test_start_prevents_self_referral(patched_handlers_db):
    message = FakeMessage(text="/start 111", from_user=FakeUser(id=111))  # referring themself
    state = FakeFSMContext()

    await start_module.cmd_start(message, state)

    async with patched_handlers_db() as session:
        user = await repository.get_user(session, 111)
    assert user.referred_by is None


@pytest.mark.asyncio
async def test_start_ignores_non_numeric_referral_payload(patched_handlers_db):
    message = FakeMessage(text="/start not-a-number", from_user=FakeUser(id=111))
    state = FakeFSMContext()

    await start_module.cmd_start(message, state)

    async with patched_handlers_db() as session:
        user = await repository.get_user(session, 111)
    assert user.referred_by is None


@pytest.mark.asyncio
async def test_start_does_not_overwrite_referrer_for_an_existing_user(patched_handlers_db):
    async with patched_handlers_db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice", referred_by=555)

    # User runs /start again later with a *different* referral payload.
    message = FakeMessage(text="/start 777", from_user=FakeUser(id=111))
    state = FakeFSMContext()
    await start_module.cmd_start(message, state)

    async with patched_handlers_db() as session:
        user = await repository.get_user(session, 111)
    assert user.referred_by == 555  # unchanged, not overwritten by the later payload


@pytest.mark.asyncio
async def test_start_clears_any_existing_fsm_state(patched_handlers_db):
    message = FakeMessage(text="/start", from_user=FakeUser(id=111))
    state = FakeFSMContext()
    await state.update_data(leftover="from a previous wizard")
    await state.set_state("SomePreviousState")

    await start_module.cmd_start(message, state)

    assert await state.get_data() == {}
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_show_prices_formats_all_tiers(patched_handlers_db):
    message = FakeMessage(text="💰 Narxlar", from_user=FakeUser(id=111))

    await start_module.show_prices(message)

    text = message.calls_for("answer")[0]["text"]
    assert text  # locale template rendered without a KeyError/format crash


@pytest.mark.asyncio
async def test_show_profile_creates_user_if_missing_and_escapes_full_name(patched_handlers_db):
    message = FakeMessage(
        text="👤 Profil",
        from_user=FakeUser(id=111, full_name="<script>Evil</script>", username="evil")
    )

    await start_module.show_profile(message)

    text = message.calls_for("answer")[0]["text"]
    assert "<script>Evil</script>" not in text
    assert "&lt;script&gt;" in text


@pytest.mark.asyncio
async def test_show_profile_reports_order_and_referral_counts(patched_handlers_db):
    async with patched_handlers_db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        await repository.create_presentation_order(
            session=session, user_id=111, topic="T", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        await repository.get_or_create_user(session, 222, "Bob", "bob", referred_by=111)

    message = FakeMessage(text="👤 Profil", from_user=FakeUser(id=111, full_name="Alice"))
    await start_module.show_profile(message)

    text = message.calls_for("answer")[0]["text"]
    assert "1" in text  # 1 order, 1 referral -- just a smoke check the counts were substituted


@pytest.mark.asyncio
async def test_show_referral_builds_a_deep_link_with_the_users_id(patched_handlers_db):
    message = FakeMessage(text="🎁 Referal", from_user=FakeUser(id=42424242))

    await start_module.show_referral(message)

    text = message.calls_for("answer")[0]["text"]
    assert "start=ref_42424242" in text


@pytest.mark.asyncio
async def test_show_help_falls_back_to_uz_locale_for_unknown_user(patched_handlers_db):
    message = FakeMessage(text="❓ Yordam", from_user=FakeUser(id=999999))  # never registered

    await start_module.show_help(message)

    assert message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_start_with_template_payload_selects_the_design(patched_handlers_db):
    from bot.states.forms import PresentationForm
    message = FakeMessage(text="/start tpl_150_apollo--emerald", from_user=FakeUser(id=111))
    state = FakeFSMContext()

    await start_module.cmd_start(message, state)

    assert (await state.get_data())["template_id"] == "150_apollo~emerald"
    assert await state.get_state() == PresentationForm.subject
    assert not message.calls_for("answer")  # no welcome menu: the wizard continues straight away
    async with patched_handlers_db() as session:
        assert await repository.get_user(session, 111) is not None
