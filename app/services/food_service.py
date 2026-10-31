"""
منطق داده‌ای بخش طبع‌شناسی خوراکی‌ها.
همه کوئری‌ها صفحه‌بندی‌شده‌اند تا با هزاران خوراکی هم سریع بمانند.
"""

import math

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import FoodItem

NAMES_PAGE_SIZE = 10
SEARCH_PAGE_SIZE = 8
MAX_SIBLING_BUTTONS = 10

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 40

ZWNJ = "\u200c"

_SEARCH_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
    }
)


# =========================================================
# توابع خالص (بدون دیتابیس)
# =========================================================

def normalize_search_query(text: str | None) -> str:
    """حروف عربی → فارسی، حذف نیم‌فاصله و فاصله‌های اضافه."""
    text = (text or "").translate(_SEARCH_CHAR_MAP)
    text = text.replace(ZWNJ, "")

    return " ".join(text.split())


def escape_like(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def total_pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))


def clamp_page(page: int, pages: int) -> int:
    return min(max(page, 0), pages - 1)


def temperament_text(item: FoodItem) -> str:
    if item.warmth == "معتدل":
        return "معتدل"

    if item.warmth and item.moisture:
        return f"{item.warmth} و {item.moisture}"

    return item.warmth or item.moisture or "ثبت نشده"


def split_temperament(temperament: str) -> tuple[str, str]:
    mapping = {
        "معتدل": ("معتدل", "معتدل"),
        "گرم و تر": ("گرم", "تر"),
        "گرم و خشک": ("گرم", "خشک"),
        "سرد و تر": ("سرد", "تر"),
        "سرد و خشک": ("سرد", "خشک"),
    }

    if temperament not in mapping:
        raise ValueError(f"طبع ناشناخته: {temperament}")

    return mapping[temperament]


VALID_TEMPERAMENTS = ("معتدل", "گرم و تر", "گرم و خشک", "سرد و تر", "سرد و خشک")


# =========================================================
# کوئری‌های دسته‌بندی
# =========================================================

def _active_in_category(category: str):
    return and_(
        FoodItem.category == category,
        FoodItem.active.is_(True),
    )


async def count_food_names(
    session: AsyncSession,
    category: str,
) -> int:
    result = await session.execute(
        select(func.count(distinct(FoodItem.name))).where(
            _active_in_category(category)
        )
    )

    return result.scalar_one()


async def get_food_names_page(
    session: AsyncSession,
    category: str,
    page: int,
):
    """
    هر ردیف: item_id (کوچک‌ترین شناسه آن خوراکی)، item_name، variants (تعداد انواع).
    """
    result = await session.execute(
        select(
            func.min(FoodItem.id).label("item_id"),
            FoodItem.name.label("item_name"),
            func.count(FoodItem.id).label("variants"),
        )
        .where(_active_in_category(category))
        .group_by(FoodItem.name)
        .order_by(FoodItem.name)
        .limit(NAMES_PAGE_SIZE)
        .offset(page * NAMES_PAGE_SIZE)
    )

    return result.all()


async def name_page_index(
    session: AsyncSession,
    category: str,
    name: str,
) -> int:
    """خوراکی موردنظر در کدام صفحه فهرست دسته قرار دارد (برای دکمه بازگشت)."""
    result = await session.execute(
        select(func.count(distinct(FoodItem.name))).where(
            _active_in_category(category),
            FoodItem.name < name,
        )
    )

    return result.scalar_one() // NAMES_PAGE_SIZE


async def get_active_item(
    session: AsyncSession,
    item_id: int,
) -> FoodItem | None:
    item = await session.get(FoodItem, item_id)

    if item is None or not item.active:
        return None

    return item


async def get_siblings(
    session: AsyncSession,
    item: FoodItem,
) -> list[FoodItem]:
    """همه انواع/گونه‌های فعال یک خوراکی (هم‌نام و هم‌دسته)."""
    result = await session.execute(
        select(FoodItem)
        .where(
            _active_in_category(item.category),
            FoodItem.name == item.name,
        )
        .order_by(FoodItem.variety, FoodItem.id)
    )

    return list(result.scalars().all())


# =========================================================
# جستجو
# =========================================================

def _search_condition(query: str):
    pattern = f"%{escape_like(query)}%"

    name_clean = func.replace(FoodItem.name, ZWNJ, "")
    variety_clean = func.replace(
        func.coalesce(FoodItem.variety, ""),
        ZWNJ,
        "",
    )
    full_clean = func.replace(
        FoodItem.name + " " + func.coalesce(FoodItem.variety, ""),
        ZWNJ,
        "",
    )

    return and_(
        FoodItem.active.is_(True),
        or_(
            name_clean.ilike(pattern, escape="\\"),
            variety_clean.ilike(pattern, escape="\\"),
            full_clean.ilike(pattern, escape="\\"),
        ),
    )


async def search_foods(
    session: AsyncSession,
    query: str,
    page: int,
) -> tuple[list[FoodItem], int]:
    condition = _search_condition(query)

    total = (
        await session.execute(
            select(func.count(FoodItem.id)).where(condition)
        )
    ).scalar_one()

    pages = total_pages(total, SEARCH_PAGE_SIZE)
    page = clamp_page(page, pages)

    result = await session.execute(
        select(FoodItem)
        .where(condition)
        .order_by(FoodItem.name, FoodItem.variety, FoodItem.id)
        .limit(SEARCH_PAGE_SIZE)
        .offset(page * SEARCH_PAGE_SIZE)
    )

    return list(result.scalars().all()), total
