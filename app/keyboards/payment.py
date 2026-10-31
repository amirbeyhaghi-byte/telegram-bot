from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app.services.payment_service import (
    format_number,
)
from app.services.temperament_service import to_persian_digits


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def terms_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("✅ خواندم و قبول می‌کنم", f"pay:accept:{plan_key}")],
            [_button("🔙 بازگشت", "subscription:back_subscription")],
        ]
    )


def invoice_keyboard(
    payment_id: int,
    card_number: str,
    amount_rial: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="کپی شماره کارت",
                    copy_text=CopyTextButton(text=card_number),
                ),
                InlineKeyboardButton(
                    text="کپی مبلغ ریال",
                    copy_text=CopyTextButton(text=str(amount_rial)),
                ),
            ],
            [_button("👀 ارسال فیش واریزی", f"pay:send:{payment_id}")],
            [_button("❌ انصراف", f"pay:cancel:{payment_id}")],
        ]
    )


def receipt_prompt_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("❌ انصراف", f"pay:cancel:{payment_id}")]
        ]
    )


def review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("✅ تأیید و فعال‌سازی", f"pay:ok:{payment_id}"),
                _button("❌ رد", f"pay:no:{payment_id}"),
            ]
        ]
    )


def review_confirm_keyboard(
    payment_id: int,
    action: str,
) -> InlineKeyboardMarkup:
    """action: okc (تأیید نهایی) یا noc (رد نهایی)."""
    label = "✅ بله، اشتراک فعال شود" if action == "okc" else "❌ بله، رد شود"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button(label, f"pay:{action}:{payment_id}"),
                _button("↩️ انصراف", f"pay:rv:{payment_id}"),
            ]
        ]
    )


def pending_list_keyboard(
    rows,
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    """rows: لیست (payment_id, برچسب دکمه)"""
    buttons = [[_button(label, f"admin:pay:{pid}")] for pid, label in rows]

    if pages > 1:
        nav = []

        if page > 0:
            nav.append(_button("◀️ قبلی", f"admin:pays:{page - 1}"))

        nav.append(
            _button(
                f"{to_persian_digits(page + 1)} / {to_persian_digits(pages)}",
                "admin:noop",
            )
        )

        if page < pages - 1:
            nav.append(_button("بعدی ▶️", f"admin:pays:{page + 1}"))

        buttons.append(nav)

    buttons.append([_button("🔄 بروزرسانی", f"admin:pays:{page}")])
    buttons.append([_button("🔙 بازگشت به پنل مدیریت", "admin:menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pending_label(payment_id: int, name: str, plan_name: str, amount: int) -> str:
    return (
        f"#{to_persian_digits(payment_id)} — {name[:20]} — "
        f"{plan_name} — {format_number(amount)}"
    )
