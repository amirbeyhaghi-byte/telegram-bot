"""منطق مدیریت کاربران برای پنل ادمین + بررسی وضعیت حساب."""

import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, User
from app.utils import is_admin, normalize_phone, utcnow

STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"

USERS_PAGE_SIZE = 8
SEARCH_LIMIT = 8
MIN_SEARCH_DIGITS = 4
MAX_SEARCH_DIGITS = 15
HISTORY_LIMIT = 5

USER_FILTERS = {
    "all": "همه",
    "active": "فعال",
    "disabled": "غیرفعال",
}


# =========================================================
# توابع خالص
# =========================================================

def subscription_state(
    subscription: Subscription,
    now=None,
) -> str:
    """active / expired / یا هر status دیگر ثبت‌شده (مثلاً cancelled)."""
    now = now or utcnow()

    if subscription.status != "active":
        return subscription.status

    return "active" if subscription.end_date > now else "expired"


def remaining_days(subscription: Subscription, now=None) -> int:
    now = now or utcnow()

    seconds = (subscription.end_date - now).total_seconds()

    return max(0, math.ceil(seconds / 86400))


def current_subscription(subscriptions: list[Subscription]):
    """اشتراک فعال فعلی؛ اگر نبود، آخرین اشتراک؛ اگر هیچ نبود None."""
    for subscription in subscriptions:
        if subscription_state(subscription) == "active":
            return subscription

    return subscriptions[0] if subscriptions else None


def total_pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))


def clamp_page(page: int, pages: int) -> int:
    return min(max(page, 0), pages - 1)


def user_filter_condition(filter_key: str):
    if filter_key == "active":
        return User.status == STATUS_ACTIVE

    if filter_key == "disabled":
        return User.status != STATUS_ACTIVE

    return None


# =========================================================
# کوئری‌ها
# =========================================================

async def count_users(session: AsyncSession, filter_key: str) -> int:
    query = select(func.count(User.id))

    condition = user_filter_condition(filter_key)

    if condition is not None:
        query = query.where(condition)

    return (await session.execute(query)).scalar_one()


async def list_users_page(
    session: AsyncSession,
    filter_key: str,
    page: int,
) -> list[User]:
    query = (
        select(User)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(USERS_PAGE_SIZE)
        .offset(page * USERS_PAGE_SIZE)
    )

    condition = user_filter_condition(filter_key)

    if condition is not None:
        query = query.where(condition)

    return list((await session.execute(query)).scalars().all())


async def search_users(
    session: AsyncSession,
    text: str,
) -> tuple[list[User], bool]:
    """
    جستجو با شماره موبایل: شماره کامل (دقیق) یا بخشی از شماره (حداقل ۴ رقم).
    خروجی: (کاربران، آیا نتایج بیشتری وجود دارد)
    """
    phone = normalize_phone(text)

    if len(phone) >= 10:
        query = select(User).where(User.phone_number == phone)
    else:
        query = (
            select(User)
            .where(User.phone_number.like(f"%{phone}%"))
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(SEARCH_LIMIT + 1)
        )

    users = list((await session.execute(query)).scalars().all())

    return users[:SEARCH_LIMIT], len(users) > SEARCH_LIMIT


async def get_user_with_history(
    session: AsyncSession,
    user_id: int,
) -> tuple[User | None, list[Subscription]]:
    user = await session.get(User, user_id)

    if user is None:
        return None, []

    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.end_date.desc())
        .limit(HISTORY_LIMIT)
    )

    return user, list(result.scalars().all())


async def set_user_status(
    session: AsyncSession,
    user_id: int,
    new_status: str,
) -> tuple[User | None, str]:
    """
    وضعیت حساب را تغییر می‌دهد (commit با فراخوان).
    نتیجه: ok / unchanged / not_found / admin
    """
    result = await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )

    user = result.scalar_one_or_none()

    if user is None:
        return None, "not_found"

    # حساب مدیر هرگز غیرفعال نمی‌شود (جلوگیری از قفل‌شدن خود ادمین)
    if new_status != STATUS_ACTIVE and is_admin(user.phone_number):
        return user, "admin"

    if user.status == new_status:
        return user, "unchanged"

    user.status = new_status

    return user, "ok"


async def get_account_status(phone_number: str) -> str:
    """active / disabled / missing — برای Middleware."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.status).where(
                User.phone_number == normalize_phone(phone_number)
            )
        )

        status = result.scalar_one_or_none()

    if status is None:
        return "missing"

    return STATUS_ACTIVE if status == STATUS_ACTIVE else STATUS_DISABLED
