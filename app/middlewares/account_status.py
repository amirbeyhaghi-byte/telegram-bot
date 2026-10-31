import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.keyboards.registration import registration_keyboard
from app.services.user_admin_service import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    get_account_status,
)

logger = logging.getLogger(__name__)

# حالت‌های ورود و ثبت‌نام هنوز «وارد شده» محسوب نمی‌شوند
_ANONYMOUS_STATE_PREFIXES = ("LoginStates", "RegistrationStates")

DISABLED_TEXT = (
    "⛔ <b>حساب کاربری شما غیرفعال شده است.</b>\n\n"
    "برای پیگیری با مدیر سامانه تماس بگیرید."
)

MISSING_TEXT = (
    "⚠️ اطلاعات حساب شما پیدا نشد.\n\n"
    "لطفاً دوباره وارد حساب شوید."
)


class AccountStatusMiddleware(BaseMiddleware):
    """
    اگر کاربرِ واردشده توسط مدیر غیرفعال شود، از همان لحظه
    از ربات خارج می‌شود (روی همه پیام‌ها و دکمه‌ها).
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        state = data.get("state")
        raw_state = data.get("raw_state")

        if (
            state is None
            or raw_state is None
            or raw_state.startswith(_ANONYMOUS_STATE_PREFIXES)
        ):
            return await handler(event, data)

        phone_number = (await state.get_data()).get("phone_number")

        if not phone_number:
            return await handler(event, data)

        status = await get_account_status(phone_number)

        if status == STATUS_ACTIVE:
            return await handler(event, data)

        logger.info(
            "Blocked account status=%s telegram_id=%s",
            status,
            event.from_user.id if event.from_user else None,
        )

        await state.clear()

        text = DISABLED_TEXT if status == STATUS_DISABLED else MISSING_TEXT

        if isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=registration_keyboard(),
                )

            await event.answer()
        else:
            await event.answer(
                text,
                parse_mode="HTML",
                reply_markup=registration_keyboard(),
            )

        return None
