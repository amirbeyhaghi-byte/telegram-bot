import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database.database import AsyncSessionLocal
from app.handlers.admin import require_admin, subscription_type_name
from app.handlers.main_menu import MENU_TEXTS, main_menu_handler
from app.keyboards.admin_users import (
    user_confirm_keyboard,
    user_detail_keyboard,
    users_list_keyboard,
    users_menu_keyboard,
    users_search_prompt_keyboard,
    users_search_results_keyboard,
)
from app.services import user_admin_service as users_svc
from app.services.temperament_service import to_persian_digits
from app.states.main import MainStates
from app.telegram_utils import safe_edit
from app.utils import format_date, is_admin, normalize_phone

logger = logging.getLogger(__name__)

router = Router()

USERS_MENU_TEXT = (
    "<b>👥 مدیریت کاربران</b>\n\n"
    "عملیات موردنظر را انتخاب کنید:"
)

SUBSCRIPTION_STATE_TEXT = {
    "active": "🟢 فعال",
    "expired": "🔴 منقضی شده",
}


# =========================================================
# توابع کمکی
# =========================================================

def parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def valid_ctx(ctx: str) -> str:
    """ctx فقط «s» یا «فیلتر.صفحه» معتبر است."""
    if ctx == "s":
        return ctx

    filter_key, _, page = ctx.partition(".")

    if filter_key not in users_svc.USER_FILTERS or parse_int(page) is None:
        return "all.0"

    return f"{filter_key}.{max(0, int(page))}"


def user_detail_text(user, subscriptions) -> str:
    full_name = html.escape(f"{user.first_name} {user.last_name}")

    account = (
        "🟢 فعال"
        if user.status == users_svc.STATUS_ACTIVE
        else "⛔ غیرفعال"
    )

    last_login = (
        format_date(user.last_login_at)
        if user.last_login_at
        else "ثبت نشده"
    )

    text = (
        "<b>👤 اطلاعات کاربر</b>\n\n"
        f"👤 <b>نام:</b> {full_name}\n"
        f"📱 <b>موبایل:</b> {user.phone_number}\n"
        f"📅 <b>ثبت‌نام:</b> {format_date(user.created_at)}\n"
        f"🕒 <b>آخرین ورود:</b> {last_login}\n"
        f"🔐 <b>وضعیت حساب:</b> {account}\n\n"
        "<b>💳 اشتراک</b>\n"
    )

    current = users_svc.current_subscription(subscriptions)

    if current is None:
        return text + "این کاربر هیچ اشتراکی ندارد."

    state = users_svc.subscription_state(current)

    state_text = SUBSCRIPTION_STATE_TEXT.get(state, state)

    text += (
        f"📌 <b>وضعیت:</b> {state_text}\n"
        f"🏷 <b>نوع:</b> {subscription_type_name(current.type)}\n"
        f"📅 <b>شروع:</b> {format_date(current.start_date)}\n"
        f"📆 <b>پایان:</b> {format_date(current.end_date)}\n"
    )

    if state == "active":
        text += (
            "⏳ <b>باقی‌مانده:</b> "
            f"{to_persian_digits(users_svc.remaining_days(current))} روز\n"
        )

    if len(subscriptions) > 1:
        text += "\n<b>🗂 سوابق اشتراک (آخرین‌ها):</b>\n"

        for index, subscription in enumerate(subscriptions, start=1):
            sub_state = users_svc.subscription_state(subscription)

            text += (
                f"{to_persian_digits(index)}. "
                f"{subscription_type_name(subscription.type)} — "
                f"{format_date(subscription.start_date)} تا "
                f"{format_date(subscription.end_date)} — "
                f"{SUBSCRIPTION_STATE_TEXT.get(sub_state, sub_state)}\n"
            )

    return text


async def build_user_detail(user_id: int, ctx: str):
    async with AsyncSessionLocal() as session:
        user, subscriptions = await users_svc.get_user_with_history(
            session,
            user_id,
        )

    if user is None:
        return None

    return user_detail_text(user, subscriptions), user_detail_keyboard(user, ctx)


# =========================================================
# منوی مدیریت کاربران
# =========================================================

