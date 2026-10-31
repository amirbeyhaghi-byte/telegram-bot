import asyncio
import logging
import os
import socket

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

from app.database.database import close_database  # noqa: E402
from app.handlers.registration import router as registration_router  # noqa: E402
from app.handlers.main_menu import router as main_menu_router  # noqa: E402
from app.handlers.food import router as food_router  # noqa: E402
from app.handlers.account import router as account_router  # noqa: E402
from app.handlers.subscription import router as subscription_router  # noqa: E402
from app.handlers.admin import router as admin_router  # noqa: E402
from app.handlers.admin_users import router as admin_users_router  # noqa: E402
from app.handlers.payment import router as payment_router  # noqa: E402
from app.middlewares.account_status import AccountStatusMiddleware  # noqa: E402
from app.handlers.temperament import router as temperament_router  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN در فایل .env تنظیم نشده است."
    )


def build_storage():
    """
    ذخیره وضعیت نشست‌ها:
    - اگر REDIS_URL در .env باشد: Redis (نشست‌ها با ری‌استارت ربات پاک نمی‌شوند)
    - در غیر این صورت: حافظه (با ری‌استارت همه باید دوباره وارد شوند)
    """
    redis_url = (os.getenv("REDIS_URL") or "").strip()

    if not redis_url:
        return MemoryStorage()

    try:
        from aiogram.fsm.storage.redis import RedisStorage
    except ImportError as error:
        raise RuntimeError(
            "REDIS_URL تنظیم شده ولی بسته redis نصب نیست "
            "(pip install redis) یا REDIS_URL را از .env حذف کنید."
        ) from error

    return RedisStorage.from_url(redis_url)


dp = Dispatcher(storage=build_storage())


# =========================
# /start
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):

    from app.keyboards.registration import registration_keyboard

    await state.clear()

    await message.answer(
        "🌿 به سامانه مزاج شناسی بیهقی خوش آمدید.\n\n"
        "این سامانه با هدف ارائه خدمات مرتبط با "
        "مزاج‌شناسی و شناخت طبع خوراکی‌ها طراحی شده است.\n\n"
        "برای استفاده از خدمات سامانه، ابتدا باید ثبت‌نام کنید.",
        reply_markup=registration_keyboard(),
    )


# =========================
# درباره سامانه
# =========================

@dp.message(F.text == "ℹ️ درباره سامانه")
async def about_handler(message: Message):
    await message.answer(
        "ℹ️ <b>درباره سامانه</b>\n\n"
        "سامانه مزاج‌شناسی بیهقی برای شناخت مزاج افراد "
        "و طبع خوراکی‌ها بر پایه طب سنتی طراحی شده است.\n\n"
        "برای استفاده از خدمات، ثبت‌نام کنید یا وارد حساب خود شوید.",
        parse_mode="HTML",
    )


# =========================
# Middleware: حساب‌های غیرفعال از همه بخش‌ها بیرون انداخته می‌شوند
# =========================

dp.message.outer_middleware(AccountStatusMiddleware())
dp.callback_query.outer_middleware(AccountStatusMiddleware())


# =========================
# Routers
# =========================

dp.include_router(registration_router)
dp.include_router(food_router)
dp.include_router(temperament_router)
dp.include_router(account_router)
dp.include_router(main_menu_router)
dp.include_router(subscription_router)
dp.include_router(admin_router)
dp.include_router(admin_users_router)
dp.include_router(payment_router)


# =========================
# Start Bot
# =========================

async def main():

    # اگر Redis تنظیم شده ولی در دسترس نیست، همین‌جا با پیام روشن متوقف می‌شویم
    redis_client = getattr(dp.storage, "redis", None)

    if redis_client is not None:
        try:
            await redis_client.ping()
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(
                "اتصال به Redis برقرار نشد؛ REDIS_URL را بررسی کنید "
                "یا برای استفاده از حافظه آن را از .env حذف کنید."
            ) from error

    session = AiohttpSession(
        timeout=60,
        limit=100,
    )

    session._connector_init["family"] = socket.AF_INET

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
    )

    logger.info("ربات سامانه مزاج شناسی بیهقی فعال شد.")

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        await dp.storage.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
