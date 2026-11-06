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
# Buttons of old messages: TezCheck is the only payment system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["pay_checkout_", "pay_click_", "pay_payme_", "check_pay_", "tc_pay_", "tc_chk_"])
async def test_without_tezcheck_no_button_marks_an_order_paid(patched_handlers_db, prefix):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"{prefix}{order_id}", user_id=111)
    handler = {"pay_checkout_": payment_module.process_old_pay_button, "pay_click_": payment_module.process_old_pay_button,
               "pay_payme_": payment_module.process_old_pay_button, "check_pay_": payment_module.process_check_payment,
               "tc_pay_": payment_module.tezcheck_pay, "tc_chk_": payment_module.tezcheck_check}[prefix]
    await handler(cb)
    assert "To‘lov tizimi hozircha ishlamayapti" in cb.calls_for("answer")[-1]["text"]
    async with patched_handlers_db() as session:
        order = await repository.get_presentation_order(session, order_id)
        txs = (await session.execute(select(PaymentTransaction))).scalars().all()
    assert order.status != "PAID" and txs == []


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["pay_checkout_", "pay_click_", "pay_payme_"])
async def test_old_pay_buttons_open_the_tezcheck_page(patched_handlers_db, tezcheck_on, prefix):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    cb = _callback(f"{prefix}{order_id}", user_id=111)
    await payment_module.process_old_pay_button(cb)
    markup = cb.message.calls_for("edit_reply_markup")[0]["reply_markup"]
    assert markup.inline_keyboard[0][0].url.startswith("https://pay.tezcheck.uz/")
    async with patched_handlers_db() as session:
        tx = (await session.execute(select(PaymentTransaction))).scalars().one()
    assert tx.provider == "TEZCHECK"


@pytest.mark.asyncio
async def test_old_check_button_never_confirms_without_money(patched_handlers_db, tezcheck_on):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    await payment_module.process_old_pay_button(_callback(f"pay_checkout_{order_id}"))
    cb = _callback(f"check_pay_{order_id}")
    await payment_module.process_check_payment(cb)
    assert "hali kelmadi" in cb.message.calls_for("answer")[-1]["text"]
    async with patched_handlers_db() as session:
        assert (await repository.get_presentation_order(session, order_id)).status != "PAID"


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["pay_checkout_", "check_pay_", "tc_pay_", "tc_chk_"])
async def test_buttons_deny_unknown_and_other_users_orders(patched_handlers_db, tezcheck_on, prefix):
    order_id = await _make_order(patched_handlers_db, user_id=111)
    handler = {"pay_checkout_": payment_module.process_old_pay_button, "check_pay_": payment_module.process_check_payment,
               "tc_pay_": payment_module.tezcheck_pay, "tc_chk_": payment_module.tezcheck_check}[prefix]
    for oid, uid in (("does-not-exist", 111), (order_id, 999)):
        cb = _callback(f"{prefix}{oid}", user_id=uid)
        await handler(cb)
        said = [c["text"] for c in cb.calls_for("answer")] + [c["text"] for c in cb.message.calls_for("answer")]
        assert any("topilmadi" in t or "sizniki emas" in t for t in said), said
    assert tezcheck_on.bills == {}


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


def test_download_file_names_are_safe():
    from bot.handlers.payment import _file_name
    assert _file_name('Suv/havo: "sikl"?', "pdf") == "SlideLab_Suv havo sikl.pdf"
    assert _file_name("", "pptx") == "SlideLab_Taqdimot.pptx"
