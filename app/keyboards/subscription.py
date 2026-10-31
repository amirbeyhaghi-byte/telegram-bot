from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.payment_service import PLANS, format_number


def subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    f"{info['emoji']} {info['title']} - "
                    f"{format_number(info['price_toman'])} تومان"
                ),
                callback_data=f"subscription:{key}",
            )
        ]
        for key, info in PLANS.items()
    ]

    buttons.append(
        [
            InlineKeyboardButton(
                text="🎁 کد اشتراک هدیه",
                callback_data="subscription:gift_code",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 بازگشت به منوی اصلی",
                callback_data="subscription:back_main",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gift_code_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به اشتراک",
                    callback_data="subscription:back_subscription",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 بازگشت به منوی اصلی",
                    callback_data="subscription:back_main",
                )
            ],
        ]
    )


def expired_subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 تمدید / خرید اشتراک",
                    callback_data="subscription:open",
                )
            ]
        ]
    )
