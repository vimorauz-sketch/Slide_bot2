import os
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from config import settings
from database.connection import AsyncSessionLocal
from database import repository
from bot.keyboards.inline import get_download_format_inline_keyboard, get_payment_link_inline_keyboard
from services.payment.providers import MockPaymentProvider, ClickPaymentProvider, PaymePaymentProvider
from services.payment import orders
from services.payment.orders import payment_mode
from bot.delivery import deliver_order
from bot.keyboards.inline import get_tezcheck_link_keyboard

logger = logging.getLogger(__name__)


def _file_name(topic: str, ext: str) -> str:
    """Safe download name: no / \\ : * ? " < > | characters (they break the file on Windows/phones)."""
    import re
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", topic or "")
    name = " ".join(name.split())[:40].strip() or "Taqdimot"
    return f"SlideLab_{name}.{ext}"


router = Router()

PAYMENTS_OFF = ("💳 To‘lov tizimi hozircha ishlamayapti — tez orada ulanadi. "
                "Ulanishi bilan shu buyurtmani to‘lab, fayllarni olishingiz mumkin.")
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

# ---------------------------------------------------------------------- TezCheck
async def _bot_username(bot) -> str:
    try:
        me = await bot.me()
        return me.username or ""
    except Exception:  # noqa: BLE001
        return ""


@router.callback_query(F.data.startswith("tc_pay_"))
async def tezcheck_pay(callback: CallbackQuery):
    """Creates (or reuses) the TezCheck bill and shows the payment page button."""
    order_id = callback.data.replace("tc_pay_", "")
    try:
        await callback.answer("⏳ To‘lov sahifasi tayyorlanmoqda…")
    except Exception:  # noqa: BLE001
        pass
    url, reason = await orders.get_payment_link(order_id, callback.from_user.id, await _bot_username(callback.bot))
    if reason == "paid":
        await deliver_order(callback.bot, order_id, force=True)
        return
    if not url:
        await callback.message.answer({
            "not_found": "⚠️ Buyurtma topilmadi.",
            "denied": "⚠️ Bu buyurtma sizniki emas.",
        }.get(reason, "⚠️ To‘lov tizimiga hozir ulanib bo‘lmadi. Bir daqiqadan so‘ng qayta urinib ko‘ring."))
        return
    text = ("💳 <b>To‘lov</b>\n\n"
            "Pastdagi tugma orqali to‘lov sahifasini oching va <b>Click</b> yoki <b>Payme</b> bilan to‘lang.\n\n"
            "✅ To‘lov o‘tishi bilan PowerPoint va PDF fayllar <b>avtomatik</b> shu yerga yuboriladi.\n"
            "<i>Karta ma’lumotlaringiz bizga ko‘rinmaydi — to‘lov TezCheck’ning xavfsiz sahifasida bo‘ladi.</i>")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_tezcheck_link_keyboard(order_id, url))
        await callback.message.answer(text, parse_mode="HTML")
    except Exception:  # noqa: BLE001
        await callback.message.answer(text, reply_markup=get_tezcheck_link_keyboard(order_id, url), parse_mode="HTML")


@router.callback_query(F.data.startswith("tc_chk_"))
async def tezcheck_check(callback: CallbackQuery):
    order_id = callback.data.replace("tc_chk_", "")
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("⚠️ Buyurtma topilmadi.", show_alert=True)
        return
    try:
        await callback.answer("🔎 Tekshirilmoqda…")
    except Exception:  # noqa: BLE001
        pass
    await _tezcheck_check(callback.message, callback.bot, order_id)


