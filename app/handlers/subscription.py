import math
from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, SubscriptionCode, User
from app.handlers.main_menu import MENU_TEXTS, main_menu_handler
from app.handlers.payment import TERMS_TEXT
from app.keyboards.main import main_menu_keyboard
from app.keyboards.payment import terms_keyboard
from app.keyboards.subscription import (
    gift_code_keyboard,
    subscription_keyboard,
)
from app.services.payment_service import PLANS
from app.services.subscription_service import apply_subscription_period
from app.states.main import MainStates
from app.utils import format_date, normalize_gift_code, utcnow


router = Router()


# ---------------------------------------------------------------------------
# ثابت‌ها
# ---------------------------------------------------------------------------

SUBSCRIPTION_NAMES = {
    "free": "دوره رایگان",
    "monthly": "ماهانه",
    "six_months": "۶ ماهه",
    "yearly": "سالیانه",
}

PLAN_CALLBACKS = {f"subscription:{plan}" for plan in PLANS}


# ---------------------------------------------------------------------------
# توابع کمکی
# ---------------------------------------------------------------------------

def subscription_type_name(subscription_type: str) -> str:
    return SUBSCRIPTION_NAMES.get(subscription_type, subscription_type)


async def get_user(session, state_data: dict, telegram_id: int | None):
    """
    ابتدا با شماره‌ی تلفن ذخیره‌شده در state کاربر را پیدا می‌کند.
    اگر state پاک شده بود و مدل User ستون telegram_id دارد،
    با آیدی تلگرام او را شناسایی می‌کند.
    """
    phone_number = state_data.get("phone_number")

    if phone_number:
        result = await session.execute(
            select(User).where(User.phone_number == phone_number)
        )
        user = result.scalar_one_or_none()

        if user is not None:
            return user

    if telegram_id is not None and hasattr(User, "telegram_id"):
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    return None


async def get_latest_subscription(session, user_id: int):
    query = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.end_date.desc())
        .limit(1)
    )

    result = await session.execute(query)

    return result.scalars().first()


# ---------------------------------------------------------------------------
# نمایش اشتراک
# ---------------------------------------------------------------------------

async def show_subscription(
    message: Message,
    state: FSMContext,
    telegram_id: int | None = None,
):
    data = await state.get_data()

    if telegram_id is None:
        telegram_id = message.from_user.id if message.from_user else None

    async with AsyncSessionLocal() as session:
        user = await get_user(session, data, telegram_id)

        if user is None:
            await message.answer(
                "⚠️ اطلاعات حساب شما در دسترس نیست.\n"
                "لطفاً دوباره وارد حساب خود شوید."
            )
            return

        subscription = await get_latest_subscription(session, user.id)

    now = utcnow()

    if subscription and subscription.end_date > now:
        remaining_seconds = (subscription.end_date - now).total_seconds()
        remaining_days = max(0, math.ceil(remaining_seconds / 86400))

        subscription_type = subscription_type_name(subscription.type)

        text = (
            "<b>💳 اشتراک</b>\n\n"
            f"📌 <b>نوع اشتراک:</b> {subscription_type}\n"
            "🟢 <b>وضعیت:</b> فعال\n"
            f"📅 <b>تاریخ شروع:</b> {format_date(subscription.start_date)}\n"
            f"📅 <b>تاریخ پایان:</b> {format_date(subscription.end_date)}\n"
            f"⏳ <b>مدت باقی‌مانده:</b> {remaining_days} روز\n\n"
        )

        if subscription.type == "free":
            text += (
                "🎁 شما در حال استفاده از دوره رایگان هستید.\n"
                "پس از پایان دوره رایگان می‌توانید "
                "یکی از اشتراک‌های موجود را خریداری کنید."
            )
        else:
            text += (
                "برای تمدید یا تغییر اشتراک، "
                "یکی از گزینه‌های زیر را انتخاب کنید."
            )

    else:
        text = (
            "<b>💳 اشتراک</b>\n\n"
            "🔴 <b>وضعیت:</b> اشتراک شما به پایان رسیده است.\n\n"
            "برای ادامه استفاده از خدمات سامانه، "
            "یکی از اشتراک‌های زیر را انتخاب کنید:"
        )

    await message.answer(
        text,
        reply_markup=subscription_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# باز کردن صفحه اشتراک از پیام «اشتراک منقضی شده»
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "subscription:open")
async def subscription_open(
    callback: CallbackQuery,
    state: FSMContext,
):
    if callback.message:
        await show_subscription(
            message=callback.message,
            state=state,
            telegram_id=callback.from_user.id,
        )

    await callback.answer()