@router.callback_query(F.data == "admin:users")
async def users_menu(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    await state.set_state(MainStates.admin_menu)

    await safe_edit(callback, USERS_MENU_TEXT, users_menu_keyboard())

    await callback.answer()


# =========================================================
# لیست کاربران (فیلتر + صفحه‌بندی)
# =========================================================

@router.callback_query(F.data.startswith("admin:ulist:"))
async def users_list(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    parts = (callback.data or "").split(":")

    filter_key = parts[2] if len(parts) > 2 else "all"

    if filter_key not in users_svc.USER_FILTERS:
        filter_key = "all"

    page = parse_int(parts[3] if len(parts) > 3 else 0, 0)

    async with AsyncSessionLocal() as session:
        total = await users_svc.count_users(session, filter_key)

        pages = users_svc.total_pages(total, users_svc.USERS_PAGE_SIZE)
        page = users_svc.clamp_page(page, pages)

        users = (
            await users_svc.list_users_page(session, filter_key, page)
            if total
            else []
        )

    text = (
        f"<b>📋 لیست کاربران — {users_svc.USER_FILTERS[filter_key]}</b>\n"
        f"تعداد: {to_persian_digits(total)}\n\n"
    )

    text += (
        "برای دیدن جزئیات، یک کاربر را انتخاب کنید."
        if users
        else "موردی برای نمایش وجود ندارد."
    )

    await safe_edit(
        callback,
        text,
        users_list_keyboard(users, filter_key, page, pages),
    )

    await callback.answer()


# =========================================================
# جستجو با شماره موبایل
# =========================================================

@router.callback_query(F.data == "admin:usearch")
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    await state.set_state(MainStates.admin_search_user)

    await safe_edit(
        callback,
        "<b>🔎 جستجوی کاربر</b>\n\n"
        "شماره موبایل کامل (مثل 09121234567) یا حداقل "
        f"{to_persian_digits(users_svc.MIN_SEARCH_DIGITS)} رقم از آن را بنویسید.",
        users_search_prompt_keyboard(),
    )

    await callback.answer()


async def search_results_view(query: str):
    async with AsyncSessionLocal() as session:
        users, more = await users_svc.search_users(session, query)

    safe_query = html.escape(query)

    if not users:
        return (
            f"🔎 کاربری برای «{safe_query}» پیدا نشد.\n\n"
            "شماره دیگری بنویسید.",
            users_search_prompt_keyboard(),
            users,
        )

    text = (
        f"<b>🔎 نتایج جستجو برای «{safe_query}»</b>\n"
        f"تعداد: {to_persian_digits(len(users))}"
        + ("+" if more else "")
        + "\n\n"
    )

    if more:
        text += "نتایج زیاد است؛ برای دقت بیشتر رقم‌های بیشتری بنویسید.\n\n"

    text += "یک کاربر را انتخاب کنید، یا شماره دیگری بنویسید."

    return text, users_search_results_keyboard(users), users


@router.message(MainStates.admin_search_user)
async def user_search_message(message: Message, state: FSMContext):
    raw_text = (message.text or "").strip()

    # زدن دکمه‌ای از منوی اصلی → خروج از جستجو
    if raw_text in MENU_TEXTS:
        await state.set_state(MainStates.menu)
        await main_menu_handler(message, state)
        return

    data = await state.get_data()

    # پیام‌های متنی از بررسی ادمین در Middleware رد نمی‌شوند؛ اینجا چک می‌کنیم
    if not is_admin(data.get("phone_number")):
        await state.set_state(MainStates.menu)
        await message.answer("⛔ شما دسترسی به پنل مدیریت ندارید.")
        return

    query = normalize_phone(raw_text)

    if not (
        users_svc.MIN_SEARCH_DIGITS <= len(query) <= users_svc.MAX_SEARCH_DIGITS
        and query.isdigit()
    ):
        await message.answer(
            "⚠️ فقط عدد وارد کنید (حداقل "
            f"{to_persian_digits(users_svc.MIN_SEARCH_DIGITS)} رقم)."
        )
        return

    await state.update_data(admin_user_query=query)

    text, keyboard, users = await search_results_view(query)

    # فقط یک نتیجه: مستقیم صفحه جزئیات
    if len(users) == 1:
        view = await build_user_detail(users[0].id, "s")

        if view is not None:
            await message.answer(view[0], parse_mode="HTML", reply_markup=view[1])
            return

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "admin:uresults")
async def user_search_results(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    data = await state.get_data()
    query = data.get("admin_user_query")

    if not query:
        await safe_edit(callback, USERS_MENU_TEXT, users_menu_keyboard())
        await callback.answer()
        return

    text, keyboard, _ = await search_results_view(query)

    await safe_edit(callback, text, keyboard)

    await callback.answer()


# =========================================================
# جزئیات کاربر
# =========================================================

@router.callback_query(F.data.startswith("admin:u:"))
async def user_detail(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    parts = (callback.data or "").split(":")

    user_id = parse_int(parts[2] if len(parts) > 2 else None)

    if user_id is None:
        await callback.answer("شناسه نامعتبر است.", show_alert=True)
        return

    ctx = valid_ctx(parts[3] if len(parts) > 3 else "all.0")

    view = await build_user_detail(user_id, ctx)

    if view is None:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return

    await safe_edit(callback, view[0], view[1])

    await callback.answer()


# =========================================================
# فعال / غیرفعال کردن حساب (با تأیید)
# =========================================================

def parse_status_callback(data: str):
    """admin:uconf|uset:{id}:{on|off}:{ctx} → (user_id, action, ctx) یا None"""
    parts = data.split(":")

    if len(parts) != 5:
        return None

    user_id = parse_int(parts[2])

    if user_id is None or parts[3] not in {"on", "off"}:
        return None

    return user_id, parts[3], valid_ctx(parts[4])


@router.callback_query(F.data.startswith("admin:uconf:"))
async def user_status_confirm(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    parsed = parse_status_callback(callback.data or "")

    if parsed is None:
        await callback.answer("اطلاعات نامعتبر است.", show_alert=True)
        return

    user_id, action, ctx = parsed

    async with AsyncSessionLocal() as session:
        user, _ = await users_svc.get_user_with_history(session, user_id)

    if user is None:
        await callback.answer("کاربر پیدا نشد.", show_alert=True)
        return

    name = html.escape(f"{user.first_name} {user.last_name}")

    if action == "off":
        text = (
            f"⚠️ آیا از <b>غیرفعال‌کردن</b> حساب «{name}» مطمئن هستید؟\n\n"
            "کاربر بلافاصله از ربات خارج می‌شود و تا زمان فعال‌سازی "
            "مجدد نمی‌تواند وارد شود."
        )
    else:
        text = (
            f"آیا از <b>فعال‌سازی مجدد</b> حساب «{name}» مطمئن هستید؟"
        )

    await safe_edit(
        callback,
        text,
        user_confirm_keyboard(user_id, action, ctx),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin:uset:"))
async def user_status_apply(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    parsed = parse_status_callback(callback.data or "")

    if parsed is None:
        await callback.answer("اطلاعات نامعتبر است.", show_alert=True)
        return

    user_id, action, ctx = parsed

    new_status = (
        users_svc.STATUS_DISABLED
        if action == "off"
        else users_svc.STATUS_ACTIVE
    )

    async with AsyncSessionLocal() as session:
        user, result = await users_svc.set_user_status(
            session,
            user_id,
            new_status,
        )

        if result == "ok":
            await session.commit()

    messages = {
        "not_found": "کاربر پیدا نشد.",
        "admin": "حساب مدیر را نمی‌توان غیرفعال کرد.",
        "unchanged": "وضعیت حساب قبلاً همین‌طور بوده است.",
        "ok": (
            "حساب غیرفعال شد."
            if action == "off"
            else "حساب دوباره فعال شد."
        ),
    }

    if result == "ok":
        logger.info(
            "User status changed id=%s new_status=%s by telegram_id=%s",
            user_id,
            new_status,
            callback.from_user.id if callback.from_user else None,
        )

    view = await build_user_detail(user_id, ctx)

    if view is not None:
        await safe_edit(callback, view[0], view[1])

    await callback.answer(messages[result], show_alert=True)
