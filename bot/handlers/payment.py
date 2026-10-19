import os
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from config import settings
from database.connection import AsyncSessionLocal
from database import repository
from bot.keyboards.inline import get_download_format_inline_keyboard, get_payment_link_inline_keyboard
from services.payment.providers import MockPaymentProvider, ClickPaymentProvider, PaymePaymentProvider

logger = logging.getLogger(__name__)


def _file_name(topic: str, ext: str) -> str:
    """Safe download name: no / \\ : * ? " < > | characters (they break the file on Windows/phones)."""
    import re
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", topic or "")
    name = " ".join(name.split())[:40].strip() or "Taqdimot"
    return f"SlideLab_{name}.{ext}"
router = Router()
payment_provider = MockPaymentProvider()


def _payment_env() -> str:
    """Read live rather than caching at import time, so PAYMENT_ENV can be
    monkeypatched in tests and so a settings reload is picked up without a
    fresh process. Can be "DEMO" or "PRODUCTION"."""
    return settings.PAYMENT_ENV.upper()

async def _start_checkout(callback: CallbackQuery, order_id: str, provider_name: str, provider) -> None:
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
        if not order:
            await callback.answer("⚠️ Buyurtma topilmadi.", show_alert=True)
            return

        if order.user_id != callback.from_user.id:
            await callback.answer("⚠️ Ruxsat etilmagan amal (Access Denied).", show_alert=True)
            return

        await repository.create_payment_transaction(
            session=session,
            order_id=order_id,
            user_id=callback.from_user.id,
            amount=order.total_price,
            provider=provider_name
        )

    pay_info = await provider.create_checkout(order_id, order.total_price, f"SlideLab Order {order_id}")

    text = (
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"<b>Buyurtma ID:</b> <code>{order_id}</code>\n"
        f"<b>To'lov summasi:</b> {order.total_price} so'm\n\n"
        f"<i>Mode: {_payment_env()} ({provider_name})</i>\n"
        f"Quyidagi havola orqali to'lovni amalga oshiring, so'ng <b>'✅ To'lovni tasdiqlash'</b> tugmasini bosing."
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_payment_link_inline_keyboard(order_id, pay_info["checkout_url"]),
            parse_mode="HTML"
        )
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data.startswith("pay_checkout_"))
async def process_pay_checkout(callback: CallbackQuery):
    order_id = callback.data.replace("pay_checkout_", "")
    await _start_checkout(callback, order_id, "MOCK", payment_provider)

@router.callback_query(F.data.startswith("pay_click_"))
async def process_pay_checkout_click(callback: CallbackQuery):
    order_id = callback.data.replace("pay_click_", "")
    provider = ClickPaymentProvider(service_id=settings.CLICK_SERVICE_ID, merchant_id=settings.CLICK_MERCHANT_ID)
    await _start_checkout(callback, order_id, "CLICK", provider)

@router.callback_query(F.data.startswith("pay_payme_"))
async def process_pay_checkout_payme(callback: CallbackQuery):
    order_id = callback.data.replace("pay_payme_", "")
    provider = PaymePaymentProvider(merchant_id=settings.PAYME_MERCHANT_ID)
    await _start_checkout(callback, order_id, "PAYME", provider)