# ---------------------------------------------------------------------------
# بازگشت به منوی اصلی
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "subscription:back_main")
async def subscription_back_main(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    await state.set_state(MainStates.menu)

    if callback.message:
        await callback.message.edit_text("به منوی اصلی بازگشتید.")

        await callback.message.answer(
            "لطفاً خدمت موردنظر خود را انتخاب کنید:",
            reply_markup=main_menu_keyboard(phone_number),
        )

    await callback.answer()


# ---------------------------------------------------------------------------
# انتخاب پلن (فیلتر صریح، فقط سه پلن معتبر)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.in_(PLAN_CALLBACKS))
async def subscription_plan_selected(
    callback: CallbackQuery,
    state: FSMContext,
):
    plan = (callback.data or "").split(":", 1)[1]

    if plan not in PLANS:
        await callback.answer(
            "گزینه اشتراک نامعتبر است.",
            show_alert=True,
        )
        return

    # مرحله اول پرداخت: نمایش قوانین و دکمه «خواندم و قبول می‌کنم»
    if callback.message:
        await callback.message.edit_text(
            TERMS_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=terms_keyboard(plan),
        )

    await callback.answer()


# ---------------------------------------------------------------------------
# کد هدیه
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "subscription:gift_code")
async def subscription_gift_code(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.set_state(MainStates.entering_gift_code)

    if callback.message:
        await callback.message.edit_text(
            "<b>🎁 کد اشتراک هدیه</b>\n\n"
            "اگر کد اشتراک رایگان دارید، "
            "کد را در پیام بعدی ارسال کنید.\n\n"
            "پس از بررسی کد، اشتراک مربوط به آن "
            "برای حساب شما فعال خواهد شد.",
            parse_mode=ParseMode.HTML,
            reply_markup=gift_code_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data == "subscription:back_subscription")
async def subscription_back_subscription(
    callback: CallbackQuery,
    state: FSMContext,
):
    # اگر کاربر در حالت وارد کردن کد بود، از آن حالت خارج شود
    await state.set_state(MainStates.menu)

    if callback.message:
        await callback.message.edit_text(
            "<b>💳 اشتراک</b>\n\n"
            "لطفاً یکی از گزینه‌های اشتراک را انتخاب کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=subscription_keyboard(),
        )

    await callback.answer()


@router.message(MainStates.entering_gift_code)
async def gift_code_message(
    message: Message,
    state: FSMContext,
):
    raw_text = (message.text or "").strip()

    # اگر کاربر به جای کد، دکمه‌ای از منوی اصلی را زد، از حالت وارد کردن کد خارج شود
    if raw_text in MENU_TEXTS:
        await state.set_state(MainStates.menu)
        await main_menu_handler(message, state)
        return

    code = normalize_gift_code(raw_text)

    if not code:
        await message.answer("⚠️ لطفاً کد اشتراک را وارد کنید.")
        return

    data = await state.get_data()
    telegram_id = message.from_user.id if message.from_user else None

    async with AsyncSessionLocal() as session:

        user = await get_user(session, data, telegram_id)

        if user is None:
            await message.answer(
                "⚠️ اطلاعات حساب شما در دسترس نیست.\n"
                "لطفاً دوباره وارد حساب خود شوید."
            )
            return

        # قفل ردیف کد: اگر دو نفر هم‌زمان یک کد را بفرستند،
        # دومی تا پایان تراکنش اول منتظر می‌ماند و سپس کد را مصرف‌شده می‌بیند.
        code_result = await session.execute(
            select(SubscriptionCode)
            .where(
                SubscriptionCode.code == code,
                SubscriptionCode.active.is_(True),
                SubscriptionCode.used.is_(False),
            )
            .with_for_update()
        )

        subscription_code = code_result.scalar_one_or_none()

        if subscription_code is None:
            await message.answer(
                "❌ کد اشتراک نامعتبر است یا قبلاً استفاده شده است."
            )
            return

        # تمدید (افزودن به پایان اشتراک فعلی) یا ساخت اشتراک جدید
        subscription, extended = await apply_subscription_period(
            session,
            user_id=user.id,
            plan_type=subscription_code.type,
            duration_days=subscription_code.duration_days,
        )

        subscription_code.used = True
        subscription_code.used_by_user_id = user.id
        subscription_code.used_at = utcnow()

        await session.commit()

        duration_days = subscription_code.duration_days
        end_date = subscription.end_date
        plan_name = subscription_type_name(subscription.type)
        phone_number = user.phone_number

    remaining_days = max(
        0,
        math.ceil((end_date - utcnow()).total_seconds() / 86400),
    )

    if extended:
        headline = (
            "<b>🎉 کد اشتراک با موفقیت ثبت شد.</b>\n\n"
            f"➕ <b>{duration_days} روز</b> به پایان اشتراک فعلی شما "
            "اضافه شد.\n"
        )
    else:
        headline = (
            "<b>🎉 کد اشتراک با موفقیت ثبت شد.</b>\n\n"
            "اشتراک شما فعال شد.\n"
            f"📅 <b>مدت اشتراک:</b> {duration_days} روز\n"
        )

    await state.set_state(MainStates.menu)

    await message.answer(
        headline
        + f"📌 <b>نوع اشتراک:</b> {plan_name}\n"
        f"📆 <b>تاریخ پایان:</b> {format_date(end_date)}\n"
        f"⏳ <b>مدت باقی‌مانده:</b> {remaining_days} روز",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(phone_number),
    )
