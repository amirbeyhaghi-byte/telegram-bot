from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery


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


async def safe_edit_caption(
    callback: CallbackQuery,
    caption: str,
    reply_markup=None,
) -> None:
    """edit_caption برای پیام‌های عکس/فایل (خطای «not modified» نادیده گرفته می‌شود)."""
    if callback.message is None:
        return

    try:
        await callback.message.edit_caption(
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise
