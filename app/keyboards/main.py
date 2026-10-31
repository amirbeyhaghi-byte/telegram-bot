from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils import is_admin


def main_menu_keyboard(
    phone_number: str | None = None,
) -> ReplyKeyboardMarkup:

    keyboard = [
        [
            KeyboardButton(text="🌿 مزاج شناسی"),
        ],
        [
            KeyboardButton(text="🍎 طبع شناسی خوراکی ها"),
        ],
        [
            KeyboardButton(text="👤 حساب کاربری"),
            KeyboardButton(text="💳 اشتراک"),
        ],
    ]

    if is_admin(phone_number):
        keyboard.append(
            [
                KeyboardButton(text="🔐 پنل مدیریت"),
            ]
        )

    keyboard.append(
        [
            KeyboardButton(text="🚪 خروج از حساب"),
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )
