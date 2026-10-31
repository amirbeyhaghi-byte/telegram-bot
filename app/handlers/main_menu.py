import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards.main import main_menu_keyboard
from app.keyboards.subscription import expired_subscription_keyboard
from app.services.subscription_service import (
    ACCESS_LOGIN_REQUIRED,
    ACCESS_OK,
    expired_message,
    get_access_status,
)
from app.states.main import MainStates
from app.utils import is_admin

logger = logging.getLogger(__name__)

router = Router()

# متن دکمه‌های منوی اصلی (برای تشخیص زدن دکمه منو در حالت‌های ورودی مثل کد هدیه)
MENU_TEXTS = {
    "🌿 مزاج شناسی",
    "🍎 طبع شناسی خوراکی ها",
    "👤 حساب کاربری",
    "💳 اشتراک",
    "🔐 پنل مدیریت",
    "🚪 خروج از حساب",
}


async def check_service_access(
    message: Message,
    phone_number: str | None,
    service_title: str,
) -> bool:
    """
    بررسی ورود و اشتراک فعال (دوره رایگان هم اشتراک فعال محسوب می‌شود).
    اگر دسترسی نباشد، پیام مناسب ارسال و False برگردانده می‌شود.
    """
    status = await get_access_status(phone_number)

    if status == ACCESS_OK:
        return True

    if status == ACCESS_LOGIN_REQUIRED:
        await message.answer(
            "⚠️ اطلاعات حساب شما در دسترس نیست.\n\n"
            "لطفاً دوباره وارد حساب شوید."
        )
        return False

    await message.answer(
        expired_message(service_title),
        parse_mode="HTML",
        reply_markup=expired_subscription_keyboard(),
    )

    return False


@router.message(MainStates.menu)
async def main_menu_handler(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    data = await state.get_data()
    phone_number = data.get("phone_number")

    # ---------------------------------
    # مزاج شناسی
    # ---------------------------------

    if text == "🌿 مزاج شناسی":

        if not await check_service_access(
            message,
            phone_number,
            "مزاج شناسی",
        ):
            return

        from app.handlers.temperament import show_temperament_intro

        await show_temperament_intro(message)
        return

    # ---------------------------------
    # طبع شناسی خوراکی ها
    # ---------------------------------

    if text == "🍎 طبع شناسی خوراکی ها":

        if not await check_service_access(
            message,
            phone_number,
            "طبع شناسی خوراکی‌ها",
        ):
            return

        from app.handlers.food import show_food_categories_message

        await show_food_categories_message(message)
        return

    # ---------------------------------
    # حساب کاربری
    # ---------------------------------

    if text == "👤 حساب کاربری":
        from app.handlers.account import show_account

        await show_account(
            message=message,
            state=state,
        )
        return

    # ---------------------------------
    # اشتراک
    # ---------------------------------

    if text == "💳 اشتراک":
        from app.handlers.subscription import show_subscription

        await show_subscription(
            message=message,
            state=state,
        )
        return

    # ---------------------------------
    # پنل مدیریت
    # ---------------------------------

    if text == "🔐 پنل مدیریت":
        from app.handlers.admin import show_admin_panel

        if not is_admin(phone_number):
            logger.warning(
                "Unauthorized admin panel access attempt by telegram_id=%s",
                message.from_user.id if message.from_user else None,
            )
            await message.answer(
                "⛔ شما دسترسی به پنل مدیریت ندارید."
            )
            return

        await show_admin_panel(
            message=message,
            state=state,
        )
        return

    # ---------------------------------
    # خروج از حساب
    # ---------------------------------

    if text == "🚪 خروج از حساب":
        from app.keyboards.registration import registration_keyboard

        await state.clear()

        await message.answer(
            "🚪 <b>با موفقیت از حساب کاربری خارج شدید.</b>\n\n"
            "برای استفاده از سامانه، می‌توانید وارد حساب شوید "
            "یا یک حساب جدید ثبت کنید.",
            reply_markup=registration_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        "لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
        reply_markup=main_menu_keyboard(phone_number),
    )
