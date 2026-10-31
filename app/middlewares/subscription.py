import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards.main import main_menu_keyboard
from app.keyboards.registration import registration_keyboard
from app.keyboards.subscription import expired_subscription_keyboard
from app.services.subscription_service import (
    ACCESS_LOGIN_REQUIRED,
    ACCESS_OK,
    expired_message,
    get_access_status,
)
from app.states.main import MainStates

logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """
    دروازه مرکزی اشتراک برای دکمه‌های inline یک روتر.

    - اشتراک فعال (شامل دوره رایگان) → هندلر اجرا می‌شود.
    - اشتراک منقضی → هندلر اجرا نمی‌شود، پیام تمدید نمایش داده می‌شود.
    - کاربر وارد نشده → هندلر اجرا نمی‌شود، به صفحه ورود هدایت می‌شود.

    allowed_callbacks: دکمه‌هایی که حتی بدون اشتراک مجازند (مثل بازگشت به منو).
    """

    def __init__(
        self,
        service_title: str | None = None,
        allowed_callbacks: set[str] | None = None,
    ) -> None:
        self.service_title = service_title
        self.allowed_callbacks = allowed_callbacks or set()

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if event.data in self.allowed_callbacks:
            return await handler(event, data)

        state: FSMContext | None = data.get("state")

        phone_number = None

        if state is not None:
            phone_number = (await state.get_data()).get("phone_number")

        status = await get_access_status(phone_number)

        if status == ACCESS_OK:
            return await handler(event, data)

        logger.info(
            "Service blocked status=%s telegram_id=%s data=%s",
            status,
            event.from_user.id if event.from_user else None,
            event.data,
        )

        if status == ACCESS_LOGIN_REQUIRED:
            if state is not None:
                await state.clear()

            if event.message:
                await event.message.answer(
                    "⚠️ اطلاعات حساب شما در دسترس نیست.\n\n"
                    "لطفاً دوباره وارد حساب شوید.",
                    reply_markup=registration_keyboard(),
                )

            await event.answer()
            return None

        # اشتراک منقضی
        if state is not None:
            await state.set_state(MainStates.menu)

        if event.message:
            text = expired_message(self.service_title)

            try:
                await event.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=expired_subscription_keyboard(),
                )
            except TelegramBadRequest:
                await event.message.answer(
                    text,
                    parse_mode="HTML",
                    reply_markup=expired_subscription_keyboard(),
                )

            await event.message.answer(
                "لطفاً یکی از گزینه‌های منوی اصلی را انتخاب کنید:",
                reply_markup=main_menu_keyboard(phone_number),
            )

        await event.answer()
        return None
