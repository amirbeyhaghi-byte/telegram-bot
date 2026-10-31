from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.temperament_service import NUMBER_EMOJIS


def temperament_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ شروع آزمون",
                    callback_data="tq:start",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="tq:menu",
                )
            ],
        ]
    )


def temperament_question_keyboard(
    index: int,
    selected: int | None = None,
) -> InlineKeyboardMarkup:
    answer_row = [
        InlineKeyboardButton(
            text=("✅ " if selected == position else "") + NUMBER_EMOJIS[position],
            callback_data=f"tq:a:{index}:{position}",
        )
        for position in range(4)
    ]

    nav_row = []

    if index > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️ سؤال قبلی",
                callback_data=f"tq:back:{index}",
            )
        )

    if selected is not None:
        nav_row.append(
            InlineKeyboardButton(
                text="سؤال بعدی ▶️",
                callback_data=f"tq:go:{index + 1}",
            )
        )

    buttons = [answer_row]

    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ انصراف و بازگشت به منو",
                callback_data="tq:cancel",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def temperament_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 آزمون جدید",
                    callback_data="tq:start",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به منوی اصلی",
                    callback_data="tq:menu",
                )
            ],
        ]
    )
