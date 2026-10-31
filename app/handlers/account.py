from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, User
from app.keyboards.account import account_keyboard
from app.keyboards.main import main_menu_keyboard
from app.states.main import MainStates
from app.utils import utcnow


router = Router()


async def show_account(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    if not phone_number:
        await message.answer(
            "⚠️ اطلاعات حساب شما در دسترس نیست.\n\n"
            "لطفاً ابتدا از حساب خارج شوید و دوباره وارد شوید."
        )
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.phone_number == phone_number
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "⚠️ اطلاعات کاربر پیدا نشد."
            )
            return

        subscription_result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id
            )
            .order_by(
                Subscription.end_date.desc()
            )
        )

        subscription = (
            subscription_result.scalars().first()
        )

    text = (
        "<b>👤 حساب کاربری</b>\n\n"
        f"👤 <b>نام:</b> "
        f"{user.first_name} {user.last_name}\n"
        f"📱 <b>شماره موبایل:</b> "
        f"{user.phone_number}\n"
        f"📅 <b>تاریخ ثبت‌نام:</b> "
        f"{user.created_at.strftime('%Y/%m/%d')}\n"
    )

    if subscription:
        now = utcnow()

        if subscription.end_date > now:
            status_text = "🟢 فعال"

            remaining_days = (
                subscription.end_date - now
            ).days

            if remaining_days < 0:
                remaining_days = 0

            if subscription.type == "free":
                subscription_type = "دوره رایگان"
            elif subscription.type == "monthly":
                subscription_type = "ماهانه"
            elif subscription.type == "six_months":
                subscription_type = "۶ ماهه"
            elif subscription.type == "yearly":
                subscription_type = "سالیانه"
            else:
                subscription_type = subscription.type

            text += (
                "\n<b>💳 اشتراک</b>\n"
                f"📌 <b>نوع:</b> "
                f"{subscription_type}\n"
                f"🟢 <b>وضعیت:</b> "
                f"{status_text}\n"
                f"📅 <b>شروع:</b> "
                f"{subscription.start_date.strftime('%Y/%m/%d')}\n"
                f"📅 <b>پایان:</b> "
                f"{subscription.end_date.strftime('%Y/%m/%d')}\n"
                f"⏳ <b>مدت باقی‌مانده:</b> "
                f"{remaining_days} روز\n"
            )

        else:
            text += (
                "\n<b>💳 اشتراک</b>\n"
                f"📌 <b>نوع:</b> "
                f"{subscription.type}\n"
                "🔴 <b>وضعیت:</b> منقضی شده\n"
                f"📅 <b>تاریخ پایان:</b> "
                f"{subscription.end_date.strftime('%Y/%m/%d')}\n"
            )

    else:
        text += (
            "\n<b>💳 اشتراک</b>\n"
            "🔴 <b>وضعیت:</b> اشتراکی ثبت نشده است.\n"
        )

    await message.answer(
        text,
        reply_markup=account_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    lambda callback: callback.data == "account_back_main"
)
async def account_back_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    await state.set_state(MainStates.menu)

    await callback.message.edit_text(
        "به منوی اصلی بازگشتید."
    )

    await callback.message.answer(
        "لطفاً خدمت موردنظر خود را انتخاب کنید:",
        reply_markup=main_menu_keyboard(
            phone_number
        ),
    )

    await callback.answer()