import html
import logging
import math
import secrets
import string

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, func, select

from app.database.database import AsyncSessionLocal
from app.database.models import SubscriptionCode, User
from app.keyboards.admin import (
    CODE_FILTERS,
    admin_codes_keyboard,
    admin_keyboard,
    admin_plan_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.states.main import MainStates
from app.utils import format_date, is_admin

logger = logging.getLogger(__name__)

router = Router()


CODES_PER_PAGE = 5

PLANS = {
    "monthly": {"name": "۱ ماهه", "type": "monthly", "days": 30},
    "six_months": {"name": "۶ ماهه", "type": "six_months", "days": 180},
    "yearly": {"name": "سالیانه", "type": "yearly", "days": 365},
}

TYPE_NAMES = {
    "monthly": "۱ ماهه",
    "six_months": "۶ ماهه",
    "yearly": "سالیانه",
    "free": "رایگان",
}


# =========================================================
# توابع کمکی
# =========================================================

def generate_gift_code() -> str:
    characters = string.ascii_uppercase + string.digits

    parts = [
        "".join(secrets.choice(characters) for _ in range(4))
        for _ in range(3)
    ]

    return "BM-" + "-".join(parts)


def subscription_type_name(subscription_type: str) -> str:
    return TYPE_NAMES.get(subscription_type, subscription_type)


async def require_admin(
    callback: CallbackQuery,
    state: FSMContext,
) -> bool:
    data = await state.get_data()

    if is_admin(data.get("phone_number")):
        return True

    logger.warning(
        "Unauthorized admin action telegram_id=%s data=%s",
        callback.from_user.id if callback.from_user else None,
        callback.data,
    )

    await callback.answer(
        "⛔ دسترسی غیرمجاز",
        show_alert=True,
    )

    return False


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    """edit_text که خطای «message is not modified» را نادیده می‌گیرد."""
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise


def code_filter_condition(filter_key: str):
    if filter_key == "free":
        return and_(
            SubscriptionCode.used.is_(False),
            SubscriptionCode.active.is_(True),
        )

    if filter_key == "used":
        return SubscriptionCode.used.is_(True)

    if filter_key == "off":
        return and_(
            SubscriptionCode.used.is_(False),
            SubscriptionCode.active.is_(False),
        )

    return None


def parse_codes_view(parts: list[str]) -> tuple[str, int]:
    """[filter, page] را معتبرسازی می‌کند."""
    filter_key = parts[0] if parts and parts[0] in CODE_FILTERS else "all"

    try:
        page = max(0, int(parts[1])) if len(parts) > 1 else 0
    except ValueError:
        page = 0

    return filter_key, page


def render_code_block(
    index: int,
    code: SubscriptionCode,
    users_by_id: dict,
) -> str:
    text = (
        f"<b>{index}. <code>{code.code}</code></b>\n"
        f"📌 <b>نوع:</b> {subscription_type_name(code.type)}\n"
        f"⏳ <b>مدت:</b> {code.duration_days} روز\n"
        f"📅 <b>ایجاد:</b> {format_date(code.created_at)}\n"
    )

    if code.used:
        text += "🔴 <b>وضعیت:</b> استفاده شده\n"

        if code.used_at:
            text += (
                f"🕒 <b>تاریخ استفاده:</b> {format_date(code.used_at)}\n"
            )

        user = users_by_id.get(code.used_by_user_id)

        if user:
            full_name = html.escape(
                f"{user.first_name} {user.last_name}"
            )

            text += (
                f"👤 <b>استفاده‌کننده:</b> {full_name}\n"
                f"📱 <b>موبایل:</b> {user.phone_number}\n"
            )

    elif not code.active:
        text += "⚫ <b>وضعیت:</b> غیرفعال\n"

    else:
        text += "🟢 <b>وضعیت:</b> قابل استفاده\n"

    return text


async def show_codes(
    callback: CallbackQuery,
    filter_key: str,
    page: int,
) -> None:
    """لیست صفحه‌بندی‌شده کدها را نمایش می‌دهد (بدون callback.answer)."""
    condition = code_filter_condition(filter_key)

    async with AsyncSessionLocal() as session:
        count_query = select(func.count(SubscriptionCode.id))

        if condition is not None:
            count_query = count_query.where(condition)

        total = (await session.execute(count_query)).scalar_one()

        total_pages = max(1, math.ceil(total / CODES_PER_PAGE))
        page = min(page, total_pages - 1)

        query = (
            select(SubscriptionCode)
            .order_by(
                SubscriptionCode.created_at.desc(),
                SubscriptionCode.id.desc(),
            )
            .limit(CODES_PER_PAGE)
            .offset(page * CODES_PER_PAGE)
        )

        if condition is not None:
            query = query.where(condition)

        codes = (await session.execute(query)).scalars().all()

        user_ids = {
            code.used_by_user_id
            for code in codes
            if code.used_by_user_id is not None
        }

        users_by_id = {}

        if user_ids:
            users = (
                await session.execute(
                    select(User).where(User.id.in_(user_ids))
                )
            ).scalars().all()

            users_by_id = {user.id: user for user in users}

    header = (
        f"<b>📋 کدهای اشتراک — {CODE_FILTERS[filter_key]}</b>\n"
        f"تعداد: {total}\n\n"
    )

    if not codes:
        text = header + "موردی برای نمایش وجود ندارد."
    else:
        start_index = page * CODES_PER_PAGE + 1

        text = header + "\n".join(
            render_code_block(index, code, users_by_id)
            for index, code in enumerate(codes, start=start_index)
        )

    await safe_edit(
        callback,
        text,
        admin_codes_keyboard(
            codes,
            filter_key=filter_key,
            page=page,
            total_pages=total_pages,
        ),
    )


# =========================================================
# پنل مدیریت
# =========================================================

async def show_admin_panel(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    if not is_admin(phone_number):
        await message.answer(
            "⛔ شما دسترسی به پنل مدیریت ندارید."
        )
        return

    await state.set_state(MainStates.admin_menu)

    await message.answer(
        "<b>🔐 پنل مدیریت</b>\n\n"
        "لطفاً عملیات موردنظر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# ساخت کد اشتراک
# =========================================================

@router.callback_query(F.data == "admin:create_code")
async def admin_create_code(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    await safe_edit(
        callback,
        "<b>🎁 ساخت کد اشتراک</b>\n\n"
        "نوع کد را انتخاب کنید:",
        admin_plan_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_plan:"))
async def admin_create_plan(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    plan = (callback.data or "").split(":", 1)[1]

    selected_plan = PLANS.get(plan)

    if selected_plan is None:
        await callback.answer(
            "نوع اشتراک نامعتبر است.",
            show_alert=True,
        )
        return

    code = generate_gift_code()

    async with AsyncSessionLocal() as session:
        session.add(
            SubscriptionCode(
                code=code,
                type=selected_plan["type"],
                duration_days=selected_plan["days"],
                active=True,
                used=False,
            )
        )

        await session.commit()

    logger.info(
        "Gift code created type=%s by telegram_id=%s",
        selected_plan["type"],
        callback.from_user.id if callback.from_user else None,
    )

    await safe_edit(
        callback,
        "<b>🎉 کد اشتراک ساخته شد.</b>\n\n"
        f"📌 <b>نوع:</b> {selected_plan['name']}\n"
        f"⏳ <b>مدت:</b> {selected_plan['days']} روز\n\n"
        "🎁 <b>کد:</b>\n"
        f"<code>{code}</code>\n\n"
        "این کد را می‌توانید در اختیار کاربر موردنظر قرار دهید.",
        admin_keyboard(),
    )

    await callback.answer()


# =========================================================
# نمایش کدهای اشتراک (فیلتر + صفحه‌بندی)
# =========================================================

@router.callback_query(F.data == "admin:list_codes")
async def admin_list_codes(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    await show_codes(callback, "all", 0)

    await callback.answer()


@router.callback_query(F.data.startswith("admin:codes:"))
async def admin_codes_view(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    parts = (callback.data or "").split(":")[2:]

    filter_key, page = parse_codes_view(parts)

    await show_codes(callback, filter_key, page)

    await callback.answer()


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery):
    await callback.answer()


# =========================================================
# غیرفعال کردن کد
# =========================================================

@router.callback_query(F.data.startswith("admin:deactivate_code:"))
async def admin_deactivate_code(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    parts = (callback.data or "").split(":")[2:]

    try:
        code_id = int(parts[0])
    except (ValueError, IndexError):
        await callback.answer(
            "شناسه کد نامعتبر است.",
            show_alert=True,
        )
        return

    filter_key, page = parse_codes_view(parts[1:])

    async with AsyncSessionLocal() as session:

        # قفل ردیف: اگر هم‌زمان کاربری در حال استفاده از کد باشد، تداخل پیش نمی‌آید
        result = await session.execute(
            select(SubscriptionCode)
            .where(SubscriptionCode.id == code_id)
            .with_for_update()
        )

        subscription_code = result.scalar_one_or_none()

        if subscription_code is None:
            await callback.answer(
                "کد اشتراک پیدا نشد.",
                show_alert=True,
            )
            return

        if subscription_code.used:
            await callback.answer(
                "این کد قبلاً استفاده شده است.",
                show_alert=True,
            )
            return

        if not subscription_code.active:
            await callback.answer(
                "این کد قبلاً غیرفعال شده است.",
                show_alert=True,
            )
            return

        subscription_code.active = False

        await session.commit()

    logger.info(
        "Gift code deactivated id=%s by telegram_id=%s",
        code_id,
        callback.from_user.id if callback.from_user else None,
    )

    await show_codes(callback, filter_key, page)

    await callback.answer(
        "کد اشتراک غیرفعال شد.",
        show_alert=True,
    )


# =========================================================
# بازگشت به پنل مدیریت
# =========================================================

@router.callback_query(F.data == "admin:menu")
async def admin_menu(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    await safe_edit(
        callback,
        "<b>🔐 پنل مدیریت</b>\n\n"
        "لطفاً عملیات موردنظر را انتخاب کنید:",
        admin_keyboard(),
    )

    await callback.answer()


# =========================================================
# بازگشت به منوی اصلی
# =========================================================

@router.callback_query(F.data == "admin:back_main")
async def admin_back_main(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await require_admin(callback, state):
        return

    data = await state.get_data()
    phone_number = data.get("phone_number")

    await state.set_state(MainStates.menu)

    if callback.message:
        await callback.message.edit_text(
            "به منوی اصلی بازگشتید."
        )

        await callback.message.answer(
            "لطفاً خدمت موردنظر خود را انتخاب کنید:",
            reply_markup=main_menu_keyboard(phone_number),
        )

    await callback.answer()
