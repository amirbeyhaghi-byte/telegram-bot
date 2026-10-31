import html
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database.database import AsyncSessionLocal
from app.database.models import FoodItem
from app.handlers.main_menu import (
    MENU_TEXTS,
    check_service_access,
    main_menu_handler,
)
from app.keyboards.food import (
    FOOD_CATEGORIES,
    food_categories_keyboard,
    food_detail_keyboard,
    food_names_keyboard,
    food_search_keyboard,
    food_search_prompt_keyboard,
    food_varieties_keyboard,
)
from app.keyboards.main import main_menu_keyboard
from app.middlewares.subscription import SubscriptionMiddleware
from app.services import food_service as foods
from app.services.temperament_service import to_persian_digits
from app.states.food import FoodStates
from app.states.main import MainStates
from app.telegram_utils import safe_edit

logger = logging.getLogger(__name__)

router = Router()

SERVICE_TITLE = "طبع شناسی خوراکی‌ها"

# همه دکمه‌های این بخش فقط با اشتراک فعال (یا دوره رایگان) کار می‌کنند؛
# فقط «بازگشت به منوی اصلی» همیشه مجاز است.
router.callback_query.middleware(
    SubscriptionMiddleware(
        service_title=SERVICE_TITLE,
        allowed_callbacks={"food_back_main"},
    )
)

CATEGORIES_TEXT = (
    "🍎 <b>طبع شناسی خوراکی‌ها</b>\n\n"
    "دسته‌بندی موردنظر را انتخاب کنید یا خوراکی را جستجو کنید:"
)


# =========================================================
# توابع کمکی
# =========================================================

def category_title(category_key: str) -> str | None:
    for key, title in FOOD_CATEGORIES:
        if key == category_key:
            return title

    return None


def category_key_of(title: str) -> str | None:
    for key, name in FOOD_CATEGORIES:
        if name == title:
            return key

    return None