@router.callback_query(F.data.startswith("check_pay_"))
async def process_check_payment(callback: CallbackQuery):
    order_id = callback.data.replace("check_pay_", "")

    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
        if not order:
            await callback.answer("⚠️ Buyurtma topilmadi.", show_alert=True)
            return

        # Security check: verify order user_id matches requesting user
        if order.user_id != callback.from_user.id:
            await callback.answer("⚠️ Access Denied: Boshqa foydalanuvchining buyurtmasi.", show_alert=True)
            return

        if _payment_env() == "PRODUCTION" and order.status != "PAID":
            # order.status is flipped to "PAID" by the Click/Payme webhook handlers
            # (services/payment/click_webhook.py PerformTransaction / Complete,
            # services/payment/payme_webhook.py PerformTransaction) once the
            # provider confirms the payment -- not by this button. If we get here,
            # the webhook callback simply hasn't arrived yet.
            await callback.answer("❌ Production Mode: Click/Payme to'lov kutilmoqda.", show_alert=True)
            return

        # In DEMO mode or once verified in PRODUCTION -> mark status as PAID
        await repository.update_order_status(session, order_id, "PAID")

    success_msg = (
        "🎉 <b>To'lov muvaffaqiyatli amalga oshirildi!</b>\n\n"
        "Sizning to‘liq presentationingiz watermarklarsiz tayyor.\n\n"
        "⬇️ <b>Qaysi formatda yuklab olmoqchisiz?</b>"
    )
    await callback.message.answer(
        success_msg,
        reply_markup=get_download_format_inline_keyboard(order_id),
        parse_mode="HTML"
    )

    try:
        await callback.answer("✅ To'lov muvaffaqiyatli tasdiqlandi!")
    except Exception:
        pass


async def _get_paid_order_or_deny(callback: CallbackQuery, order_id: str):
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
        if not order:
            await callback.answer("⚠️ Buyurtma topilmadi.", show_alert=True)
            return None

        if order.user_id != callback.from_user.id:
            await callback.answer("⚠️ Access Denied: Boshqa foydalanuvchining buyurtmasi.", show_alert=True)
            return None

        if order.status != "PAID":
            await callback.answer("⚠️ Avval to'lovni tasdiqlang.", show_alert=True)
            return None

        return order


async def _ensure_pdf_path(order) -> str:
    if order.pdf_path and os.path.exists(order.pdf_path):
        return order.pdf_path

    # The PDF was removed from disk: rebuild it from the order's saved content.json (same text
    # and photos as the preview the user paid for), or from basic order data as a last resort.
    from services.presentation import rerender_pdf
    storage_dir = os.path.dirname(order.pdf_path) if order.pdf_path else os.path.join("storage", order.id)
    return await rerender_pdf(
        storage_dir,
        fallback_data={"topic": order.topic, "subject": order.subject, "slide_count": order.slide_count},
        theme_key=order.template_id,
    )


async def _send_pdf(callback: CallbackQuery, order):
    pdf_path = await _ensure_pdf_path(order)
    doc_file = FSInputFile(pdf_path, filename=_file_name(order.topic, "pdf"))
    await callback.message.answer_document(
        document=doc_file,
        caption="📄 <b>PDF format</b> (to'liq, watermark-free)",
        parse_mode="HTML"
    )


async def _send_pptx(callback: CallbackQuery, order):
    if order.pptx_path and os.path.exists(order.pptx_path):
        pptx_file = FSInputFile(order.pptx_path, filename=_file_name(order.topic, "pptx"))
        await callback.message.answer_document(
            document=pptx_file,
            caption="📊 <b>PowerPoint (.pptx) format</b>\n<i>PowerPoint yoki Google Slides orqali erkin tahrirlashingiz mumkin.</i>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("⚠️ PowerPoint fayli topilmadi.")


@router.callback_query(F.data.startswith("dl_pdf_"))
async def process_download_pdf(callback: CallbackQuery):
    order_id = callback.data.replace("dl_pdf_", "")
    order = await _get_paid_order_or_deny(callback, order_id)
    if not order:
        return

    await _send_pdf(callback, order)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("dl_pptx_"))
async def process_download_pptx(callback: CallbackQuery):
    order_id = callback.data.replace("dl_pptx_", "")
    order = await _get_paid_order_or_deny(callback, order_id)
    if not order:
        return

    await _send_pptx(callback, order)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("dl_both_"))
async def process_download_both(callback: CallbackQuery):
    order_id = callback.data.replace("dl_both_", "")
    order = await _get_paid_order_or_deny(callback, order_id)
    if not order:
        return

    await _send_pdf(callback, order)
    await _send_pptx(callback, order)
    try:
        await callback.answer()
    except Exception:
        pass
