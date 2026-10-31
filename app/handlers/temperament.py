import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.main import main_menu_keyboard
from app.keyboards.temperament import (
    temperament_intro_keyboard,
    temperament_question_keyboard,
    temperament_result_keyboard,
)
from app.middlewares.subscription import SubscriptionMiddleware
from app.services.temperament_service import (
    calculate_percentages,
    first_unanswered,
    is_valid_session,
    new_session,
    question_text,
    result_text,
    selected_position,
    to_persian_digits,
    total_questions,
)
from app.states.main import MainStates

logger = logging.getLogger(__name__)

router = Router()

# همه دکمه‌های آزمون فقط با اشتراک فعال (یا دوره رایگان) کار می‌کنند؛
# انصراف و بازگشت به منو همیشه مجاز است.
router.callback_query.middleware(
    SubscriptionMiddleware(
        service_title="مزاج شناسی",
        allowed_callbacks={"tq:cancel", "tq:menu"},
    )
)


def intro_text() -> str:
    total = to_persian_digits(total_questions())

    return (
        "🌿 <b>مزاج‌شناسی</b>\n\n"
        f"در این آزمون {total} پرسش از شما پرسیده می‌شود و برای هر پرسش "
        "چهار گزینه وجود دارد. گزینه‌ای را انتخاب کنید که بیشتر به "
        "حالت <b>طبیعی و همیشگی</b> شما شبیه است (نه شرایط موقتی مانند "
        "بیماری، خستگی یا مصرف دارو).\n\n"
        "🔹 در هر مرحله می‌توانید به پرسش قبلی برگردید و پاسخ را اصلاح کنید.\n"
        "🔹 در هر مرحله می‌توانید انصراف دهید و به منوی اصلی برگردید.\n"
        "🔹 آزمون را می‌توانید برای خودتان یا دیگران انجام دهید؛ "
        "نتیجه‌ها ذخیره نمی‌شوند."
    )


async def show_temperament_intro(message: Message) -> None:
    """از منوی اصلی فراخوانی می‌شود."""
    await message.answer(
        intro_text(),
        parse_mode="HTML",
        reply_markup=temperament_intro_keyboard(),
    )


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise


async def load_session(state: FSMContext) -> dict | None:
    data = await state.get_data()
    session = data.get("tq")

    return session if is_valid_session(session) else None


async def show_question(
    callback: CallbackQuery,
    session: dict,
    index: int,
) -> None:
    await safe_edit(
        callback,
        question_text(session, index),
        temperament_question_keyboard(
            index,
            selected_position(session, index),
        ),
    )


async def show_result(
    callback: CallbackQuery,
    state: FSMContext,
    session: dict,
) -> None:
    percentages = calculate_percentages(session["answers"])

    # نتیجه ذخیره نمی‌شود؛ جلسه آزمون هم از حافظه پاک می‌شود
    await state.update_data(tq=None)

    await safe_edit(
        callback,
        result_text(percentages),
        temperament_result_keyboard(),
    )


async def session_expired(callback: CallbackQuery) -> None:
    await callback.answer(
        "این آزمون منقضی شده است. لطفاً دوباره شروع کنید.",
        show_alert=True,
    )

    await safe_edit(
        callback,
        intro_text(),
        temperament_intro_keyboard(),
    )


# ---------------------------------
# شروع آزمون (جدید)
# ---------------------------------

@router.callback_query(F.data == "tq:start")
async def start_test(callback: CallbackQuery, state: FSMContext):
    session = new_session()

    await state.update_data(tq=session)

    await show_question(callback, session, 0)

    await callback.answer()


# ---------------------------------
# ثبت پاسخ
# ---------------------------------

@router.callback_query(F.data.startswith("tq:a:"))
async def answer_question(callback: CallbackQuery, state: FSMContext):
    session = await load_session(state)

    if session is None:
        await session_expired(callback)
        return

    parts = (callback.data or "").split(":")

    try:
        index = int(parts[2])
        position = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer()
        return

    total = total_questions()

    if not (0 <= index < total and 0 <= position < 4):
        await callback.answer()
        return

    frontier = first_unanswered(session)

    # پرسش‌هایی که هنوز به آن‌ها نرسیده‌ایم قابل پاسخ نیستند
    if frontier is not None and index > frontier:
        await callback.answer()
        return

    session["answers"][index] = session["order"][index][position]

    await state.update_data(tq=session)

    next_index = first_unanswered(session)

    if next_index is None:
        await show_result(callback, state, session)
    else:
        await show_question(callback, session, next_index)

    await callback.answer()


# ---------------------------------
# برگشت به پرسش قبلی / رفتن به پرسش بعدی
# ---------------------------------

@router.callback_query(F.data.startswith("tq:back:"))
async def previous_question(callback: CallbackQuery, state: FSMContext):
    session = await load_session(state)

    if session is None:
        await session_expired(callback)
        return

    try:
        index = int((callback.data or "").split(":")[2])
    except (ValueError, IndexError):
        await callback.answer()
        return

    index = min(max(index - 1, 0), total_questions() - 1)

    await show_question(callback, session, index)

    await callback.answer()


@router.callback_query(F.data.startswith("tq:go:"))
async def go_to_question(callback: CallbackQuery, state: FSMContext):
    session = await load_session(state)

    if session is None:
        await session_expired(callback)
        return

    try:
        index = int((callback.data or "").split(":")[2])
    except (ValueError, IndexError):
        await callback.answer()
        return

    frontier = first_unanswered(session)

    if frontier is None:
        await show_result(callback, state, session)
        await callback.answer()
        return

    # نمی‌شود از پرسش‌های بی‌پاسخ پرید
    index = min(max(index, 0), frontier)

    await show_question(callback, session, index)

    await callback.answer()


# ---------------------------------
# انصراف / بازگشت به منو
# ---------------------------------

async def leave_to_main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
) -> None:
    data = await state.get_data()
    phone_number = data.get("phone_number")

    await state.update_data(tq=None)
    await state.set_state(MainStates.menu)

    if callback.message:
        try:
            await callback.message.edit_text(text)
        except TelegramBadRequest:
            pass

        await callback.message.answer(
            "لطفاً خدمت موردنظر خود را انتخاب کنید:",
            reply_markup=main_menu_keyboard(phone_number),
        )

    await callback.answer()


@router.callback_query(F.data == "tq:cancel")
async def cancel_test(callback: CallbackQuery, state: FSMContext):
    await leave_to_main_menu(
        callback,
        state,
        "❌ آزمون لغو شد. هر زمان بخواهید می‌توانید آزمون جدیدی شروع کنید.",
    )


@router.callback_query(F.data == "tq:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await leave_to_main_menu(
        callback,
        state,
        "به منوی اصلی بازگشتید.",
    )
