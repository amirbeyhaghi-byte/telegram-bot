from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, User
from app.utils import normalize_phone, utcnow

FREE_TRIAL_DAYS = 30

# ترتیب ارزش اشتراک‌ها؛ برای جلوگیری از تنزل نوع اشتراک هنگام تمدید
SUBSCRIPTION_RANK = {
    "free": 0,
    "monthly": 1,
    "six_months": 2,
    "yearly": 3,
}


def higher_type(first: str, second: str) -> str:
    """نوع اشتراکی را برمی‌گرداند که رتبه‌ی بالاتری دارد."""
    if SUBSCRIPTION_RANK.get(second, 0) >= SUBSCRIPTION_RANK.get(first, 0):
        return second

    return first


async def create_free_subscription(
    session: AsyncSession,
    user_id: int,
    days: int = FREE_TRIAL_DAYS,
) -> Subscription:
    """
    اشتراک رایگان اولیه را می‌سازد.
    commit را فراخوان انجام می‌دهد (همراه با ساخت کاربر در یک تراکنش).
    """
    now = utcnow()

    subscription = Subscription(
        user_id=user_id,
        type="free",
        start_date=now,
        end_date=now + timedelta(days=days),
        status="active",
    )

    session.add(subscription)

    await session.flush()

    return subscription


async def get_active_subscription(
    phone_number: str,
) -> Subscription | None:
    """
    اشتراک فعال کاربر را برمی‌گرداند (دوره رایگان هم دقیقاً مثل اشتراک عادی است).
    """
    phone = normalize_phone(phone_number)

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.phone_number == phone)
        )

        user = user_result.scalar_one_or_none()

        if user is None:
            return None

        subscription_result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.end_date > utcnow(),
            )
            .order_by(Subscription.end_date.desc())
            .limit(1)
        )

        return subscription_result.scalars().first()


async def has_active_subscription(
    phone_number: str,
) -> bool:
    subscription = await get_active_subscription(phone_number)

    return subscription is not None


async def apply_subscription_period(
    session: AsyncSession,
    user_id: int,
    plan_type: str,
    duration_days: int,
) -> tuple[Subscription, bool]:
    """
    منطق واحد تمدید/فعال‌سازی اشتراک (کد هدیه، پرداخت و ...).

    - اگر کاربر اشتراک فعال دارد: مدت جدید به «پایان اشتراک فعلی» اضافه می‌شود
      (اشتراک قبلی از بین نمی‌رود) و نوع اشتراک هرگز تنزل پیدا نمی‌کند.
    - اگر اشتراک فعالی ندارد: اشتراک جدید از همین لحظه ساخته می‌شود.

    ردیف کاربر قفل می‌شود تا دو درخواست هم‌زمان یک کاربر
    (مثلاً دو کد با هم) تداخل نکنند.
    commit را فراخوان انجام می‌دهد.

    خروجی: (اشتراک، آیا_تمدید_شد)
    """
    await session.execute(
        select(User.id)
        .where(User.id == user_id)
        .with_for_update()
    )

    now = utcnow()
    duration = timedelta(days=duration_days)

    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.end_date > now,
        )
        .order_by(Subscription.end_date.desc())
        .limit(1)
        .with_for_update()
    )

    current = result.scalars().first()

    if current is not None:
        current.end_date = current.end_date + duration
        current.type = higher_type(current.type, plan_type)

        return current, True

    subscription = Subscription(
        user_id=user_id,
        type=plan_type,
        start_date=now,
        end_date=now + duration,
        status="active",
    )

    session.add(subscription)

    await session.flush()

    return subscription, False


ACCESS_OK = "ok"
ACCESS_LOGIN_REQUIRED = "login_required"
ACCESS_EXPIRED = "expired"


async def get_access_status(
    phone_number: str | None,
) -> str:
    """
    وضعیت دسترسی کاربر به خدمات اشتراکی:
    ACCESS_OK / ACCESS_LOGIN_REQUIRED / ACCESS_EXPIRED
    (دوره رایگان و اشتراک پولی هیچ تفاوتی ندارند).
    """
    if not phone_number:
        return ACCESS_LOGIN_REQUIRED

    if await has_active_subscription(phone_number):
        return ACCESS_OK

    return ACCESS_EXPIRED


def expired_message(service_title: str | None = None) -> str:
    target = (
        f"خدمت «{service_title}»"
        if service_title
        else "خدمات سامانه"
    )

    return (
        "🔴 <b>اشتراک شما منقضی شده است.</b>\n\n"
        f"برای استفاده از {target} "
        "لطفاً اشتراک خود را تمدید کنید.\n\n"
        "برای تمدید یا خرید اشتراک، دکمه زیر را بزنید."
    )
