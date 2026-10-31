import html
import logging
import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database.database import AsyncSessionLocal
from app.database.models import Payment, User
from app.handlers.main_menu import MENU_TEXTS, main_menu_handler
from app.keyboards.main import main_menu_keyboard
from app.keyboards.payment import (
    invoice_keyboard,
    pending_label,
    pending_list_keyboard,
    receipt_prompt_keyboard,
    review_confirm_keyboard,
    review_keyboard,
)
from app.keyboards.subscription import subscription_keyboard
from app.services import payment_service as pay
from app.services.subscription_service import apply_subscription_period
from app.services.temperament_service import to_persian_digits
from app.services.user_service import get_user_by_phone
from app.states.main import MainStates
from app.telegram_utils import safe_edit, safe_edit_caption
from app.utils import format_date, is_admin, utcnow

logger = logging.getLogger(__name__)

router = Router()

TERMS_TEXT = (
    "⭕️ <b>لطفاً قبل از ادامه، موارد زیر را با دقت مطالعه کنید!</b>\n\n"
    "1. شما موظف به پرداخت دقیق مبلغ درج شده در متن فاکتور هستید! "
    "به هیچ عنوان حتی یک قرون هم تغییر ندهید و رند نکنید!\n\n"
    "2. پس از پرداخت حتماً رسید واریزی را ارسال فرمایید تا به تأیید "
    "مدیر سامانه برسد.\n"
    "3. فرآیند بررسی، تأیید و فعال‌سازی حداکثر 24 ساعت زمان خواهد برد.\n"
    "4. مبلغ فاکتور به شماره کارت اعلام‌شده در مرحله بعد می‌بایست "
    "واریز گردد.\n\n"
    "با مطالعه موارد فوق، مسئولیت رعایت شرایط و احتیاط را می‌پذیرم و "
    "برای ادامه فرآیند پرداخت آماده هستم⬇️"
)

RECEIPT_PROMPT = (
    "💎 لطفاً تصویر فیش واریزی خود را ارسال کنید.\n"
    "⚠️ تصویر باید واضح و خوانا باشد."
)

SUBSCRIPTION_SCREEN_TEXT = (
    "<b>💳 اشتراک</b>\n\n"
    "لطفاً یکی از گزینه‌های اشتراک را انتخاب کنید:"
)


# =========================================================
# توابع کمکی
# =========================================================

def parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def invoice_text(payment, plan_name: str, cfg: dict) -> str:
    return (
        f"🧾 <b>فاکتور شماره {to_persian_digits(payment.id)}</b> — "
        f"اشتراک {html.escape(plan_name)}\n\n"
        "🆘 <b>مهم: مبلغ را دقیق بزنید، رند نکنید</b>\n\n"
        f"💰 <b>مبلغ قابل پرداخت:</b> "
        f"<b>{pay.format_number(payment.amount_rial)} ریال</b>\n\n"
        f"💳 <b>شماره کارت:</b> <code>{cfg['card']}</code>\n"
        f"🏦 <b>بانک:</b> {html.escape(cfg['bank'])}\n"
        f"👤 <b>صاحب حساب:</b> {html.escape(cfg['owner'])}\n\n"
        "❌ <b>واریز پل و پایا ممنوع است!</b>"
    )


def review_caption(payment, user, status_line: str) -> str:
    plan = pay.plan_info(payment.plan_type)
    plan_name = plan["name"] if plan else payment.plan_type

    full_name = html.escape(f"{user.first_name} {user.last_name}")

    sent = (
        format_date(payment.receipt_sent_at)
        if payment.receipt_sent_at
        else "—"
    )

    return (
        f"🧾 <b>فیش واریزی — فاکتور {to_persian_digits(payment.id)}</b>\n\n"
        f"👤 <b>کاربر:</b> {full_name}\n"
        f"📱 <b>موبایل:</b> {user.phone_number}\n"
        f"📦 <b>اشتراک:</b> {html.escape(plan_name)} "
        f"({to_persian_digits(payment.duration_days)} روز)\n"
        f"💰 <b>مبلغ فاکتور:</b> {pay.format_number(payment.amount_rial)} ریال\n"
        f"🕒 <b>ارسال فیش:</b> {sent}\n\n"
        f"📌 <b>وضعیت:</b> {status_line}"
    )


