"""منطق پرداخت کارت‌به‌کارت: پلن‌ها، فاکتور و وضعیت تراکنش‌ها."""

import math
import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Payment
from app.services.temperament_service import to_persian_digits

# منبع واحد قیمت پلن‌ها (تومان). مبلغ فاکتور = تومان × ۱۰ (ریال)
PLANS = {
    "monthly": {
        "emoji": "📅",
        "name": "ماهانه",
        "title": "اشتراک ماهانه",
        "days": 30,
        "price_toman": 100_000,
    },
    "six_months": {
        "emoji": "📆",
        "name": "۶ ماهه",
        "title": "اشتراک ۶ ماهه",
        "days": 180,
        "price_toman": 500_000,
    },
    "yearly": {
        "emoji": "🗓",
        "name": "سالیانه",
        "title": "اشتراک سالیانه",
        "days": 365,
        "price_toman": 800_000,
    },
}

STATUS_AWAITING = "awaiting_receipt"
STATUS_PENDING = "pending_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"

STATUS_TEXT = {
    STATUS_AWAITING: "در انتظار ارسال فیش",
    STATUS_PENDING: "⏳ در انتظار بررسی",
    STATUS_APPROVED: "✅ تأیید شد",
    STATUS_REJECTED: "❌ رد شد",
    STATUS_CANCELLED: "لغو شد",
}

PENDING_PAGE_SIZE = 8


# =========================================================
# توابع خالص
# =========================================================

def plan_info(plan_key: str) -> dict | None:
    return PLANS.get(plan_key)


def amount_rial(plan_key: str) -> int:
    return PLANS[plan_key]["price_toman"] * 10


def format_number(value: int) -> str:
    """۱٬۰۰۰٬۰۰۰ (ارقام فارسی با جداکننده هزارگان)."""
    return to_persian_digits(f"{value:,}".replace(",", "٬"))


def card_digits(card_number: str | None) -> str:
    return "".join(ch for ch in (card_number or "") if ch.isdigit())


def payment_config() -> dict | None:
    """
    مشخصات کارت مقصد از فایل .env:
    PAYMENT_CARD_NUMBER, PAYMENT_CARD_BANK, PAYMENT_CARD_OWNER
    اگر ناقص یا نامعتبر باشد None برمی‌گرداند.
    """
    card = card_digits(os.getenv("PAYMENT_CARD_NUMBER"))
    bank = (os.getenv("PAYMENT_CARD_BANK") or "").strip()
    owner = (os.getenv("PAYMENT_CARD_OWNER") or "").strip()

    if len(card) != 16 or not bank or not owner:
        return None

    return {"card": card, "bank": bank, "owner": owner}


def admin_telegram_id() -> int | None:
    try:
        return int((os.getenv("ADMIN_TELEGRAM_ID") or "").strip())
    except ValueError:
        return None


def is_reviewer_telegram(user_id: int | None) -> bool:
    admin_id = admin_telegram_id()

    return admin_id is not None and user_id == admin_id


def total_pages(total: int) -> int:
    return max(1, math.ceil(total / PENDING_PAGE_SIZE))


# =========================================================
# کوئری‌ها
# =========================================================

async def create_invoice(
    session: AsyncSession,
    user_id: int,
    telegram_id: int,
    plan_key: str,
) -> Payment:
    """فاکتور جدید می‌سازد؛ فاکتورهای بدون فیشِ قبلی همین کاربر لغو می‌شوند."""
    result = await session.execute(
        select(Payment).where(
            Payment.user_id == user_id,
            Payment.status == STATUS_AWAITING,
        )
    )

    for old in result.scalars().all():
        old.status = STATUS_CANCELLED

    info = PLANS[plan_key]

    payment = Payment(
        user_id=user_id,
        telegram_id=telegram_id,
        plan_type=plan_key,
        duration_days=info["days"],
        amount_rial=amount_rial(plan_key),
        status=STATUS_AWAITING,
    )

    session.add(payment)

    await session.flush()

    return payment


async def get_payment(
    session: AsyncSession,
    payment_id: int,
    lock: bool = False,
) -> Payment | None:
    query = select(Payment).where(Payment.id == payment_id)

    if lock:
        query = query.with_for_update()

    return (await session.execute(query)).scalar_one_or_none()


async def has_pending_review(
    session: AsyncSession,
    user_id: int,
) -> bool:
    result = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.user_id == user_id,
            Payment.status == STATUS_PENDING,
        )
    )

    return result.scalar_one() > 0


async def count_pending(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.status == STATUS_PENDING
        )
    )

    return result.scalar_one()


async def list_pending_page(
    session: AsyncSession,
    page: int,
) -> list[Payment]:
    result = await session.execute(
        select(Payment)
        .where(Payment.status == STATUS_PENDING)
        .order_by(Payment.receipt_sent_at, Payment.id)
        .limit(PENDING_PAGE_SIZE)
        .offset(page * PENDING_PAGE_SIZE)
    )

    return list(result.scalars().all())