def parse_int(value: str, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def food_detail_text(item: FoodItem) -> str:
    text = (
        "<b>🍎 اطلاعات خوراکی</b>\n\n"
        f"📌 <b>نام:</b> {html.escape(item.name)}\n"
        f"📂 <b>دسته:</b> {html.escape(item.category)}\n"
    )

    if item.variety:
        text += f"🔹 <b>نوع / گونه:</b> {html.escape(item.variety)}\n"

    text += f"🌡 <b>طبع:</b> {html.escape(foods.temperament_text(item))}\n"

    if item.description:
        text += "\n📝 <b>توضیحات:</b>\n" + html.escape(item.description)

    return text


# =========================================================
# ورود از منوی اصلی و صفحه دسته‌ها
# =========================================================

async def show_food_categories_message(message: Message) -> None:
    """از منوی اصلی فراخوانی می‌شود."""
    await message.answer(
        CATEGORIES_TEXT,
        parse_mode="HTML",
        reply_markup=food_categories_keyboard(),
    )


@router.callback_query(F.data == "food:cats")
async def show_categories(callback: CallbackQuery, state: FSMContext):
    # از حالت جستجو خارج می‌شویم تا متن‌های بعدی جستجو حساب نشوند
    await state.set_state(MainStates.menu)

    await safe_edit(callback, CATEGORIES_TEXT, food_categories_keyboard())

    await callback.answer()


@router.callback_query(F.data == "food:noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "food_back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    phone_number = data.get("phone_number")

    await state.set_state(MainStates.menu)

    if callback.message:
        await safe_edit(callback, "به منوی اصلی بازگشتید.")

        await callback.message.answer(
            "لطفاً خدمت موردنظر خود را انتخاب کنید:",
            reply_markup=main_menu_keyboard(phone_number),
        )

    await callback.answer()


# =========================================================
# فهرست خوراکی‌های یک دسته (صفحه‌بندی‌شده)
# =========================================================

async def show_category_page(
    callback: CallbackQuery,
    category_key: str,
    page: int,
) -> None:
    title = category_title(category_key)

    if title is None:
        await callback.answer("دسته‌بندی نامعتبر است.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        total = await foods.count_food_names(session, title)

        pages = foods.total_pages(total, foods.NAMES_PAGE_SIZE)
        page = foods.clamp_page(page, pages)

        rows = (
            await foods.get_food_names_page(session, title, page)
            if total
            else []
        )

    if not rows:
        await safe_edit(
            callback,
            f"📂 <b>{html.escape(title)}</b>\n\n"
            "در حال حاضر خوراکی‌ای در این دسته ثبت نشده است.",
            food_categories_keyboard(),
        )
        return

    await safe_edit(
        callback,
        f"📂 <b>{html.escape(title)}</b>\n"
        f"تعداد: {to_persian_digits(total)} خوراکی\n\n"
        "خوراکی موردنظر را انتخاب کنید:",
        food_names_keyboard(category_key, rows, page, pages),
    )


@router.callback_query(F.data.startswith("food:c:"))
async def category_page_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")

    if len(parts) != 4:
        await callback.answer()
        return

    await state.set_state(MainStates.menu)

    await show_category_page(
        callback,
        parts[2],
        parse_int(parts[3], 0),
    )

    await callback.answer()


# =========================================================
# انواع یک خوراکی
# =========================================================

async def show_varieties_or_detail(
    callback: CallbackQuery,
    item_id: int,
) -> None:
    async with AsyncSessionLocal() as session:
        item = await foods.get_active_item(session, item_id)

        if item is None:
            await callback.answer("خوراکی پیدا نشد.", show_alert=True)
            return

        siblings = await foods.get_siblings(session, item)

        category_key = category_key_of(item.category)
        page = await foods.name_page_index(session, item.category, item.name)

    back_callback = (
        f"food:c:{category_key}:{page}"
        if category_key
        else "food:cats"
    )

    # فقط یک نوع وجود دارد: مستقیم اطلاعات کامل
    if len(siblings) <= 1:
        await safe_edit(
            callback,
            food_detail_text(item),
            food_detail_keyboard(item, siblings, "c", back_callback),
        )
        return

    await safe_edit(
        callback,
        f"🍎 <b>{html.escape(item.name)}</b>\n"
        f"📂 {html.escape(item.category)}\n\n"
        "نوع یا گونه موردنظر را انتخاب کنید:",
        food_varieties_keyboard(siblings, back_callback),
    )


@router.callback_query(F.data.startswith("food:n:"))
async def food_name_handler(callback: CallbackQuery):
    item_id = parse_int((callback.data or "").split(":")[2])

    if item_id is None:
        await callback.answer("اطلاعات نامعتبر است.", show_alert=True)
        return

    await show_varieties_or_detail(callback, item_id)

    await callback.answer()


@router.callback_query(F.data.startswith("food:b:"))
async def food_back_handler(callback: CallbackQuery):
    """بازگشت از صفحه جزئیات (مسیر دسته‌بندی)."""
    item_id = parse_int((callback.data or "").split(":")[2])

    if item_id is None:
        await callback.answer()
        return

    await show_varieties_or_detail(callback, item_id)

    await callback.answer()


# =========================================================
# اطلاعات کامل یک خوراکی
# =========================================================

@router.callback_query(F.data.startswith("food:i:"))
async def food_item_handler(callback: CallbackQuery):
    parts = (callback.data or "").split(":")

    if len(parts) != 4:
        await callback.answer()
        return

    item_id = parse_int(parts[2])
    src = parts[3]

    if item_id is None or not (src == "c" or src.startswith("q")):
        await callback.answer("اطلاعات نامعتبر است.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        item = await foods.get_active_item(session, item_id)

        if item is None:
            await callback.answer("خوراکی پیدا نشد.", show_alert=True)
            return

        siblings = await foods.get_siblings(session, item)

    if src == "c":
        back_callback = f"food:b:{item.id}"
    else:
        back_callback = f"food:q:{parse_int(src[1:], 0)}"

    await safe_edit(
        callback,
        food_detail_text(item),
        food_detail_keyboard(item, siblings, src, back_callback),
    )

    await callback.answer()


# =========================================================
# جستجو
# =========================================================

@router.callback_query(F.data == "food:s")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FoodStates.searching)

    await safe_edit(
        callback,
        "🔍 <b>جستجوی خوراکی</b>\n\n"
        "نام خوراکی یا نوع آن را بنویسید (مثلاً: سیب یا گوسفند).",
        food_search_prompt_keyboard(),
    )

    await callback.answer()


async def build_search_view(query: str, page: int):
    async with AsyncSessionLocal() as session:
        items, total = await foods.search_foods(session, query, page)

    pages = foods.total_pages(total, foods.SEARCH_PAGE_SIZE)
    page = foods.clamp_page(page, pages)

    safe_query = html.escape(query)

    if total == 0:
        return (
            f"🔍 نتیجه‌ای برای «{safe_query}» پیدا نشد.\n\n"
            "عبارت دیگری بنویسید یا از دسته‌ها انتخاب کنید.",
            food_search_prompt_keyboard(),
        )

    return (
        f"🔍 <b>نتایج جستجو برای «{safe_query}»</b>\n"
        f"تعداد: {to_persian_digits(total)} مورد\n\n"
        "یکی را انتخاب کنید، یا برای جستجوی جدید نام دیگری بنویسید.",
        food_search_keyboard(items, page, pages),
    )


@router.message(FoodStates.searching)
async def search_message(message: Message, state: FSMContext):
    raw_text = (message.text or "").strip()

    # اگر به جای عبارت جستجو، دکمه‌ای از منوی اصلی زده شد، از جستجو خارج می‌شویم
    if raw_text in MENU_TEXTS:
        await state.set_state(MainStates.menu)
        await main_menu_handler(message, state)
        return

    data = await state.get_data()

    # پیام‌های متنی از Middleware عبور نمی‌کنند؛ اشتراک را اینجا هم چک می‌کنیم
    if not await check_service_access(
        message,
        data.get("phone_number"),
        SERVICE_TITLE,
    ):
        await state.set_state(MainStates.menu)
        return

    query = foods.normalize_search_query(raw_text)

    if not (
        foods.MIN_QUERY_LENGTH <= len(query) <= foods.MAX_QUERY_LENGTH
    ):
        await message.answer(
            "⚠️ عبارت جستجو باید حداقل "
            f"{to_persian_digits(foods.MIN_QUERY_LENGTH)} و حداکثر "
            f"{to_persian_digits(foods.MAX_QUERY_LENGTH)} حرف باشد."
        )
        return

    await state.update_data(food_query=query)

    text, keyboard = await build_search_view(query, 0)

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("food:q:"))
async def search_page_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    query = data.get("food_query")

    if not query:
        await callback.answer(
            "جستجو منقضی شده است. دوباره جستجو کنید.",
            show_alert=True,
        )

        await safe_edit(callback, CATEGORIES_TEXT, food_categories_keyboard())
        return

    page = parse_int((callback.data or "").split(":")[2], 0)

    text, keyboard = await build_search_view(query, page)

    await safe_edit(callback, text, keyboard)

    await callback.answer()
