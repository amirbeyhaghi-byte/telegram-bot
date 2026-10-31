from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.temperament_service import to_persian_digits

FOOD_CATEGORIES = [
    ("meat", "گوشت و فرآورده‌های گوشتی"),
    ("fish", "آبزیان"),
    ("dairy", "لبنیات و تخم‌مرغ"),
    ("grains", "غلات و فرآورده‌های غلات"),
    ("legumes", "حبوبات"),
    ("fruits", "میوه‌ها"),
    ("vegetables", "سبزیجات و گیاهان"),
    ("nuts", "مغزها، دانه‌ها و خشکبار"),
    ("spices", "ادویه‌ها و چاشنی‌ها"),
    ("oils", "روغن‌ها و چربی‌ها"),
    ("sweets", "شیرینی‌ها و شیرین‌کننده‌ها"),
    ("drinks", "نوشیدنی‌ها و دم‌نوش‌ها"),
]

MAX_SIBLING_BUTTONS = 10


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _nav_row(prefix: str, page: int, pages: int):
    """ردیف صفحه‌بندی؛ prefix مثل «food:c:meat:» یا «food:q:»."""
    if pages <= 1:
        return None

    row = []

    if page > 0:
        row.append(_button("◀️ قبلی", f"{prefix}{page - 1}"))

    row.append(
        _button(
            f"{to_persian_digits(page + 1)} / {to_persian_digits(pages)}",
            "food:noop",
        )
    )

    if page < pages - 1:
        row.append(_button("بعدی ▶️", f"{prefix}{page + 1}"))

    return row


def food_categories_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [_button(title, f"food:c:{key}:0")]
        for key, title in FOOD_CATEGORIES
    ]

    buttons.append([_button("🔍 جستجوی خوراکی", "food:s")])
    buttons.append([_button("🔙 بازگشت به منوی اصلی", "food_back_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def food_names_keyboard(
    category_key: str,
    rows,
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    buttons = []

    for row in rows:
        label = row.item_name

        if row.variants > 1:
            label += f" ({to_persian_digits(row.variants)} نوع)"

        buttons.append([_button(label, f"food:n:{row.item_id}")])

    nav = _nav_row(f"food:c:{category_key}:", page, pages)

    if nav:
        buttons.append(nav)

    buttons.append(
        [
            _button("🔍 جستجو", "food:s"),
            _button("📂 دسته‌ها", "food:cats"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def food_varieties_keyboard(
    items,
    back_callback: str,
) -> InlineKeyboardMarkup:
    buttons = [
        [_button(item.variety or "بدون نوع", f"food:i:{item.id}:c")]
        for item in items
    ]

    buttons.append([_button("🔙 بازگشت به خوراکی‌ها", back_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def food_detail_keyboard(
    item,
    siblings,
    src: str,
    back_callback: str,
) -> InlineKeyboardMarkup:
    buttons = []

    others = [other for other in siblings if other.id != item.id]

    for other in others[:10]:
        buttons.append(
            [
                _button(
                    f"🔹 {other.variety or 'بدون نوع'}",
                    f"food:i:{other.id}:{src}",
                )
            ]
        )

    buttons.append([_button("🔙 بازگشت", back_callback)])

    buttons.append(
        [
            _button("🔍 جستجو", "food:s"),
            _button("📂 دسته‌ها", "food:cats"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def food_search_keyboard(
    items,
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    buttons = []

    for item in items:
        label = item.name

        if item.variety:
            label += f" — {item.variety}"

        buttons.append([_button(label, f"food:i:{item.id}:q{page}")])

    nav = _nav_row("food:q:", page, pages)

    if nav:
        buttons.append(nav)

    buttons.append([_button("📂 دسته‌ها", "food:cats")])
    buttons.append([_button("🔙 بازگشت به منوی اصلی", "food_back_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def food_search_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button("📂 بازگشت به دسته‌ها", "food:cats")]]
    )
