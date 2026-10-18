import os
import pytest
from sqlalchemy import select
from bot.handlers import payment as payment_module
from tests.fixtures.telegram_fakes import FakeCallbackQuery, FakeUser
from database import repository
from database.models import PaymentTransaction


async def _make_order(db, user_id=111, pptx_path=None, pdf_path=None, status=None):
    async with db() as session:
        await repository.get_or_create_user(session, user_id, "Tester", "tester")
        order = await repository.create_presentation_order(
            session=session, user_id=user_id, topic="Fotosintez", subject="Biologiya",
            slide_count=5, template_id="01_midnight_tech", total_price=1750,
            pptx_path=pptx_path, pdf_path=pdf_path
        )
        if status:
            await repository.update_order_status(session, order.id, status)
        return order.id


def _callback(data, user_id=111):
    return FakeCallbackQuery(data=data, from_user=FakeUser(id=user_id))


# ---------------------------------------------------------------------------
# process_pay_checkout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_checkout_denies_unknown_order(patched_handlers_db):
    cb = _callback("pay_checkout_does-not-exist")
    await payment_module.process_pay_checkout(cb)
    assert cb.calls_for("answer")[0]["text"].startswith("⚠️ Buyurtma topilmadi")


@pytest.mark.asyncio
async def test_pay_checkout_denies_other_users_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_checkout_{order_id}", user_id=999)

    await payment_module.process_pay_checkout(cb)

    assert "Access Denied" in cb.calls_for("answer")[0]["text"]
    assert cb.message.calls_for("edit_text") == []


@pytest.mark.asyncio
async def test_pay_checkout_shows_a_clickable_payment_link(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_checkout_{order_id}", user_id=111)

    await payment_module.process_pay_checkout(cb)

    edit_call = cb.message.calls_for("edit_text")[0]
    keyboard = edit_call["reply_markup"]
    url_buttons = [btn.url for row in keyboard.inline_keyboard for btn in row if btn.url]
    # Regression guard: the generated checkout URL must actually reach the user,
    # not just be computed and discarded.
    assert any(order_id in url or "checkout" in url.lower() or "t.me" in url for url in url_buttons)


@pytest.mark.asyncio
async def test_pay_checkout_records_a_payment_transaction(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_checkout_{order_id}", user_id=111)

    await payment_module.process_pay_checkout(cb)

    async with patched_handlers_db() as session:
        result = await session.execute(select(PaymentTransaction).where(PaymentTransaction.order_id == order_id))
        transactions = result.scalars().all()
        assert len(transactions) == 1
        assert transactions[0].status == "WAITING_PAYMENT"


# ---------------------------------------------------------------------------
# process_check_payment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_payment_denies_unknown_order(patched_handlers_db):
    cb = _callback("check_pay_does-not-exist")
    await payment_module.process_check_payment(cb)
    assert cb.calls_for("answer")[0]["text"].startswith("⚠️ Buyurtma topilmadi")


@pytest.mark.asyncio
async def test_check_payment_denies_other_users_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"check_pay_{order_id}", user_id=999)

    await payment_module.process_check_payment(cb)

    assert "Access Denied" in cb.calls_for("answer")[0]["text"]
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
        assert order.status != "PAID"


@pytest.mark.asyncio
async def test_check_payment_in_demo_mode_marks_order_paid_and_offers_format_choice(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "DEMO")
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"check_pay_{order_id}", user_id=111)

    await payment_module.process_check_payment(cb)

    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
        assert order.status == "PAID"

    answer_call = cb.message.calls_for("answer")[0]
    assert "formatda" in answer_call["text"]
    callback_datas = [btn.callback_data for row in answer_call["reply_markup"].inline_keyboard for btn in row]
    assert f"dl_pdf_{order_id}" in callback_datas
    assert f"dl_pptx_{order_id}" in callback_datas
    assert f"dl_both_{order_id}" in callback_datas


@pytest.mark.asyncio
async def test_check_payment_in_production_mode_blocks_unverified_payment(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "PRODUCTION")
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"check_pay_{order_id}", user_id=111)

    await payment_module.process_check_payment(cb)

    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
        assert order.status != "PAID"
    assert "Production Mode" in cb.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_check_payment_called_twice_does_not_corrupt_order_status(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "DEMO")
    order_id = await _make_order(patched_handlers_db, user_id=111)

    await payment_module.process_check_payment(_callback(f"check_pay_{order_id}", user_id=111))
    await payment_module.process_check_payment(_callback(f"check_pay_{order_id}", user_id=111))

    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
        assert order.status == "PAID"  # idempotent, not corrupted by a repeated confirm tap


# ---------------------------------------------------------------------------
# Download handlers (dl_pdf / dl_pptx / dl_both)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_download_denied_before_payment(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)  # status defaults to PREVIEW_READY
    cb = _callback(f"dl_both_{order_id}", user_id=111)

    await payment_module.process_download_both(cb)

    assert "to'lovni tasdiqlang" in cb.calls_for("answer")[0]["text"]
    assert cb.message.calls_for("answer_document") == []


