from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def registration_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 ثبت‌نام")],
            [KeyboardButton(text="🔐 ورود به حساب")],
            [KeyboardButton(text="ℹ️ درباره سامانه")],
        ],
        resize_keyboard=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 ارسال شماره موبایل",
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def login_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 ورود به حساب")],
            [KeyboardButton(text="📝 ثبت‌نام")],
        ],
        resize_keyboard=True,
    )