import pytest
from database import repository


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user(db):
    async with db() as session:
        user = await repository.get_or_create_user(session, 111, "Alice", "alice")
        assert user.telegram_id == 111
        assert user.full_name == "Alice"
        assert user.balance == 0


@pytest.mark.asyncio
async def test_get_or_create_user_is_idempotent(db):
    async with db() as session:
        first = await repository.get_or_create_user(session, 111, "Alice", "alice")
        second = await repository.get_or_create_user(session, 111, "Alice Updated", "alice2")
    # Second call must return the SAME existing row, not overwrite it with new values.
    assert first.telegram_id == second.telegram_id
    assert second.full_name == "Alice"


@pytest.mark.asyncio
async def test_get_user_returns_none_for_unknown_user(db):
    async with db() as session:
        user = await repository.get_user(session, 999999)
        assert user is None


@pytest.mark.asyncio
async def test_update_user_language_persists(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        await repository.update_user_language(session, 111, "ru")
        user = await repository.get_user(session, 111)
        assert user.language == "ru"


@pytest.mark.asyncio
async def test_create_presentation_order_defaults_to_preview_ready(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        order = await repository.create_presentation_order(
            session=session, user_id=111, topic="Fotosintez", subject="Biologiya",
            slide_count=10, template_id="01_midnight_tech", total_price=3500
        )
        assert order.status == "PREVIEW_READY"
        assert order.id  # UUID primary key auto-generated


@pytest.mark.asyncio
async def test_two_orders_get_distinct_ids(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        order_a = await repository.create_presentation_order(
            session=session, user_id=111, topic="A", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        order_b = await repository.create_presentation_order(
            session=session, user_id=111, topic="B", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        assert order_a.id != order_b.id


@pytest.mark.asyncio
async def test_update_order_status_to_paid(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        order = await repository.create_presentation_order(
            session=session, user_id=111, topic="A", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        await repository.update_order_status(session, order.id, "PAID")
        refreshed = await repository.get_presentation_order(session, order.id)
        assert refreshed.status == "PAID"


@pytest.mark.asyncio
async def test_get_presentation_order_returns_none_for_unknown_id(db):
    async with db() as session:
        order = await repository.get_presentation_order(session, "does-not-exist")
        assert order is None


@pytest.mark.asyncio
async def test_get_setting_returns_default_when_unset(db):
    async with db() as session:
        value = await repository.get_setting(session, "price_per_slide", "350")
        assert value == "350"


@pytest.mark.asyncio
async def test_set_setting_then_get_setting_roundtrips(db):
    async with db() as session:
        await repository.set_setting(session, "price_per_slide", "500")
        value = await repository.get_setting(session, "price_per_slide", "350")
        assert value == "500"


@pytest.mark.asyncio
async def test_set_setting_overwrites_existing_value(db):
    async with db() as session:
        await repository.set_setting(session, "min_slides", "5")
        await repository.set_setting(session, "min_slides", "8")
        value = await repository.get_setting(session, "min_slides", "0")
        assert value == "8"


@pytest.mark.asyncio
async def test_create_payment_transaction_starts_waiting_for_payment(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        order = await repository.create_presentation_order(
            session=session, user_id=111, topic="A", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        tx = await repository.create_payment_transaction(session, order.id, 111, 1750, provider="CLICK")
        assert tx.status == "WAITING_PAYMENT"
        assert tx.amount == 1750


@pytest.mark.asyncio
async def test_user_orders_count_only_counts_that_user(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        await repository.get_or_create_user(session, 222, "Bob", "bob")
        await repository.create_presentation_order(
            session=session, user_id=111, topic="A", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        await repository.create_presentation_order(
            session=session, user_id=111, topic="B", subject="S", slide_count=5,
            template_id="01_midnight_tech", total_price=1750
        )
        count_111 = await repository.get_user_orders_count(session, 111)
        count_222 = await repository.get_user_orders_count(session, 222)
        assert count_111 == 2
        assert count_222 == 0


@pytest.mark.asyncio
async def test_referral_count_tracks_referred_users(db):
    async with db() as session:
        await repository.get_or_create_user(session, 111, "Alice", "alice")
        await repository.get_or_create_user(session, 222, "Bob", "bob", referred_by=111)
        await repository.get_or_create_user(session, 333, "Carol", "carol", referred_by=111)
        count = await repository.get_user_referrals_count(session, 111)
        assert count == 2
