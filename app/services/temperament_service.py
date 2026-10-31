"""منطق خالص آزمون مزاج‌شناسی (بدون وابستگی به تلگرام یا دیتابیس)."""

import html
import random

from app.data.temperament_questions import (
    QUESTIONS,
    TEMPERAMENT_KEYS,
    TEMPERAMENTS,
)

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

DISCLAIMER = (
    "⚠️ این نتایج قطعی نیست و به تناسب شرایط فردی و نوع تغذیه "
    "هر فرد می‌تواند متفاوت باشد."
)

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(value) -> str:
    return str(value).translate(_PERSIAN_DIGITS)


def total_questions() -> int:
    return len(QUESTIONS)


def new_session(rng: random.Random | None = None) -> dict:
    """
    یک آزمون جدید می‌سازد.
    ترتیب گزینه‌های هر پرسش یک‌بار تصادفی می‌شود و در جلسه ثابت می‌ماند
    (با برگشت به پرسش قبلی همان ترتیب نمایش داده می‌شود).
    """
    rng = rng or random.SystemRandom()

    order = []

    for _ in QUESTIONS:
        keys = list(TEMPERAMENT_KEYS)
        rng.shuffle(keys)
        order.append(keys)

    return {
        "order": order,
        "answers": [None] * len(QUESTIONS),
    }


def is_valid_session(session) -> bool:
    """اگر تعداد پرسش‌ها بعد از ویرایش فایل پرسش‌ها عوض شده باشد، جلسه قدیمی نامعتبر است."""
    if not isinstance(session, dict):
        return False

    order = session.get("order")
    answers = session.get("answers")

    if not isinstance(order, list) or not isinstance(answers, list):
        return False

    if len(order) != len(QUESTIONS) or len(answers) != len(QUESTIONS):
        return False

    return all(
        isinstance(item, list)
        and sorted(item) == sorted(TEMPERAMENT_KEYS)
        for item in order
    )


def first_unanswered(session: dict) -> int | None:
    for index, answer in enumerate(session["answers"]):
        if answer is None:
            return index

    return None


def answered_count(session: dict) -> int:
    return sum(1 for answer in session["answers"] if answer is not None)


def selected_position(session: dict, index: int) -> int | None:
    """جایگاه (۰ تا ۳) گزینه‌ای که کاربر قبلاً برای این پرسش انتخاب کرده."""
    answer = session["answers"][index]

    if answer is None:
        return None

    return session["order"][index].index(answer)


def question_text(session: dict, index: int) -> str:
    total = len(QUESTIONS)
    question = QUESTIONS[index]

    filled = round(answered_count(session) / total * 10)
    bar = "▰" * filled + "▱" * (10 - filled)

    lines = [
        "🌿 <b>مزاج‌شناسی</b>",
        f"سؤال {to_persian_digits(index + 1)} از {to_persian_digits(total)}   {bar}",
        "",
        f"<b>{html.escape(question['text'])}</b>",
        "",
    ]

    for position, key in enumerate(session["order"][index]):
        option = html.escape(question["options"][key])
        lines.append(f"{NUMBER_EMOJIS[position]} {option}")
        lines.append("")

    lines.append("یکی از گزینه‌ها را انتخاب کنید:")

    return "\n".join(lines)


def calculate_percentages(answers: list) -> dict:
    """
    درصد هر مزاج را برمی‌گرداند؛ مجموع همیشه دقیقاً ۱۰۰ است
    (روش بزرگ‌ترین باقی‌مانده).
    """
    counts = {key: 0 for key in TEMPERAMENT_KEYS}

    for answer in answers:
        if answer in counts:
            counts[answer] += 1

    total = sum(counts.values())

    if total == 0:
        return {key: 0 for key in TEMPERAMENT_KEYS}

    exact = {key: counts[key] * 100 / total for key in TEMPERAMENT_KEYS}
    percentages = {key: int(exact[key]) for key in TEMPERAMENT_KEYS}

    remaining = 100 - sum(percentages.values())

    by_remainder = sorted(
        TEMPERAMENT_KEYS,
        key=lambda key: (exact[key] - percentages[key]),
        reverse=True,
    )

    for key in by_remainder[:remaining]:
        percentages[key] += 1

    return percentages


def dominant_keys(percentages: dict) -> list:
    highest = max(percentages.values())

    return [key for key in TEMPERAMENT_KEYS if percentages[key] == highest]


def result_text(percentages: dict) -> str:
    ordered = sorted(
        TEMPERAMENT_KEYS,
        key=lambda key: percentages[key],
        reverse=True,
    )

    lines = [
        "🌿 <b>نتیجه مزاج‌شناسی</b>",
        "",
        "مزاج شما به نسبت پاسخ‌ها به شرح زیر می‌باشد:",
        "",
    ]

    for key in ordered:
        info = TEMPERAMENTS[key]

        lines.append(
            f"{info['emoji']} {to_persian_digits(percentages[key])}٪ "
            f"{info['name']} ({info['quality']})"
        )

    dominant = dominant_keys(percentages)
    names = " و ".join(TEMPERAMENTS[key]["name"] for key in dominant)

    lines += ["", f"📖 <b>مزاج غالب: {names}</b>", ""]

    lines.append(DISCLAIMER)

    return "\n".join(lines)
