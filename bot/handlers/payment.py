import os
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from database.connection import AsyncSessionLocal
from database import repository
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


# ---------------------------------------------------------------------- TezCheck
async def _bot_username(bot) -> str:
    try:
        me = await bot.me()
        return me.username or ""
    except Exception:  # noqa: BLE001
        return ""


def _watch_payment(bot, order_id: str, chat_id: int) -> None:
    """Files come by themselves as soon as TezCheck says the bill is paid (no webhook needed)."""
    async def notify(text: str):
        await bot.send_message(chat_id, text)
    orders.watch_bill(order_id, lambda oid: deliver_order(bot, oid), notify)


@router.callback_query(F.data.startswith("tc_pay_"))
async def tezcheck_pay(callback: CallbackQuery):
    await _pay(callback, callback.data.replace("tc_pay_", "", 1))


async def _pay(callback: CallbackQuery, order_id: str) -> None:
    """Creates (or reuses) the TezCheck bill and shows the payment page button."""
    if payment_mode() != "tezcheck":
        await _answer(callback, PAYMENTS_OFF, alert=True)
        return
    await _answer(callback, "⏳ To‘lov sahifasi tayyorlanmoqda…")
    url, reason = await orders.get_payment_link(order_id, callback.from_user.id, await _bot_username(callback.bot))
    if reason == "paid":
        if not await deliver_order(callback.bot, order_id, force=True):
            await callback.message.answer("✅ Bu buyurtma to‘langan. Fayllar yuborilmoqda…")
        return
    if not url:
        await callback.message.answer({
            "not_found": "⚠️ Buyurtma topilmadi.",
            "denied": "⚠️ Bu buyurtma sizniki emas.",
            "closed": "⚠️ Bu buyurtma bekor qilingan. Yangi taqdimot yarating.",
            "off": PAYMENTS_OFF,
            "amount": "⚠️ Buyurtma summasi juda kichik (kamida 1 000 so‘m). Admin bilan bog‘laning.",
            "pending": "🔄 Oldingi to‘lovingiz hali tekshirilmoqda — qayta to‘lamang, natijani o‘zimiz yuboramiz.",
        }.get(reason, "⚠️ To‘lov tizimiga hozir ulanib bo‘lmadi. Bir daqiqadan so‘ng qayta urinib ko‘ring."))
        if reason == "pending":
            _watch_payment(callback.bot, order_id, callback.from_user.id)
        return
    text = ("💳 <b>To‘lov</b>\n\n"
            "Pastdagi tugma orqali to‘lov sahifasini oching va <b>Click</b> yoki <b>Payme</b> bilan to‘lang.\n\n"
            "✅ To‘lov o‘tishi bilan PowerPoint va PDF fayllar <b>avtomatik</b> shu yerga yuboriladi.\n"
            "<i>Karta ma’lumotlaringiz bizga ko‘rinmaydi — to‘lov TezCheck’ning xavfsiz sahifasida bo‘ladi.</i>")
    _watch_payment(callback.bot, order_id, callback.from_user.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=get_tezcheck_link_keyboard(order_id, url))
        await callback.message.answer(text, parse_mode="HTML")
    except Exception:  # noqa: BLE001
        await callback.message.answer(text, reply_markup=get_tezcheck_link_keyboard(order_id, url), parse_mode="HTML")


@router.callback_query(F.data.startswith("tc_chk_"))
async def tezcheck_check(callback: CallbackQuery):
    await _check(callback, callback.data.replace("tc_chk_", "", 1))


async def _check(callback: CallbackQuery, order_id: str) -> None:
    async with AsyncSessionLocal() as session:
        order = await repository.get_presentation_order(session, order_id)
    if not order or order.user_id != callback.from_user.id:
        await _answer(callback, "⚠️ Buyurtma topilmadi.", alert=True)
        return
    if order.status == "PAID":
        await _answer(callback, "✅ To‘langan")
        await deliver_order(callback.bot, order_id, force=True)
        return
    if payment_mode() != "tezcheck":
        await _answer(callback, PAYMENTS_OFF, alert=True)
        return
    await _answer(callback, "🔎 Tekshirilmoqda…")
    await _tezcheck_check(callback.message, callback.bot, order_id)


async def _answer(callback: CallbackQuery, text: str, alert: bool = False) -> None:
    try:
        await callback.answer(text, show_alert=alert)
    except Exception:  # noqa: BLE001 - "query is too old" after a slow request
        pass


async def _tezcheck_check(message, bot, order_id: str) -> None:
    result, st = await orders.check_bill(order_id)
    if result in ("paid", "already"):
        if not await deliver_order(bot, order_id, force=(result == "already")):
            await message.answer("✅ To‘lov qabul qilingan. Fayllar yuborilmoqda…")
        return
    if result in ("waiting", "unknown", "failed"):
        _watch_payment(bot, order_id, message.chat.id)  # e.g. after a restart: keep watching
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
    if order.status == "PAID":
        if not await deliver_order(message.bot, order_id):
            await message.answer("✅ To‘lov qabul qilingan — fayllar yuborilgan (yuqoriroqda).")
        return
    if payment_mode() != "tezcheck":
        await message.answer(PAYMENTS_OFF)
        return
    await _tezcheck_check(message, message.bot, order_id)


# ------------------------------------------------- buttons of old messages (before TezCheck)
@router.callback_query(F.data.startswith("pay_checkout_") | F.data.startswith("pay_click_")
                       | F.data.startswith("pay_payme_"))
async def process_old_pay_button(callback: CallbackQuery):
    """Old "To'lov qilish" / Click / Payme buttons: TezCheck is the only payment system now."""
    await _pay(callback, callback.data.split("_", 2)[2])


@router.callback_query(F.data.startswith("check_pay_"))
async def process_check_payment(callback: CallbackQuery):
    """Old "To'lovni tasdiqlash" button: only TezCheck can say an order is paid."""
    await _check(callback, callback.data.replace("check_pay_", "", 1))


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
