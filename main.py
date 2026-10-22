import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError
from aiogram.types import ErrorEvent
from config import settings
from database.connection import init_db
from bot.handlers import start, create_pres, ocr_task, payment, admin
from bot.webhook_app import run_webhook_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
from services import errorlog  # noqa: E402
errorlog.install()  # the dashboard's "Tizim holati" shows the latest errors

async def main():
    logger.info("Initializing database...")
    await init_db()
    from services import runtime
    await runtime.load()

    token = settings.BOT_TOKEN.strip()
    if not token or "YOUR_TELEGRAM_BOT_TOKEN" in token or "ExampleToken" in token:
        logger.error("❌ XATO: Haqqoniy Telegram BOT_TOKEN kiritilmagan!")
        logger.error("👉 Iltimos, .env faylini ochib, BOT_TOKEN=... o'rniga @BotFather bergan tokeningizni kiriting.")
        return

    try:
        bot = Bot(token=token)
    except TokenValidationError:
        logger.error(f"❌ XATO: '{token}' yaroqsiz Telegram bot token formati!")
        logger.error("👉 @BotFather bergan to'g'ri token shakli: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        return

    logger.info("Starting SlideLab Telegram Bot...")
    dp = Dispatcher()

    @dp.errors()
    async def on_error(event: ErrorEvent):
        msg = str(event.exception).lower()
        if any(k in msg for k in ("query is too old", "message is not modified", "message to delete not found",
                                  "bot was blocked by the user", "message can't be deleted")):
            logger.info("ignored Telegram error: %s", event.exception)  # harmless, the user saw nothing wrong
            return True
        logger.exception("Unhandled error while processing update", exc_info=event.exception)
        update = event.update
        chat_id = None
        if update.message:
            chat_id = update.message.chat.id
        elif update.callback_query and update.callback_query.message:
            chat_id = update.callback_query.message.chat.id
        if chat_id:
            try:
                await bot.send_message(
                    chat_id,
                    "⚠️ Kechirasiz, xatolik yuz berdi. Iltimos qayta urinib ko'ring yoki /start buyrug'ini bosing."
                )
            except Exception:
                pass
        return True

    # Flood protection before any handler (admins are never limited)
    from bot.middlewares.throttling import ThrottlingMiddleware
    dp.update.outer_middleware(ThrottlingMiddleware(
        rate=settings.THROTTLE_RATE, burst=settings.THROTTLE_BURST,
        ban_seconds=settings.THROTTLE_BAN_SECONDS, admins=settings.admin_id_list, dynamic=True))
    # Blocked users, maintenance mode and "last seen" (all controlled from the admin dashboard)
    from bot.middlewares.gate import GateMiddleware
    dp.update.outer_middleware(GateMiddleware())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(ocr_task.router)
    dp.include_router(create_pres.router)
    dp.include_router(payment.router)

    webhook_runner = await run_webhook_app(settings.WEBHOOK_HOST, settings.WEBHOOK_PORT, bot, dp)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logger.error("❌ XATO: Kiritilgan Telegram BOT_TOKEN bekor qilingan yoki nohaq (Unauthorized)!")
        logger.error("👉 @BotFather ga kirib, botingiz tokenini qayta olib, .env fayliga kiriting.")
    finally:
        await webhook_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