@pytest.mark.asyncio
async def test_download_denied_for_other_users_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111, status="PAID")
    cb = _callback(f"dl_both_{order_id}", user_id=999)

    await payment_module.process_download_both(cb)

    assert "Access Denied" in cb.calls_for("answer")[0]["text"]
    assert cb.message.calls_for("answer_document") == []


@pytest.mark.asyncio
async def test_dl_pdf_sends_only_the_pdf(patched_handlers_db, storage_dir):
    pdf_path = os.path.join(storage_dir, "p.pdf")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-fake")
    order_id = await _make_order(patched_handlers_db, user_id=111, pdf_path=pdf_path, status="PAID")
    cb = _callback(f"dl_pdf_{order_id}", user_id=111)

    await payment_module.process_download_pdf(cb)

    docs = cb.message.calls_for("answer_document")
    assert len(docs) == 1
    assert docs[0]["document"].filename.endswith(".pdf")


@pytest.mark.asyncio
async def test_dl_pptx_sends_only_the_pptx(patched_handlers_db, storage_dir):
    pptx_path = os.path.join(storage_dir, "p.pptx")
    with open(pptx_path, "wb") as f:
        f.write(b"fake-pptx-bytes")
    order_id = await _make_order(patched_handlers_db, user_id=111, pptx_path=pptx_path, status="PAID")
    cb = _callback(f"dl_pptx_{order_id}", user_id=111)

    await payment_module.process_download_pptx(cb)

    docs = cb.message.calls_for("answer_document")
    assert len(docs) == 1
    assert docs[0]["document"].filename.endswith(".pptx")


@pytest.mark.asyncio
async def test_dl_pptx_reports_missing_file_instead_of_crashing(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111, pptx_path=None, status="PAID")
    cb = _callback(f"dl_pptx_{order_id}", user_id=111)

    await payment_module.process_download_pptx(cb)

    assert cb.message.calls_for("answer_document") == []
    assert "topilmadi" in cb.message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_dl_both_sends_pdf_and_pptx(patched_handlers_db, storage_dir):
    pdf_path = os.path.join(storage_dir, "p.pdf")
    pptx_path = os.path.join(storage_dir, "p.pptx")
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-fake")
    with open(pptx_path, "wb") as f:
        f.write(b"fake-pptx-bytes")
    order_id = await _make_order(patched_handlers_db, user_id=111, pdf_path=pdf_path, pptx_path=pptx_path, status="PAID")
    cb = _callback(f"dl_both_{order_id}", user_id=111)

    await payment_module.process_download_both(cb)

    docs = cb.message.calls_for("answer_document")
    assert len(docs) == 2
    filenames = {d["document"].filename.rsplit(".", 1)[-1] for d in docs}
    assert filenames == {"pdf", "pptx"}


@pytest.mark.asyncio
async def test_dl_pdf_regenerates_pdf_when_file_missing_from_disk(patched_handlers_db, storage_dir):
    missing_pdf_path = os.path.join(storage_dir, "was_deleted.pdf")  # never actually created
    order_id = await _make_order(patched_handlers_db, user_id=111, pdf_path=missing_pdf_path, status="PAID")
    cb = _callback(f"dl_pdf_{order_id}", user_id=111)

    await payment_module.process_download_pdf(cb)

    docs = cb.message.calls_for("answer_document")
    assert len(docs) == 1  # fell back to on-the-fly regeneration instead of failing


# ---------------------------------------------------------------------------
# Click / Payme checkout initiation (PRODUCTION mode)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pay_click_generates_a_real_click_checkout_link(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.CLICK_SERVICE_ID", "20000")
    monkeypatch.setattr("config.settings.CLICK_MERCHANT_ID", "12345")
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_click_{order_id}", user_id=111)

    await payment_module.process_pay_checkout_click(cb)

    edit_call = cb.message.calls_for("edit_text")[0]
    keyboard = edit_call["reply_markup"]
    url = keyboard.inline_keyboard[0][0].url
    assert "my.click.uz" in url
    assert "service_id=20000" in url
    assert "merchant_id=12345" in url
    assert order_id in url


@pytest.mark.asyncio
async def test_pay_payme_generates_a_real_payme_checkout_link(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.PAYME_MERCHANT_ID", "abc123")
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_payme_{order_id}", user_id=111)

    await payment_module.process_pay_checkout_payme(cb)

    edit_call = cb.message.calls_for("edit_text")[0]
    keyboard = edit_call["reply_markup"]
    url = keyboard.inline_keyboard[0][0].url
    assert "checkout.paycom.uz/abc123" in url
    assert order_id in url


@pytest.mark.asyncio
async def test_pay_click_denies_other_users_order(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_click_{order_id}", user_id=999)

    await payment_module.process_pay_checkout_click(cb)

    assert "Access Denied" in cb.calls_for("answer")[0]["text"]
    assert cb.message.calls_for("edit_text") == []


@pytest.mark.asyncio
async def test_pay_click_records_a_payment_transaction_with_click_provider_label(patched_handlers_db):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"pay_click_{order_id}", user_id=111)

    await payment_module.process_pay_checkout_click(cb)

    async with patched_handlers_db() as session:
        result = await session.execute(select(PaymentTransaction).where(PaymentTransaction.order_id == order_id))
        tx = result.scalars().one()
    assert tx.provider == "CLICK"