async def current_user(session, state: FSMContext) -> User | None:
    data = await state.get_data()
    phone_number = data.get("phone_number")

    if not phone_number:
        return None

    return await get_user_by_phone(session, phone_number)


def extract_receipt(message: Message):
    """(file_id, kind) فقط برای عکس یا فایل تصویری؛ در غیر این صورت (None, None)."""
    if message.photo:
        return message.photo[-1].file_id, "photo"

    document = message.document

    if document and (document.mime_type or "").startswith("image/"):
        return document.file_id, "document"

    return None, None


async def send_receipt(bot, chat_id: int, payment, caption: str, keyboard):
    if payment.receipt_kind == "document":
        return await bot.send_document(
            chat_id,
            payment.receipt_file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    return await bot.send_photo(
        chat_id,
        payment.receipt_file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def can_review(callback: CallbackQuery, state: FSMContext) -> bool:
    """فقط مدیر: شناسه تلگرام برابر ADMIN_TELEGRAM_ID یا ورود با شماره مدیر."""
    user_id = callback.from_user.id if callback.from_user else None

    if pay.is_reviewer_telegram(user_id):
        return True

    data = await state.get_data()

    if is_admin(data.get("phone_number")):
        return True

    logger.warning(
        "Unauthorized payment review telegram_id=%s data=%s",
        user_id,
        callback.data,
    )

    await callback.answer("⛔ دسترسی غیرمجاز", show_alert=True)

    return False


# =========================================================
# کاربر: پذیرش قوانین → فاکتور
# =========================================================

@router.callback_query(F.data.startswith("pay:accept:"))
async def accept_terms(callback: CallbackQuery, state: FSMContext):
    plan_key = (callback.data or "").split(":")[2]
    plan = pay.plan_info(plan_key)

    if plan is None:
        await callback.answer("گزینه اشتراک نامعتبر است.", show_alert=True)
        return

    cfg = pay.payment_config()

    if cfg is None:
        logger.error(
            "PAYMENT_CARD_NUMBER / PAYMENT_CARD_BANK / PAYMENT_CARD_OWNER "
            "در فایل .env تنظیم نشده یا نامعتبر است."
        )

        await callback.answer(
            "⚠️ پرداخت موقتاً در دسترس نیست. لطفاً بعداً تلاش کنید.",
            show_alert=True,
        )
        return

    async with AsyncSessionLocal() as session:
        user = await current_user(session, state)

        if user is None:
            await callback.answer(
                "اطلاعات حساب شما در دسترس نیست. لطفاً دوباره وارد شوید.",
                show_alert=True,
            )
            return

        if await pay.has_pending_review(session, user.id):
            await safe_edit(
                callback,
                "⏳ <b>فیش واریزی قبلی شما در حال بررسی است.</b>\n\n"
                "تا مشخص شدن نتیجه (حداکثر 24 ساعت) امکان صدور فاکتور "
                "جدید نیست.",
                subscription_keyboard(),
            )
            await callback.answer()
            return

        payment = await pay.create_invoice(
            session,
            user.id,
            callback.from_user.id,
            plan_key,
        )

        await session.commit()

        text = invoice_text(payment, plan["name"], cfg)
        keyboard = invoice_keyboard(
            payment.id,
            cfg["card"],
            payment.amount_rial,
        )

    await safe_edit(callback, text, keyboard)

    await callback.answer()


# =========================================================
# کاربر: درخواست فیش
# =========================================================

@router.callback_query(F.data.startswith("pay:send:"))
async def ask_receipt(callback: CallbackQuery, state: FSMContext):
    payment_id = parse_int((callback.data or "").split(":")[2])

    async with AsyncSessionLocal() as session:
        user = await current_user(session, state)
        payment = (
            await pay.get_payment(session, payment_id)
            if payment_id is not None
            else None
        )

    if (
        user is None
        or payment is None
        or payment.user_id != user.id
        or payment.status != pay.STATUS_AWAITING
    ):
        await callback.answer(
            "این فاکتور دیگر معتبر نیست. لطفاً فاکتور جدید بسازید.",
            show_alert=True,
        )
        return

    await state.set_state(MainStates.sending_receipt)
    await state.update_data(pay_id=payment.id)

    if callback.message:
        await callback.message.answer(
            RECEIPT_PROMPT,
            reply_markup=receipt_prompt_keyboard(payment.id),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("pay:cancel:"))
async def cancel_invoice(callback: CallbackQuery, state: FSMContext):
    payment_id = parse_int((callback.data or "").split(":")[2])

    async with AsyncSessionLocal() as session:
        user = await current_user(session, state)

        payment = (
            await pay.get_payment(session, payment_id, lock=True)
            if payment_id is not None
            else None
        )

        if (
            user is not None
            and payment is not None
            and payment.user_id == user.id
            and payment.status == pay.STATUS_AWAITING
        ):
            payment.status = pay.STATUS_CANCELLED
            await session.commit()

    await state.set_state(MainStates.menu)
    await state.update_data(pay_id=None)

    await safe_edit(
        callback,
        "❌ فاکتور لغو شد.\n\n" + SUBSCRIPTION_SCREEN_TEXT,
        subscription_keyboard(),
    )

    await callback.answer()


# =========================================================
# کاربر: دریافت تصویر فیش
# =========================================================

@router.message(MainStates.sending_receipt)
async def receive_receipt(message: Message, state: FSMContext):
    raw_text = (message.text or "").strip()

    # زدن دکمه منوی اصلی → خروج از مرحله ارسال فیش (فاکتور باز می‌ماند)
    if raw_text in MENU_TEXTS:
        await state.set_state(MainStates.menu)
        await main_menu_handler(message, state)
        return

    file_id, kind = extract_receipt(message)

    if file_id is None:
        await message.answer(
            "⚠️ لطفاً فقط تصویر فیش واریزی را ارسال کنید.\n"
            "تصویر باید واضح و خوانا باشد."
        )
        return

    data = await state.get_data()
    payment_id = data.get("pay_id")

    async with AsyncSessionLocal() as session:
        user = await current_user(session, state)

        payment = (
            await pay.get_payment(session, payment_id, lock=True)
            if payment_id is not None
            else None
        )

        if (
            user is None
            or payment is None
            or payment.user_id != user.id
            or payment.status != pay.STATUS_AWAITING
        ):
            await state.set_state(MainStates.menu)

            await message.answer(
                "این فاکتور دیگر معتبر نیست. لطفاً از بخش «💳 اشتراک» "
                "فاکتور جدید بسازید.",
                reply_markup=main_menu_keyboard(
                    data.get("phone_number")
                ),
            )
            return

        payment.receipt_file_id = file_id
        payment.receipt_kind = kind
        payment.receipt_sent_at = utcnow()
        payment.status = pay.STATUS_PENDING

        await session.commit()

        caption = review_caption(
            payment,
            user,
            pay.STATUS_TEXT[pay.STATUS_PENDING],
        )

        snapshot = ReceiptSnapshot(payment)
        phone_number = user.phone_number

    await state.set_state(MainStates.menu)
    await state.update_data(pay_id=None)

    await message.answer(
        "✅ <b>فیش واریزی شما دریافت شد.</b>\n\n"
        "پس از بررسی و تأیید مدیر، اشتراک شما فعال می‌شود "
        "(حداکثر تا 24 ساعت) و نتیجه به شما اطلاع داده خواهد شد.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(phone_number),
    )

    await notify_admin(message.bot, snapshot, caption)


class ReceiptSnapshot:
    """نمای ساده از Payment برای استفاده بعد از بسته شدن session."""

    def __init__(self, payment: Payment):
        self.id = payment.id
        self.receipt_file_id = payment.receipt_file_id
        self.receipt_kind = payment.receipt_kind


async def notify_admin(bot, snapshot, caption: str) -> bool:
    """فیش و فاکتور را برای مدیر می‌فرستد؛ در صورت خطا فقط لاگ می‌شود
    (فیش در «پرداخت‌های در انتظار» پنل مدیریت هم دیده می‌شود)."""
    admin_id = pay.admin_telegram_id()

    if admin_id is None:
        logger.warning(
            "ADMIN_TELEGRAM_ID تنظیم نشده؛ فیش فاکتور %s فقط در پنل مدیریت دیده می‌شود.",
            snapshot.id,
        )
        return False

    try:
        await send_receipt(
            bot,
            admin_id,
            snapshot,
            caption,
            review_keyboard(snapshot.id),
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception(
            "ارسال فیش فاکتور %s برای مدیر ناموفق بود.",
            snapshot.id,
        )
        return False


# =========================================================
# مدیر: بررسی فیش (تأیید / رد با مرحله تأیید نهایی)
# =========================================================

async def load_review(payment_id: int):
    async with AsyncSessionLocal() as session:
        payment = await pay.get_payment(session, payment_id)

        if payment is None:
            return None, None

        user = await session.get(User, payment.user_id)

    return payment, user


@router.callback_query(F.data.regexp(r"^pay:(ok|no):\d+$"))
async def review_ask_confirm(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    _, action, raw_id = (callback.data or "").split(":")

    payment, user = await load_review(int(raw_id))

    if payment is None:
        await callback.answer("فاکتور پیدا نشد.", show_alert=True)
        return

    if payment.status != pay.STATUS_PENDING:
        await callback.answer(
            f"وضعیت این فاکتور «{pay.STATUS_TEXT.get(payment.status, payment.status)}» است.",
            show_alert=True,
        )
        return

    question = (
        "⚠️ <b>تأیید نهایی:</b> اشتراک کاربر فعال شود؟"
        if action == "ok"
        else "⚠️ <b>تأیید نهایی:</b> این فیش رد شود؟"
    )

    await safe_edit_caption(
        callback,
        review_caption(payment, user, pay.STATUS_TEXT[pay.STATUS_PENDING])
        + "\n\n"
        + question,
        review_confirm_keyboard(payment.id, "okc" if action == "ok" else "noc"),
    )

    await callback.answer()


@router.callback_query(F.data.regexp(r"^pay:rv:\d+$"))
async def review_back(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    payment, user = await load_review(int((callback.data or "").split(":")[2]))

    if payment is None:
        await callback.answer("فاکتور پیدا نشد.", show_alert=True)
        return

    await safe_edit_caption(
        callback,
        review_caption(payment, user, pay.STATUS_TEXT.get(payment.status, payment.status)),
        review_keyboard(payment.id) if payment.status == pay.STATUS_PENDING else None,
    )

    await callback.answer()


@router.callback_query(F.data.regexp(r"^pay:okc:\d+$"))
async def review_approve(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    payment_id = int((callback.data or "").split(":")[2])

    async with AsyncSessionLocal() as session:
        payment = await pay.get_payment(session, payment_id, lock=True)

        if payment is None:
            await callback.answer("فاکتور پیدا نشد.", show_alert=True)
            return

        # جلوگیری از تأیید مجدد (فعال‌سازی دوباره اشتراک)
        if payment.status != pay.STATUS_PENDING:
            status_text = pay.STATUS_TEXT.get(payment.status, payment.status)
            await callback.answer(
                f"این فاکتور قبلاً بررسی شده است ({status_text}).",
                show_alert=True,
            )
            return

        user = await session.get(User, payment.user_id)

        subscription, extended = await apply_subscription_period(
            session,
            user_id=payment.user_id,
            plan_type=payment.plan_type,
            duration_days=payment.duration_days,
        )

        subscription.payment_id = payment.id

        payment.status = pay.STATUS_APPROVED
        payment.reviewed_at = utcnow()
        payment.reviewed_by = callback.from_user.id
        payment.subscription_id = subscription.id

        await session.commit()

        end_date = subscription.end_date
        telegram_id = payment.telegram_id
        phone_number = user.phone_number
        caption = review_caption(
            payment,
            user,
            pay.STATUS_TEXT[pay.STATUS_APPROVED]
            + f" — اشتراک تا {format_date(end_date)} فعال شد",
        )

    logger.info(
        "Payment approved id=%s by telegram_id=%s",
        payment_id,
        callback.from_user.id,
    )

    await safe_edit_caption(callback, caption, None)

    await callback.answer("اشتراک کاربر فعال شد.", show_alert=True)

    await notify_user(
        callback.bot,
        telegram_id,
        "🎉 <b>پرداخت شما تأیید و اشتراک فعال شد.</b>\n\n"
        f"📆 <b>تاریخ پایان:</b> {format_date(end_date)}\n"
        f"⏳ <b>مدت باقی‌مانده:</b> "
        f"{to_persian_digits(max(0, math.ceil((end_date - utcnow()).total_seconds() / 86400)))} روز",
        main_menu_keyboard(phone_number),
    )


@router.callback_query(F.data.regexp(r"^pay:noc:\d+$"))
async def review_reject(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    payment_id = int((callback.data or "").split(":")[2])

    async with AsyncSessionLocal() as session:
        payment = await pay.get_payment(session, payment_id, lock=True)

        if payment is None:
            await callback.answer("فاکتور پیدا نشد.", show_alert=True)
            return

        if payment.status != pay.STATUS_PENDING:
            status_text = pay.STATUS_TEXT.get(payment.status, payment.status)
            await callback.answer(
                f"این فاکتور قبلاً بررسی شده است ({status_text}).",
                show_alert=True,
            )
            return

        user = await session.get(User, payment.user_id)

        payment.status = pay.STATUS_REJECTED
        payment.reviewed_at = utcnow()
        payment.reviewed_by = callback.from_user.id

        await session.commit()

        telegram_id = payment.telegram_id
        phone_number = user.phone_number
        caption = review_caption(payment, user, pay.STATUS_TEXT[pay.STATUS_REJECTED])

    logger.info(
        "Payment rejected id=%s by telegram_id=%s",
        payment_id,
        callback.from_user.id,
    )

    await safe_edit_caption(callback, caption, None)

    await callback.answer("فیش رد شد.", show_alert=True)

    await notify_user(
        callback.bot,
        telegram_id,
        "❌ <b>فیش واریزی شما تأیید نشد.</b>\n\n"
        "اگر مبلغ را واریز کرده‌اید، لطفاً با مدیر سامانه تماس بگیرید "
        "یا از بخش «💳 اشتراک» فاکتور جدید بسازید و فیش واضح‌تری ارسال کنید.",
        main_menu_keyboard(phone_number),
    )


async def notify_user(bot, telegram_id: int, text: str, keyboard) -> None:
    try:
        await bot.send_message(
            telegram_id,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:  # noqa: BLE001
        logger.exception("اطلاع‌رسانی به کاربر %s ناموفق بود.", telegram_id)


# =========================================================
# مدیر: لیست پرداخت‌های در انتظار (پشتیبان اگر پیام فیش گم شد)
# =========================================================

@router.callback_query(F.data.startswith("admin:pays:"))
async def pending_payments(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    page = parse_int((callback.data or "").split(":")[2], 0)

    async with AsyncSessionLocal() as session:
        total = await pay.count_pending(session)

        pages = pay.total_pages(total)
        page = min(max(page, 0), pages - 1)

        payments = (
            await pay.list_pending_page(session, page) if total else []
        )

        rows = []

        for payment in payments:
            user = await session.get(User, payment.user_id)
            plan = pay.plan_info(payment.plan_type)

            rows.append(
                (
                    payment.id,
                    pending_label(
                        payment.id,
                        f"{user.first_name} {user.last_name}",
                        plan["name"] if plan else payment.plan_type,
                        payment.amount_rial,
                    ),
                )
            )

    text = (
        "<b>💰 پرداخت‌های در انتظار بررسی</b>\n"
        f"تعداد: {to_persian_digits(total)}\n\n"
        + (
            "برای دیدن فیش و تصمیم‌گیری، یکی را انتخاب کنید."
            if rows
            else "فیشی در انتظار بررسی نیست."
        )
    )

    await safe_edit(callback, text, pending_list_keyboard(rows, page, pages))

    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:pay:\d+$"))
async def open_pending_payment(callback: CallbackQuery, state: FSMContext):
    if not await can_review(callback, state):
        return

    payment_id = int((callback.data or "").split(":")[2])

    payment, user = await load_review(payment_id)

    if payment is None or payment.status != pay.STATUS_PENDING:
        await callback.answer(
            "این فیش دیگر در انتظار بررسی نیست.",
            show_alert=True,
        )
        return

    if callback.message:
        await send_receipt(
            callback.bot,
            callback.message.chat.id,
            payment,
            review_caption(payment, user, pay.STATUS_TEXT[pay.STATUS_PENDING]),
            review_keyboard(payment.id),
        )

    await callback.answer()
