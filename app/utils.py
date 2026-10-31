import os
from datetime import datetime, timezone

# تاریخ شمسی (اختیاری): pip install jdatetime
try:
    import jdatetime
except ImportError:  # اگر نصب نبود، تاریخ میلادی نمایش داده می‌شود
    jdatetime = None

_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def utcnow() -> datetime:
    """
    جایگزین datetime.utcnow() (منسوخ در پایتون ۳.۱۲).
    خروجی naive و به وقت UTC است تا با ستون‌های DateTime ساده سازگار بماند.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_phone(phone_number: str) -> str:
    """
    همه فرمت‌های رایج شماره ایرانی را به شکل 09xxxxxxxxx تبدیل می‌کند:
    +98912..., 98912..., 0098912..., 912..., ارقام فارسی/عربی.
    """
    phone = (phone_number or "").translate(_DIGITS)
    phone = "".join(
        ch for ch in phone if ch.isdigit() or ch == "+"
    )

    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone

    return phone.replace("+", "")


def is_admin(phone_number: str | None) -> bool:
    admin_phone = os.getenv("ADMIN_PHONE")

    if not admin_phone or not phone_number:
        return False

    return normalize_phone(phone_number) == normalize_phone(admin_phone)


def format_date(value: datetime) -> str:
    """نمایش تاریخ به شمسی (در صورت نصب بودن jdatetime) وگرنه میلادی."""
    if jdatetime is not None:
        return jdatetime.datetime.fromgregorian(
            datetime=value
        ).strftime("%Y/%m/%d")

    return value.strftime("%Y/%m/%d")


def normalize_gift_code(code: str | None) -> str:
    """
    کد هدیه را یکسان‌سازی می‌کند: حذف فاصله، ارقام فارسی به انگلیسی، حروف بزرگ.
    کدها همیشه با حروف بزرگ ساخته می‌شوند.
    """
    code = (code or "").translate(_DIGITS)

    return "".join(code.split()).upper()
