"""The free first presentation, bonus presentations and the referral programme."""
import os

import pytest
from sqlalchemy import select

from bot.handlers import create_pres, start as start_module
from database import repository
from database.models import PresentationOrder, User
from services import credits, guard, runtime
from services.payment import orders
from tests.fixtures.telegram_fakes import FakeCallbackQuery, FakeFSMContext, FakeMessage, FakeUser


@pytest.fixture
def trial_on():
    runtime._values["free_trial"] = "1"


@pytest.fixture
def payments_off(monkeypatch):
    monkeypatch.setattr("config.settings.ALLOW_DEMO_PAYMENTS", False)
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "DEMO")
    monkeypatch.setattr("config.settings.TEZCHECK_API_KEY", "")
    assert orders.payment_mode() == "off"


async def _user(db, uid, **kw):
    async with db() as s:
        await repository.get_or_create_user(s, uid, kw.pop("name", f"U{uid}"), None, **kw)


async def _order(db, uid, price=3500):
    async with db() as s:
        o = await repository.create_presentation_order(s, uid, "Mavzu", "Fan", 10, "05_nature_organic", price)
        return o.id


@pytest.mark.asyncio
async def test_trial_is_spent_once_then_bonus_then_nothing(patched_handlers_db, trial_on):
    await _user(patched_handlers_db, 1)
    assert (await credits.available(1)).total == 1
    assert await credits.claim(1, 10) == credits.TRIAL
    assert await credits.claim(1, 10) is None
    await credits.add_bonus(1, 2)
    assert (await credits.available(1)).total == 2
    assert await credits.claim(1, 10) == credits.BONUS
    assert await credits.claim(1, 10) == credits.BONUS
    assert await credits.claim(1, 10) is None
    await credits.add_bonus(1, -5)  # never below zero
    assert (await credits.available(1)).bonus == 0


@pytest.mark.asyncio
async def test_free_presentation_has_a_size_limit(patched_handlers_db, trial_on):
    await _user(patched_handlers_db, 2)
    runtime._values["free_max_slides"] = "12"
    assert await credits.claim(2, 20) is None          # too big: paid as usual
    assert (await credits.available(2)).trial          # and the trial is kept
    assert await credits.claim(2, 12) == credits.TRIAL


@pytest.mark.asyncio
async def test_trial_can_be_switched_off(patched_handlers_db):
    await _user(patched_handlers_db, 3)
    assert (await credits.available(3)).total == 0
    assert await credits.claim(3, 5) is None


@pytest.mark.asyncio
async def test_free_user_may_create_while_payments_are_off(patched_handlers_db, trial_on, payments_off):
    await _user(patched_handlers_db, 4)
    assert not guard.creation_open()
    assert await guard.check(4) is None
    assert await guard.check(4, slide_count=10) is None
    assert (await guard.check(4, slide_count=40)).reason == "closed"   # bigger than the free size
    await credits.claim(4, 10)
    assert (await guard.check(4)).reason == "closed"                  # the free one is used up


@pytest.mark.asyncio
async def test_referral_bonus_comes_with_the_friends_first_real_payment(patched_handlers_db, trial_on):
    await _user(patched_handlers_db, 10, name="Ali")
    await _user(patched_handlers_db, 11, name="Vali", referred_by=10)
    free_order = await _order(patched_handlers_db, 11)
    await orders.mark_paid(free_order, by=credits.TRIAL, amount=0)
    assert (await credits.available(10)).bonus == 0          # a free presentation earns nothing (fake accounts)

    paid1, paid2 = await _order(patched_handlers_db, 11), await _order(patched_handlers_db, 11)
    await orders.mark_paid(paid1, by="TEZCHECK", amount=3500)
    await orders.mark_paid(paid2, by="TEZCHECK", amount=3500)
    assert (await credits.available(10)).bonus == 1          # once per friend
    st = await credits.stats(10)
    assert (st.invited, st.paid) == (1, 1)


@pytest.mark.asyncio
async def test_referral_trigger_first_rewards_the_first_presentation(patched_handlers_db, trial_on):
    runtime._values["referral_trigger"] = "first"
    runtime._values["referral_bonus"] = "2"
    await _user(patched_handlers_db, 20)
    await _user(patched_handlers_db, 21, referred_by=20)
    await orders.mark_paid(await _order(patched_handlers_db, 21), by=credits.TRIAL, amount=0)
    assert (await credits.available(20)).bonus == 2


@pytest.mark.asyncio
async def test_admin_test_payment_never_rewards(patched_handlers_db, trial_on):
    runtime._values["referral_trigger"] = "first"
    await _user(patched_handlers_db, 30)
    await _user(patched_handlers_db, 31, referred_by=30)
    await orders.mark_paid(await _order(patched_handlers_db, 31), by="TEST", amount=0)
    assert (await credits.available(30)).bonus == 0


