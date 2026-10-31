from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 ساخت کد اشتراک",
                    callback_data="admin:create_code",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 کدهای اشتراک",
                    callback_data="admin:list_codes",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 مدیریت کاربران",
                    callback_data="admin:users",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 پرداخت‌های در انتظار",
                    callback_data="admin:pays:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="admin:back_main",
                )
            ],
        ]
    )


def admin_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 کد ۱ ماهه",
                    callback_data="admin_plan:monthly",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📆 کد ۶ ماهه",
                    callback_data="admin_plan:six_months",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗓 کد سالیانه",
                    callback_data="admin_plan:yearly",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="admin:menu",
                )
            ],
        ]
    )


CODE_FILTERS = {
    "all": "همه",
    "free": "قابل استفاده",
    "used": "استفاده‌شده",
    "off": "غیرفعال",
}


def admin_codes_keyboard(
    codes,
    filter_key: str = "all",
    page: int = 0,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    buttons = []

    # دکمه‌های فیلتر (فیلتر فعلی با ✅ مشخص می‌شود)
    filter_buttons = [
        InlineKeyboardButton(
            text=("✅ " if key == filter_key else "") + title,
            callback_data=f"admin:codes:{key}:0",
        )
        for key, title in CODE_FILTERS.items()
    ]

    buttons.append(filter_buttons[:2])
    buttons.append(filter_buttons[2:])

    # دکمه غیرفعال‌سازی فقط برای کدهای قابل استفاده همین صفحه
    for code in codes:
        if not code.used and code.active:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"❌ غیرفعال کردن {code.code}",
                        callback_data=(
                            f"admin:deactivate_code:"
                            f"{code.id}:{filter_key}:{page}"
                        ),
                    )
                ]
            )

    # صفحه‌بندی
    if total_pages > 1:
        nav = []

        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️ قبلی",
                    callback_data=f"admin:codes:{filter_key}:{page - 1}",
                )
            )

        nav.append(
            InlineKeyboardButton(
                text=f"{page + 1} / {total_pages}",
                callback_data="admin:noop",
            )
        )

        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="بعدی ▶️",
                    callback_data=f"admin:codes:{filter_key}:{page + 1}",
                )
            )

        buttons.append(nav)

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 بروزرسانی",
                callback_data=f"admin:codes:{filter_key}:{page}",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 بازگشت به پنل مدیریت",
                callback_data="admin:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