async def _tezcheck_check(message, bot, order_id: str) -> None:
    result, st = await orders.check_bill(order_id)
    if result in ("paid", "already"):
        if not await deliver_order(bot, order_id, force=(result == "already")):
            await message.answer("✅ To‘lov qabul qilingan. Fayllar yuborilmoqda…")
        return
    await message.answer({
        "waiting": "⏳ To‘lov hali kelmadi. To‘lov sahifasida to‘lovni yakunlang — fayllar avtomatik keladi.",
        "unknown": "🔄 To‘lov tekshirilmoqda (bank javobi kutilmoqda). Bir necha daqiqada natijani o‘zimiz yuboramiz — "
                   "qayta to‘lamang.",
        "failed": "❌ To‘lov o‘tmadi" + (f" ({st.problem})" if st and st.problem else "") +
                  ". To‘lov sahifasida qaytadan urinib ko‘ring.",
        "no_bill": "💳 Avval «To‘lash» tugmasini bosing.",
    }.get(result, "⚠️ Hozir tekshirib bo‘lmadi. Birozdan so‘ng qayta urinib ko‘ring."))


async def handle_paid_deeplink(message, order_id: str) -> None:
    """/start paid_<order>: the customer came back from the payment page."""
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order or order.user_id != message.from_user.id:
        await message.answer("⚠️ Buyurtma topilmadi.")
        return
    await _tezcheck_check(message, message.bot, order_id)


@router.callback_query(F.data.startswith("pay_checkout_"))
async def process_pay_checkout(callback: CallbackQuery):
    order_id = callback.data.replace("pay_checkout_", "")
    mode = payment_mode()
    if mode == "tezcheck":  # an old demo button: real payments only
        callback.data = f"tc_pay_{order_id}"
        await tezcheck_pay(callback)
        return
    if not orders.test_payment_allowed(callback.from_user.id):
        await callback.answer(PAYMENTS_OFF, show_alert=True)
        return
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
    admin_test = False

    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
        if not order:
            await callback.answer("⚠️ Buyurtma topilmadi.", show_alert=True)
            return

        # Security check: verify order user_id matches requesting user
        if order.user_id != callback.from_user.id:
            await callback.answer("⚠️ Access Denied: Boshqa foydalanuvchining buyurtmasi.", show_alert=True)
            return

        if payment_mode() == "tezcheck":
            # real payments: only TezCheck can say the order is paid
            await callback.answer()
            await _tezcheck_check(callback.message, callback.bot, order_id)
            return

        if _payment_env() == "PRODUCTION" and order.status != "PAID":
            # order.status is flipped to "PAID" by the Click/Payme webhook handlers
            # (services/payment/click_webhook.py PerformTransaction / Complete,
            # services/payment/payme_webhook.py PerformTransaction) once the
            # provider confirms the payment -- not by this button. If we get here,
            # the webhook callback simply hasn't arrived yet.
            await callback.answer("❌ Production Mode: Click/Payme to'lov kutilmoqda.", show_alert=True)
            return

        if order.status != "PAID":
            if not orders.test_payment_allowed(callback.from_user.id):
                # no working payment system: this button must never give files away
                await callback.answer(PAYMENTS_OFF, show_alert=True)
                return
            if payment_mode() == "demo":  # ALLOW_DEMO_PAYMENTS=true, testing only
                await repository.update_order_status(session, order_id, "PAID")
            else:
                admin_test = True

    if admin_test:
        # an admin testing before payments are connected: no money, so revenue stays untouched
        await orders.mark_paid(order_id, by="TEST", amount=0)

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

    try:  # answered now: preparing the file can take longer than Telegram waits for an answer
        await callback.answer("⏳ Fayl yuborilmoqda…")
    except Exception:  # noqa: BLE001
        pass
    return order


async def _wait_files(order) -> None:
    """The PDF/PPTX are built in the background after the previews; wait for them if needed."""
    path = order.pdf_path or order.pptx_path
    if path and not (os.path.exists(order.pdf_path or "") and os.path.exists(order.pptx_path or "")):
        from services.presentation import ensure_files
        try:
            await ensure_files(os.path.dirname(path))
        except Exception:  # noqa: BLE001 - the PDF fallback below still works
            logger.exception("files for order %s could not be built", order.id)


async def _ensure_pdf_path(order) -> str:
    await _wait_files(order)
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
    await _wait_files(order)
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