@pytest.mark.asyncio
async def test_start_links_only_new_users_to_real_inviters_and_tells_the_inviter(patched_handlers_db, trial_on):
    await _user(patched_handlers_db, 40, name="Inviter")
    msg = FakeMessage(text="/start ref_41000", from_user=FakeUser(id=41))   # unknown inviter
    await start_module.cmd_start(msg, FakeFSMContext())
    msg = FakeMessage(text="/start ref_40", from_user=FakeUser(id=42))
    await start_module.cmd_start(msg, FakeFSMContext())
    async with patched_handlers_db() as s:
        assert (await repository.get_user(s, 41)).referred_by is None
        assert (await repository.get_user(s, 42)).referred_by == 40
    assert any(m["chat_id"] == 40 and "Yangi do‘st" in m["text"] for m in msg.bot.sent_messages)
    welcome = msg.calls_for("answer")[-1]["text"]
    assert "BEPUL" in welcome


@pytest.mark.asyncio
async def test_referral_screen_shows_stats_and_share_button(patched_handlers_db, trial_on):
    await _user(patched_handlers_db, 50)
    await _user(patched_handlers_db, 51, referred_by=50)
    msg = FakeMessage(text="🎁 Referal", from_user=FakeUser(id=50))
    await start_module.show_referral(msg)
    call = msg.calls_for("answer")[-1]
    assert "start=ref_50" in call["text"] and "Taklif qilinganlar: <b>1</b>" in call["text"]
    urls = [b.url for row in call["reply_markup"].inline_keyboard for b in row if b.url]
    assert urls and urls[0].startswith("https://t.me/share/url?url=")


@pytest.fixture
def sandboxed_create_pres(monkeypatch, tmp_path):
    monkeypatch.setattr(create_pres, "__file__", os.path.join(str(tmp_path), "root", "bot", "handlers", "create_pres.py"))


@pytest.mark.asyncio
async def test_first_presentation_is_delivered_free_without_payment(
        patched_handlers_db, sandboxed_create_pres, no_openai_key, trial_on, payments_off):
    uid = 60
    await _user(patched_handlers_db, uid)
    state = FakeFSMContext()
    await state.update_data(template_id="05_nature_organic", subject="Biologiya", topic="Fotosintez",
                            slide_count=6, author_name="Jasur", language="uz", additional_notes="", total_price=2100)
    cb = FakeCallbackQuery(data="confirm_pres_temp_order", from_user=FakeUser(id=uid))
    await create_pres.generate_and_preview_presentation(cb, state)

    async with patched_handlers_db() as s:
        order = (await s.execute(select(PresentationOrder).where(PresentationOrder.user_id == uid))).scalars().one()
        user = await s.get(User, uid)
    assert order.status == "PAID" and order.paid_by == "TRIAL" and order.paid_amount == 0
    assert order.delivered_at is not None
    assert user.trial_used_at is not None
    docs = [m for m in cb.message.bot.sent_messages if m.get("document")]
    assert len(docs) == 2                                         # PPTX and PDF, no payment asked
    assert any("Bepul taqdimotingiz tayyor" in (m["text"] or "") for m in cb.message.bot.sent_messages)
    assert "Do‘stlaringizni taklif qiling" in cb.message.calls_for("answer")[-1]["text"]
    assert (await guard.check(uid)).reason == "closed"            # the next one waits for payments


@pytest.mark.asyncio
async def test_wizard_tells_about_the_free_presentation_and_its_size(patched_handlers_db, trial_on, payments_off):
    from bot.states.forms import PresentationForm
    runtime._values["free_max_slides"] = "12"
    await _user(patched_handlers_db, 70)
    state = FakeFSMContext()
    await state.set_state(PresentationForm.topic)
    msg = FakeMessage(text="Fotosintez", from_user=FakeUser(id=70))
    await create_pres.process_topic(msg, state)
    text = msg.calls_for("answer")[-1]["text"]
    assert "Birinchi taqdimotingiz bepul" in text and "maksimum: 12" in text
    big = FakeMessage(text="20", from_user=FakeUser(id=70))
    await create_pres.process_slide_count(big, state)
    assert "12 slaydgacha" in big.calls_for("answer")[-1]["text"] or "Maksimum" in big.calls_for("answer")[-1]["text"]
    ok = FakeMessage(text="10", from_user=FakeUser(id=70))
    await create_pres.process_slide_count(ok, state)
    assert (await state.get_data())["slide_count"] == 10
