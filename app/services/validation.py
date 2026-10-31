"""اعتبارسنجی ورودی‌های کاربر (نام، رمز عبور، شماره موبایل)."""

import re

from app.utils import normalize_phone

# حروف فارسی/عربی (بدون ارقام و علائم نگارشی) + حروف لاتین
_LETTERS = (
    "A-Za-z"
    "\u0621-\u063A\u0641-\u064A"
    "\u067E\u0686\u0698\u06AF\u06A9\u06CC\u06C0"
)

_NAME_RE = re.compile(rf"^[{_LETTERS}][{_LETTERS}\u200c '\-]*$")

_CHAR_MAP = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})

NAME_MIN = 2
NAME_MAX = 40
PASSWORD_MIN = 6
PASSWORD_MAX = 128

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(number: int) -> str:
    return str(number).translate(_FA)


def validate_name(text: str | None) -> tuple[str | None, str | None]:
    """خروجی: (نام تمیزشده، پیام خطا). فقط یکی از دو مقدار None نیست."""
    name = " ".join((text or "").translate(_CHAR_MAP).split())

    if not (NAME_MIN <= len(name) <= NAME_MAX):
        return None, (
            f"⚠️ طول نام باید بین {_fa(NAME_MIN)} تا {_fa(NAME_MAX)} حرف باشد."
        )

    if not _NAME_RE.match(name):
        return None, (
            "⚠️ فقط از حروف فارسی یا انگلیسی استفاده کنید "
            "(بدون عدد و علامت)."
        )

    return name, None


def validate_password(
    password: str | None,
    phone_number: str | None = None,
) -> str | None:
    """
    پیام خطا یا None اگر رمز مناسب است.
    فقط دو شرط: حداقل ۶ کاراکتر، و برابر شماره موبایل نبودن.
    (حروف، عدد و هر نویسهٔ دیگری آزاد است.)
    """
    password = password or ""

    if len(password) < PASSWORD_MIN:
        return f"⚠️ رمز عبور باید حداقل {_fa(PASSWORD_MIN)} کاراکتر باشد."

    if len(password) > PASSWORD_MAX:
        return f"⚠️ رمز عبور نباید بیشتر از {_fa(PASSWORD_MAX)} کاراکتر باشد."

    if phone_number and _looks_like_phone(password, phone_number):
        return "⚠️ رمز عبور نباید همان شماره موبایل شما باشد."

    return None


def _looks_like_phone(password: str, phone_number: str) -> bool:
    """رمزی که فقط ارقام (و + - فاصله) است و پس از نرمال‌سازی همان شماره است."""
    if not all(ch.isdigit() or ch in "+- " for ch in password):
        return False

    return normalize_phone(password) == normalize_phone(phone_number)


def is_valid_phone(phone_number: str | None) -> bool:
    """موبایل ایران: 09xxxxxxxxx (۱۱ رقم)؛ سایر شماره‌ها: ۸ تا ۱۵ رقم."""
    phone = phone_number or ""

    if not phone.isdigit():
        return False

    if phone.startswith("09"):
        return len(phone) == 11

    return 8 <= len(phone) <= 15
