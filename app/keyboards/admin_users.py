from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.temperament_service import to_persian_digits
from app.services.user_admin_service import STATUS_ACTIVE, USER_FILTERS


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def user_label(user) -> str:
    icon = "🟢" if user.status == STATUS_ACTIVE else "⛔"
    name = f"{user.first_name} {user.last_name}".strip()[:30]

    return f"{icon} {name} — {user.phone_number}"


def users_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("📋 لیست کاربران", "admin:ulist:all:0")],
            [_button("🔎 جستجو با شماره موبایل", "admin:usearch")],
            [_button("🔙 بازگشت به پنل مدیریت", "admin:menu")],
        ]
    )


def users_list_keyboard(
    users,
    filter_key: str,
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            _button(
                ("✅ " if key == filter_key else "") + title,
                f"admin:ulist:{key}:0",
            )
            for key, title in USER_FILTERS.items()
        ]
    ]

    for user in users:
        buttons.append(
            [_button(user_label(user), f"admin:u:{user.id}:{filter_key}.{page}")]
        )

    if pages > 1:
        nav = []

        if page > 0:
            nav.append(_button("◀️ قبلی", f"admin:ulist:{filter_key}:{page - 1}"))

        nav.append(
            _button(
                f"{to_persian_digits(page + 1)} / {to_persian_digits(pages)}",
                "admin:noop",
            )
        )

        if page < pages - 1:
            nav.append(_button("بعدی ▶️", f"admin:ulist:{filter_key}:{page + 1}"))

        buttons.append(nav)

    buttons.append([_button("🔙 مدیریت کاربران", "admin:users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def users_search_results_keyboard(users) -> InlineKeyboardMarkup:
    buttons = [
        [_button(user_label(user), f"admin:u:{user.id}:s")] for user in users
    ]

    buttons.append([_button("🔙 مدیریت کاربران", "admin:users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def users_search_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button("🔙 مدیریت کاربران", "admin:users")]]
    )


def user_back_callback(ctx: str) -> str:
    """ctx: «s» (نتایج جستجو) یا «فیلتر.صفحه» (لیست)."""
    if ctx == "s":
        return "admin:uresults"

    filter_key, _, page = ctx.partition(".")

    return f"admin:ulist:{filter_key}:{page or 0}"


def user_detail_keyboard(user, ctx: str) -> InlineKeyboardMarkup:
    if user.status == STATUS_ACTIVE:
        toggle = _button(
            "⛔ غیرفعال کردن حساب",
            f"admin:uconf:{user.id}:off:{ctx}",
        )
    else:
        toggle = _button(
            "✅ فعال کردن حساب",
            f"admin:uconf:{user.id}:on:{ctx}",
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle],
            [_button("🔄 بروزرسانی", f"admin:u:{user.id}:{ctx}")],
            [_button("🔙 بازگشت", user_back_callback(ctx))],
        ]
    )


def user_confirm_keyboard(user_id: int, action: str, ctx: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("✅ بله، انجام شود", f"admin:uset:{user_id}:{action}:{ctx}"),
                _button("❌ انصراف", f"admin:u:{user_id}:{ctx}"),
            ]
        ]
    )
