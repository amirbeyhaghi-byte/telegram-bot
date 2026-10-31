from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def account_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="account_back_main",
                )
            ]
        ]
    )